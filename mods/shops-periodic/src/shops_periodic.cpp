// shops_periodic.cpp - rerolls the game's in-memory ShopLineupParam rows on a timer.
//
// The manifest (src/manifest.h) supplies curated pools and the ShopLineupParam row ids to refresh.
// Planning is pure C++ and host-tested.  The in-memory write is fail-closed: no row is touched until
// the owner configures a verified AOB and row geometry in shops_periodic.ini.  Every resolved address
// is probed with VirtualQuery before a single u32 is written, so a wrong game build cannot fault the
// process - the worst outcome is a log line saying why the write stayed off.
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>
#include <map>
#include <random>
#include <string>
#include <vector>

#include <windows.h>

#include "manifest.h"

using namespace shops_periodic;

namespace {

struct Config {
    std::atomic<bool> enabled{true};
    std::atomic<unsigned> every_minutes{15};
};

// All game-specific values live here.  The DLL never guesses them: without an AOB and a row count it
// stays in tick-only mode.  `equip_id_offset = 8` matches the on-disk param row layout
// (id u32, name offset u32, then fields); a live build may differ and must be verified by the owner.
struct ParamConfig {
    std::string aob;
    int disp_offset = -1;              // >= 0: disp32 at match+offset; -1: the match is the rows base
    bool deref = false;                // 1: the resolved address holds the pointer to follow once
    std::uint32_t rows_offset = 0;     // bytes from the resolved pointer to the first row entry
    std::uint32_t row_count = 0;       // number of row entries to index
    std::uint32_t row_stride = 0;      // bytes between row entries
    bool row_pointer = true;           // entries are pointers to rows, not inline rows
    std::uint32_t id_offset = 0;       // u32 row id inside a row
    std::uint32_t equip_id_offset = 8; // u32 equipId inside a row
    std::uint32_t seed = 0;            // 0 = fresh seed each launch

    // Offsets are capped well below a plausible row size: a huge mistyped value could wrap a pointer
    // into unrelated committed memory and pass readable() while writing to the wrong place.
    bool configured() const {
        return !aob.empty() && row_count != 0 && row_stride != 0 &&
               rows_offset < 0x100000 && id_offset < 0x100000 && equip_id_offset < 0x100000;
    }
};

using RowMap = std::map<std::uint32_t, std::uint8_t*>;

std::string read_ini(const char* path) {
    std::ifstream f(path);
    return std::string(std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>());
}

bool parse_u32(const std::string& text, std::uint32_t& out) {
    if (text.empty()) {
        return false;
    }
    char* end = nullptr;
    errno = 0;
    const unsigned long value = std::strtoul(text.c_str(), &end, 10);
    if (errno == ERANGE || end != text.c_str() + text.size() || value > 0xFFFFFFFFul) {
        return false;
    }
    out = static_cast<std::uint32_t>(value);
    return true;
}

bool parse_i32(const std::string& text, int& out) {
    if (text.empty()) {
        return false;
    }
    char* end = nullptr;
    errno = 0;
    const long value = std::strtol(text.c_str(), &end, 10);
    if (errno == ERANGE || end != text.c_str() + text.size() ||
        value < -2147483647L || value > 2147483647L) {
        return false;
    }
    out = static_cast<int>(value);
    return true;
}

bool readable(const void* address, std::size_t bytes) {
    MEMORY_BASIC_INFORMATION info{};
    if (VirtualQuery(address, &info, sizeof(info)) != sizeof(info)) {
        return false;
    }
    if (info.State != MEM_COMMIT || info.Protect == PAGE_NOACCESS ||
        info.Protect == (PAGE_GUARD | PAGE_NOACCESS)) {
        return false;
    }
    const auto offset = static_cast<std::size_t>(
        static_cast<const std::uint8_t*>(address) - static_cast<const std::uint8_t*>(info.BaseAddress));
    return offset <= info.RegionSize && bytes <= info.RegionSize - offset;
}

// --------------------------------------------------------------------------- AOB scan
struct Pattern {
    std::vector<std::uint8_t> bytes;
    std::vector<std::uint8_t> mask;
};

bool parse_pattern(const std::string& text, Pattern& out) {
    std::size_t i = 0;
    while (i < text.size()) {
        while (i < text.size() && text[i] == ' ') {
            ++i;
        }
        if (i >= text.size()) {
            break;
        }
        if (text[i] == '?') {
            if (i + 1 >= text.size() || text[i + 1] != '?') {
                return false;               // wildcards are pairs: ?? = one unknown byte
            }
            out.bytes.push_back(0);
            out.mask.push_back(0);
            i += 2;
        } else {
            if (i + 2 > text.size()) {
                return false;
            }
            const std::string hex = text.substr(i, 2);
            char* end = nullptr;
            const unsigned long value = std::strtoul(hex.c_str(), &end, 16);
            if (end != hex.c_str() + hex.size() || value > 0xFF) {
                return false;
            }
            out.bytes.push_back(static_cast<std::uint8_t>(value));
            out.mask.push_back(0xFF);
            i += 2;
        }
    }
    return !out.bytes.empty();
}

std::uint8_t* scan(const std::uint8_t* begin, std::size_t size, const Pattern& pattern) {
    if (pattern.bytes.empty() || size < pattern.bytes.size()) {
        return nullptr;
    }
    const std::size_t last = size - pattern.bytes.size();
    for (std::size_t i = 0; i <= last; ++i) {
        std::size_t j = 0;
        for (; j < pattern.bytes.size(); ++j) {
            if (pattern.mask[j] && begin[i + j] != pattern.bytes[j]) {
                break;
            }
        }
        if (j == pattern.bytes.size()) {
            return const_cast<std::uint8_t*>(begin + i);
        }
    }
    return nullptr;
}

struct Section {
    std::uint8_t* begin;
    std::size_t size;
};

bool module_range(HMODULE module, std::uint8_t*& base, std::size_t& size) {
    base = reinterpret_cast<std::uint8_t*>(module);
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        return false;
    }
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) {
        return false;
    }
    size = nt->OptionalHeader.SizeOfImage;
    return true;
}

std::vector<Section> exec_sections(std::uint8_t* base) {
    std::vector<Section> out;
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS*>(base + dos->e_lfanew);
    const auto* section = IMAGE_FIRST_SECTION(nt);
    for (unsigned i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        if ((section[i].Characteristics & IMAGE_SCN_MEM_EXECUTE) != 0) {
            out.push_back({base + section[i].VirtualAddress, section[i].Misc.VirtualSize});
        }
    }
    return out;
}

// Find the first AOB hit whose resolved pointer owns a readable array of `row_count` entries.
bool resolve_rows(HMODULE module, const ParamConfig& cfg, std::uint8_t*& rows, std::string& error) {
    Pattern pattern;
    if (!parse_pattern(cfg.aob, pattern)) {
        error = "the configured aob is not valid hex (wildcards are two question marks)";
        return false;
    }
    std::uint8_t* base = nullptr;
    std::size_t size = 0;
    if (!module_range(module, base, size)) {
        error = "cannot read the game's PE headers";
        return false;
    }
    const std::size_t need = static_cast<std::size_t>(cfg.row_count) *
                             static_cast<std::size_t>(cfg.row_stride);
    for (const Section& section : exec_sections(base)) {
        std::uint8_t* hit = scan(section.begin, section.size, pattern);
        if (hit == nullptr) {
            continue;
        }
        std::uint8_t* resolved = hit;
        if (cfg.disp_offset >= 0) {
            const std::size_t at = static_cast<std::size_t>(cfg.disp_offset);
            if (at + sizeof(std::int32_t) > pattern.bytes.size() || !readable(hit + at, sizeof(std::int32_t))) {
                continue;
            }
            std::int32_t displacement = 0;
            std::memcpy(&displacement, hit + at, sizeof(displacement));
            resolved = hit + at + sizeof(std::int32_t) + displacement;
        }
        if (cfg.deref) {
            // The verified ParamRepository AOB points at its singleton *slot*.  Follow it once so
            // rows_offset can be measured from the live object, as the memory probe reports it.
            if (!readable(resolved, sizeof(void*))) {
                continue;
            }
            resolved = *reinterpret_cast<std::uint8_t**>(resolved);
        }
        const auto address = reinterpret_cast<std::uintptr_t>(resolved);
        if (!readable(resolved, sizeof(void*)) || cfg.rows_offset > UINTPTR_MAX - address) {
            continue;
        }
        std::uint8_t* candidate = resolved + cfg.rows_offset;
        if (readable(candidate, need)) {
            rows = candidate;
            return true;
        }
    }
    error = "no AOB hit resolved to a readable ShopLineupParam row array";
    return false;
}

// Index live rows by their id.  A bad geometry shows up here as zero readable rows, never as a write.
bool build_row_map(std::uint8_t* rows, const ParamConfig& cfg, RowMap& out, unsigned& unreadable) {
    for (std::uint32_t i = 0; i < cfg.row_count; ++i) {
        std::uint8_t* entry = rows + static_cast<std::size_t>(i) * cfg.row_stride;
        std::uint8_t* row = entry;
        if (cfg.row_pointer) {
            if (!readable(entry, sizeof(void*))) {
                ++unreadable;
                continue;
            }
            row = *reinterpret_cast<std::uint8_t**>(entry);
            if (row == nullptr) {
                continue;
            }
        }
        if (!readable(row, static_cast<std::size_t>(cfg.id_offset) + sizeof(std::uint32_t))) {
            ++unreadable;
            continue;
        }
        std::uint32_t id = 0;
        std::memcpy(&id, row + cfg.id_offset, sizeof(id));
        if (id != 0) {
            out.emplace(id, row);
        }
    }
    return !out.empty();
}

Config g_cfg;
ParamConfig g_param;
Manifest g_manifest;
RowMap g_rows;
std::atomic<bool> g_running{false};
std::atomic<bool> g_armed{false};
std::atomic<std::uint32_t> g_seed{0};
std::atomic<unsigned> g_ticks{0};
// Raw Win32 handles, not std::thread: DllMain runs under the loader lock, so the worker must be
// created with CreateThread (its body starts only after that lock is released) and shutdown must
// never block for an unbounded join.  The stop event lets a long interval end within one second.
HANDLE g_thread = nullptr;
HANDLE g_stop_event = nullptr;

void tick(const char* why) {
    unsigned slots = 0;
    for (const auto& block : g_manifest.shops) {
        slots += static_cast<unsigned>(block.size());
    }
    std::printf("[shops_periodic] %s: %zu blocks, %u sellable slots, every %u min, manifest bind %016llx, write %s\n",
                why, g_manifest.shop_count(), slots, g_cfg.every_minutes.load(),
                (unsigned long long)g_manifest.bind, g_armed.load() ? "armed" : "tick-only");
    if (!g_armed.load()) {
        return;
    }

    // A fresh seed per tick would make the interval meaningless; advancing one counter keeps every
    // reroll different while a configured seed still makes them reproducible.
    std::mt19937 rng(g_seed.load() + g_ticks.fetch_add(1));
    const std::vector<Reroll> plan = plan_reroll(g_manifest, rng);
    unsigned written = 0;
    unsigned missing = 0;
    unsigned blocked = 0;
    for (const Reroll& item : plan) {
        const auto it = g_rows.find(item.row_id);
        if (it == g_rows.end()) {
            ++missing;
            continue;
        }
        std::uint8_t* target = it->second + static_cast<std::size_t>(g_param.equip_id_offset);
        if (!readable(target, sizeof(std::uint32_t))) {
            ++blocked;
            continue;
        }
        const std::uint32_t value = item.item_id;
        std::memcpy(target, &value, sizeof(value));
        ++written;
    }
    std::printf("[shops_periodic] reroll: %u written, %u row ids not found, %u unreadable\n",
                written, missing, blocked);
}

DWORD WINAPI worker(LPVOID) {
    while (g_running.load()) {
        const unsigned seconds = g_cfg.every_minutes.load() * 60u;
        for (unsigned waited = 0; waited < seconds; ++waited) {
            if (WaitForSingleObject(g_stop_event, 1000) == WAIT_OBJECT_0) {
                return 0;
            }
        }
        if (!g_running.load()) break;
        tick("periodic");
    }
    return 0;
}

}  // namespace

extern "C" __declspec(dllexport) bool shops_periodic_init(const char* manifest_path, const char* ini_path) {
    std::string err;
    if (!load_manifest(manifest_path, g_manifest, err)) {
        std::printf("[shops_periodic] inert: cannot load manifest %s (%s)\n", manifest_path, err.c_str());
        return false;
    }
    const std::string ini_text = read_ini(ini_path);
    unsigned minutes = static_cast<unsigned>(std::strtoul(
        ini_value(ini_text, "general", "every_minutes", "15").c_str(), nullptr, 10));
    // Cap the interval so a mistyped huge value cannot make the worker effectively immortal.
    g_cfg.every_minutes = minutes > 0 ? (minutes < 1440 ? minutes : 1440) : 15;
    g_cfg.enabled = ini_value(ini_text, "general", "enabled", "1") != "0";
    if (!g_cfg.enabled) {
        std::printf("[shops_periodic] inert: enabled = 0 in ini\n");
        return true;
    }
    if (g_thread != nullptr) {
        return true;                     // init is re-entrant from more than one loader
    }

    g_param.aob = ini_value(ini_text, "param", "aob", "");
    parse_i32(ini_value(ini_text, "param", "aob_disp", "-1"), g_param.disp_offset);
    g_param.deref = ini_value(ini_text, "param", "deref", "0") != "0";
    parse_u32(ini_value(ini_text, "param", "rows_offset", "0"), g_param.rows_offset);
    parse_u32(ini_value(ini_text, "param", "row_count", "0"), g_param.row_count);
    parse_u32(ini_value(ini_text, "param", "row_stride", "0"), g_param.row_stride);
    g_param.row_pointer = ini_value(ini_text, "param", "row_pointer", "1") != "0";
    parse_u32(ini_value(ini_text, "param", "id_offset", "0"), g_param.id_offset);
    parse_u32(ini_value(ini_text, "param", "equip_id_offset", "8"), g_param.equip_id_offset);
    parse_u32(ini_value(ini_text, "general", "seed", "0"), g_param.seed);
    if (g_param.seed == 0) {
        // DllMain holds the loader lock: rand_s/random_device can call into other DLLs here.  A
        // monotonic Win32 tick is enough entropy for a game tick and cannot deadlock the loader.
        g_param.seed = static_cast<std::uint32_t>(GetTickCount64());
    }
    g_seed = g_param.seed;

    if (g_param.configured()) {
        std::string error;
        std::uint8_t* rows = nullptr;
        if (resolve_rows(GetModuleHandleW(nullptr), g_param, rows, error)) {
            RowMap indexed;
            unsigned unreadable = 0;
            if (build_row_map(rows, g_param, indexed, unreadable)) {
                g_rows.swap(indexed);
                g_armed = true;
                std::printf("[shops_periodic] armed: %zu row ids (%u unreadable), seed %u, "
                            "stride %u, deref %u, id+%u, equip+%u\n", g_rows.size(), unreadable,
                            g_seed.load(), g_param.row_stride, g_param.deref ? 1 : 0,
                            g_param.id_offset, g_param.equip_id_offset);
            } else {
                std::printf("[shops_periodic] inert: no readable ShopLineupParam rows (%u unreadable entries)\n",
                            unreadable);
            }
        } else {
            std::printf("[shops_periodic] inert: %s\n", error.c_str());
        }
    } else {
        std::printf("[shops_periodic] tick-only: set [param] aob, row_count and row_stride in "
                    "shops_periodic.ini to enable the write\n");
    }

    g_stop_event = CreateEventA(nullptr, TRUE, FALSE, nullptr);
    if (g_stop_event == nullptr) {
        std::printf("[shops_periodic] inert: could not create the stop event\n");
        return true;
    }
    g_running = true;
    g_thread = CreateThread(nullptr, 0, worker, nullptr, 0, nullptr);
    tick("startup");
    return true;
}

extern "C" __declspec(dllexport) void shops_periodic_shutdown() {
    g_running = false;
    g_armed = false;
    if (g_stop_event != nullptr) {
        SetEvent(g_stop_event);
    }
    if (g_thread != nullptr) {
        // Bounded: holding the loader lock while a worker sleeps for 15 minutes was a hang at exit.
        WaitForSingleObject(g_thread, 2000);
        CloseHandle(g_thread);
        g_thread = nullptr;
    }
    if (g_stop_event != nullptr) {
        CloseHandle(g_stop_event);
        g_stop_event = nullptr;
    }
}

BOOL WINAPI DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        char dll_path[MAX_PATH] = {0};
        GetModuleFileNameA(module, dll_path, MAX_PATH);
        std::string folder(dll_path);
        const std::size_t slash = folder.find_last_of("\\/");
        folder = slash == std::string::npos ? std::string(".") : folder.substr(0, slash);
        const std::string ini = folder + "\\shops_periodic.ini";
        // The manifest travels with regulation.bin in <mod root>\mod, two folders up from dll/offline.
        const std::string local = folder + "\\shops_periodic.txt";
        const std::string mod = folder + "\\..\\..\\mod\\shops_periodic.txt";
        const char* manifest = std::ifstream(local).good() ? local.c_str() : mod.c_str();
        try {
            shops_periodic_init(manifest, ini.c_str());
        } catch (...) {
            // DllMain must never throw: leave the game untouched.
            g_running = false;
            g_armed = false;
        }
    } else if (reason == DLL_PROCESS_DETACH) {
        shops_periodic_shutdown();
    }
    return TRUE;
}

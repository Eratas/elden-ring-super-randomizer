// loot_variants.dll - Mod Engine native mod: Borderlands-style loot for Elden Ring.
//
// The Super Randomizer's --loot-variants pass writes loot_variants.txt: per weapon, which affinity
// rows exist, the weapon's upgrade ceiling, and which Ashes of War each row may mount.  This mod
// intercepts the game's shared item-give function and, for every weapon handed out, rewrites
//     item id = base + affinity * 100 + upgrade level
// with a fresh affinity and level from the manifest, and mounts a random Ash of War from the row's
// own pool.  The row is the same weapon, so the model, icon and moveset stay recognisable; what
// changes per pickup is the affinity (stats, scaling, status build-up), the level and the skill.
//
// How the hook works: the give function is resolved once from the two AOBs the item randomizer uses
// (verified on the installed 1.16.1 binary, both resolving to the same function), then every `E8
// rel32` in the executable sections that targets it is found by arithmetic - four on 1.16.1.  Each
// one is pointed at a 14-byte relay next to the module that jumps to this DLL's detour, and the
// detour calls the original function.  No instruction is moved, so the hook composes with mods that
// hook the function itself, and a game update that moves the function but keeps the AOBs still works.
//
// Fail-soft: no manifest, no AOB hit, no relay or no ini means the game runs untouched and the log
// says why.  The detour does not allocate and never throws.
//
// Build: see build.ps1 (MinGW g++).  Config: loot_variants.ini next to the DLL.

#include "variant_logic.h"

#include <windows.h>

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <mutex>
#include <string>
#include <vector>

namespace {

// --------------------------------------------------------------------------- game structures
// Layout verified against the item randomizer's hook (elden-ring-item-randomizer-new-2).
struct ItemInfo {
    std::uint32_t item_id = 0xFFFFFFFFu;
    std::uint32_t item_quantity = 0;
    std::uint32_t item_relayvalue = 0;
    std::uint32_t item_ashes_of_war = 0xFFFFFFFFu;
};

struct ItemGiveStruct {
    std::uint32_t item_struct_count = 0;
    ItemInfo item_info[10];
};

using GiveItemFunction = void (*)(std::uint64_t, ItemGiveStruct*, void*);

constexpr std::size_t kGiveCapacity = 10;

// --------------------------------------------------------------------------- globals
HINSTANCE g_self = nullptr;
loot_variants::Manifest g_manifest;
loot_variants::Options g_options;
GiveItemFunction g_original = nullptr;
std::uint64_t g_seed = 0;
std::mutex g_log_mutex;
std::ofstream g_log;
bool g_log_on = false;
std::atomic<std::uint32_t> g_rolls_logged{0};
std::atomic<std::uint64_t> g_roll_count{0};

void log_line(const std::string& text) {
    if (!g_log_on) {
        return;
    }
    std::lock_guard<std::mutex> lock(g_log_mutex);
    if (g_log.is_open()) {
        g_log << text << '\n';
        g_log.flush();
    }
}

std::wstring dll_dir() {
    wchar_t buffer[MAX_PATH * 4] = {};
    const DWORD n = GetModuleFileNameW(g_self, buffer, static_cast<DWORD>(std::size(buffer)));
    std::wstring path(buffer, n);
    const std::size_t slash = path.find_last_of(L"\\/");
    return slash == std::wstring::npos ? L"." : path.substr(0, slash);
}

bool file_exists(const std::wstring& path) {
    const DWORD attributes = GetFileAttributesW(path.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_DIRECTORY);
}

std::string read_file(const std::wstring& path, bool& ok) {
    ok = false;
    HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                              OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return {};
    }
    LARGE_INTEGER size{};
    if (!GetFileSizeEx(file, &size) || size.QuadPart <= 0 || size.QuadPart > 8 * 1024 * 1024) {
        CloseHandle(file);
        return {};
    }
    std::string data(static_cast<std::size_t>(size.QuadPart), '\0');
    DWORD read = 0;
    const bool read_ok = ReadFile(file, data.data(), static_cast<DWORD>(data.size()), &read, nullptr) != 0;
    CloseHandle(file);
    if (!read_ok) {
        return {};
    }
    data.resize(read);
    ok = true;
    return data;
}

std::wstring join(const std::wstring& a, const std::wstring& b) {
    if (a.empty()) {
        return b;
    }
    const wchar_t last = a.back();
    return a + ((last == L'\\' || last == L'/') ? L"" : L"\\") + b;
}

// The manifest lives next to the DLL when the user copies it there, but the randomizer writes it
// next to regulation.bin - which for a Mod Engine mod folder is `<mod>\regulation.bin` while the DLL
// sits in `<mod>\..\dll\offline` or `<mod>\..\dll`.  Search the layouts that actually exist instead
// of asking the user to copy the file.
std::wstring find_manifest(const std::wstring& dir, const std::wstring& configured) {
    std::vector<std::wstring> candidates;
    if (!configured.empty()) {
        candidates.push_back(configured.size() > 1 && configured[1] == L':'
                                 ? configured
                                 : join(dir, configured));
    }
    candidates.push_back(join(dir, L"loot_variants.txt"));
    std::wstring up = dir;
    for (int i = 0; i < 4; ++i) {
        up = join(up, L"..");
        candidates.push_back(join(up, L"loot_variants.txt"));
        candidates.push_back(join(join(up, L"mod"), L"loot_variants.txt"));
    }
    wchar_t exe[MAX_PATH * 4] = {};
    if (GetModuleFileNameW(nullptr, exe, static_cast<DWORD>(std::size(exe))) > 0) {
        std::wstring game(exe);
        const std::size_t slash = game.find_last_of(L"\\/");
        if (slash != std::wstring::npos) {
            game = game.substr(0, slash);
            candidates.push_back(join(game, L"loot_variants.txt"));
            candidates.push_back(join(join(game, L"mod"), L"loot_variants.txt"));
        }
    }
    for (const std::wstring& path : candidates) {
        if (file_exists(path)) {
            return path;
        }
    }
    return {};
}

std::string narrow(const std::wstring& text) {
    std::string out;
    out.reserve(text.size());
    for (wchar_t ch : text) {
        out.push_back(ch <= 0x7F ? static_cast<char>(ch) : '?');
    }
    return out;
}

// --------------------------------------------------------------------------- ini
// A missing key must be distinguishable from a key set to 0, because the manifest's defaults are the
// fallback and the ini only overrides what it mentions.
bool ini_value(const std::wstring& ini, const wchar_t* section, const wchar_t* key, std::wstring& out) {
    if (ini.empty()) {
        return false;
    }
    wchar_t buffer[1024] = {};
    const DWORD n = GetPrivateProfileStringW(section, key, L"\x01", buffer,
                                             static_cast<DWORD>(std::size(buffer)), ini.c_str());
    if (n == 0 || (n == 1 && buffer[0] == L'\x01')) {
        return false;
    }
    out.assign(buffer, n);
    return true;
}

bool ini_int(const std::wstring& ini, const wchar_t* section, const wchar_t* key, int& out) {
    std::wstring text;
    if (!ini_value(ini, section, key, text) || text.empty()) {
        return false;
    }
    wchar_t* end = nullptr;
    const long value = std::wcstol(text.c_str(), &end, 10);
    if (end == text.c_str()) {
        return false;
    }
    out = static_cast<int>(value);
    return true;
}

void apply_ini(const std::wstring& ini, loot_variants::Options& options) {
    int value = 0;
    if (ini_int(ini, L"roll", L"affinity", value)) {
        options.reroll_affinity = value != 0;
    }
    if (ini_int(ini, L"roll", L"level", value)) {
        options.reroll_level = value != 0;
    }
    if (ini_int(ini, L"roll", L"ash_chance", value)) {
        options.ash_chance = value < 0 ? 0 : (value > 100 ? 100 : value);
    }
    std::wstring curve;
    if (ini_value(ini, L"roll", L"level_curve", curve)) {
        options.level_curve = curve == L"even" ? loot_variants::kCurveEven
                            : curve == L"legendary" ? loot_variants::kCurveLegendary
                                                    : loot_variants::kCurveCommon;
    }
}

// --------------------------------------------------------------------------- AOB scan
struct Pattern {
    std::vector<std::uint8_t> bytes;
    std::vector<std::uint8_t> mask;
};

bool parse_pattern(const char* text, Pattern& out) {
    const char* p = text;
    while (*p) {
        while (*p == ' ') {
            ++p;
        }
        if (!*p) {
            break;
        }
        if (p[0] == '?' && p[1] == '?') {
            out.bytes.push_back(0);
            out.mask.push_back(0);
            p += 2;
        } else {
            char* end = nullptr;
            const unsigned long value = std::strtoul(p, &end, 16);
            if (end == p || value > 0xFF) {
                return false;
            }
            out.bytes.push_back(static_cast<std::uint8_t>(value));
            out.mask.push_back(0xFF);
            p = end;
        }
        while (*p == ' ') {
            ++p;
        }
    }
    return !out.bytes.empty();
}

std::uint8_t* scan(const std::uint8_t* begin, std::size_t size, const Pattern& pattern) {
    if (pattern.bytes.empty() || size < pattern.bytes.size()) {
        return nullptr;
    }
    const std::size_t last = size - pattern.bytes.size();
    const std::uint8_t first = pattern.bytes[0];
    for (std::size_t i = 0; i <= last; ++i) {
        if (pattern.mask[0] && begin[i] != first) {
            continue;
        }
        std::size_t j = 1;
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

struct Section {
    std::uint8_t* begin;
    std::size_t size;
};

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

// Every `E8 rel32` in the game's code that calls `target`.  Resolving the calls by arithmetic rather
// than by four hand-copied AOBs means a game update that keeps the function but reorders the code
// still gets all of them.
std::vector<std::uint8_t*> find_calls(const std::vector<Section>& sections, GiveItemFunction target) {
    std::vector<std::uint8_t*> out;
    const std::uintptr_t destination = reinterpret_cast<std::uintptr_t>(target);
    for (const Section& section : sections) {
        for (std::size_t i = 0; i + 5 <= section.size; ++i) {
            if (section.begin[i] != 0xE8) {
                continue;
            }
            std::int32_t displacement = 0;
            std::memcpy(&displacement, section.begin + i + 1, sizeof(displacement));
            const std::uintptr_t resolved =
                reinterpret_cast<std::uintptr_t>(section.begin + i) + 5 + displacement;
            if (resolved == destination) {
                out.push_back(section.begin + i);
            }
        }
    }
    return out;
}

// A relay has to be within +-2 GB of the call site, so it is allocated next to the game module
// rather than wherever the DLL happened to load.
std::uint8_t* alloc_near(std::uint8_t* module_base, std::size_t module_size, std::size_t need) {
    SYSTEM_INFO info{};
    GetSystemInfo(&info);
    const std::uintptr_t granularity = info.dwAllocationGranularity ? info.dwAllocationGranularity : 0x10000;
    const std::uintptr_t low = reinterpret_cast<std::uintptr_t>(module_base);
    const std::uintptr_t high = low + module_size;
    for (std::uintptr_t delta = 0; delta < 0x70000000ull; delta += granularity) {
        const std::uintptr_t after = (high + delta + granularity - 1) & ~(granularity - 1);
        if (void* p = VirtualAlloc(reinterpret_cast<void*>(after), need, MEM_RESERVE | MEM_COMMIT,
                                   PAGE_EXECUTE_READWRITE)) {
            return static_cast<std::uint8_t*>(p);
        }
        if (low > delta) {
            const std::uintptr_t before = (low - delta) & ~(granularity - 1);
            if (void* p = VirtualAlloc(reinterpret_cast<void*>(before), need, MEM_RESERVE | MEM_COMMIT,
                                       PAGE_EXECUTE_READWRITE)) {
                return static_cast<std::uint8_t*>(p);
            }
        }
    }
    return nullptr;
}

bool patch_call(std::uint8_t* call, std::uint8_t* relay) {
    const std::int64_t relative = reinterpret_cast<std::int64_t>(relay) -
                                  (reinterpret_cast<std::int64_t>(call) + 5);
    if (relative < INT32_MIN || relative > INT32_MAX) {
        return false;
    }
    DWORD old = 0;
    if (!VirtualProtect(call, 5, PAGE_EXECUTE_READWRITE, &old)) {
        return false;
    }
    const std::int32_t displacement = static_cast<std::int32_t>(relative);
    std::memcpy(call + 1, &displacement, sizeof(displacement));
    FlushInstructionCache(GetCurrentProcess(), call, 5);
    DWORD ignored = 0;
    VirtualProtect(call, 5, old, &ignored);
    return true;
}

// --------------------------------------------------------------------------- the detour
void detour(std::uint64_t manager, ItemGiveStruct* items, void* details) {
    if (items != nullptr && !g_manifest.weapons.empty()) {
        thread_local loot_variants::Rng rng(g_seed ^ static_cast<std::uint64_t>(GetCurrentThreadId()));
        std::uint32_t count = items->item_struct_count;
        if (count > kGiveCapacity) {
            count = kGiveCapacity;
        }
        for (std::uint32_t i = 0; i < count; ++i) {
            ItemInfo& item = items->item_info[i];
            const std::uint32_t before = item.item_id;
            const loot_variants::Rolled rolled =
                loot_variants::roll_item(before, g_manifest, g_options, rng);
            if (rolled.item_id == before && rolled.ash == loot_variants::kNoAsh) {
                continue;
            }
            if (rolled.item_id != before) {
                item.item_id = rolled.item_id;
                item.item_quantity = 1;
                item.item_relayvalue = 0;
            }
            if (rolled.ash != loot_variants::kNoAsh) {
                item.item_ashes_of_war = rolled.ash;
            }
            g_roll_count.fetch_add(1, std::memory_order_relaxed);
            const std::uint32_t logged = g_rolls_logged.fetch_add(1, std::memory_order_relaxed);
            if (logged < 20) {
                char line[160] = {};
                std::snprintf(line, sizeof(line), "roll %u -> %u ash=%08X", before, rolled.item_id, rolled.ash);
                log_line(line);
            }
        }
    }
    g_original(manager, items, details);
}

// --------------------------------------------------------------------------- init
DWORD WINAPI init_thread(LPVOID) {
    Sleep(300);                                   // let the loader finish with the process

    const std::wstring dir = dll_dir();
    const std::wstring ini = join(dir, L"loot_variants.ini");
    const bool have_ini = file_exists(ini);

    int enabled = 1;
    int log_on = 1;
    int seed = 0;
    std::wstring configured;
    if (have_ini) {
        ini_int(ini, L"general", L"enabled", enabled);
        ini_int(ini, L"general", L"log", log_on);
        ini_int(ini, L"general", L"seed", seed);
        ini_value(ini, L"general", L"manifest", configured);
    }
    g_log_on = log_on != 0;
    if (g_log_on) {
        g_log.open(std::filesystem::path(join(dir, L"loot_variants.log")),
                   std::ios::out | std::ios::trunc);
        g_log_on = g_log.is_open();
    }
    if (seed != 0) {
        g_seed = static_cast<std::uint64_t>(static_cast<std::uint32_t>(seed));
    }
    log_line("loot_variants: starting");

    if (enabled == 0) {
        log_line("loot_variants: disabled in the ini");
        return 0;
    }

    const std::wstring manifest_path = find_manifest(dir, configured);
    if (manifest_path.empty()) {
        log_line("loot_variants: no loot_variants.txt found (run the randomizer with --loot-variants, "
                 "then keep the file next to this DLL or next to regulation.bin) - inert");
        return 0;
    }
    bool read_ok = false;
    const std::string text = read_file(manifest_path, read_ok);
    if (!read_ok) {
        log_line("loot_variants: cannot read " + narrow(manifest_path) + " - inert");
        return 0;
    }
    std::string error;
    if (!loot_variants::parse_manifest(text, g_manifest, error)) {
        log_line("loot_variants: " + narrow(manifest_path) + ": " + error + " - inert");
        return 0;
    }
    g_options = g_manifest.defaults;
    if (have_ini) {
        apply_ini(ini, g_options);
    }
    {
        char summary[320] = {};
        std::snprintf(summary, sizeof(summary),
                      "loot_variants: manifest %s: %zu weapons, %zu ash pools, %zu bad lines",
                      narrow(manifest_path).c_str(), g_manifest.weapons.size(), g_manifest.gems.size(),
                      g_manifest.bad_lines);
        log_line(summary);
    }

    std::uint8_t* module = nullptr;
    std::size_t module_size = 0;
    if (!module_range(GetModuleHandleW(nullptr), module, module_size)) {
        log_line("loot_variants: cannot read the game's PE headers - inert");
        return 0;
    }

    struct Site {
        const char* aob;
        std::size_t offset;
        const char* name;
    };
    const Site sites[] = {
        {"4C 8D 45 34 48 8D 55 90 49 8B CC E8 ?? ?? ?? ?? 48 8B 05 ?? ?? ?? ?? 48 85 C0 75 2E", 11, "map"},
        {"44 8B 4C 24 34 4C 8D 45 74 48 8D 55 D0 49 8B CC E8 ?? ?? ?? ?? 83 7D 98 00 74 68", 16, "lua"},
    };
    GiveItemFunction target = nullptr;
    for (const Site& site : sites) {
        Pattern pattern;
        if (!parse_pattern(site.aob, pattern)) {
            continue;
        }
        std::uint8_t* hit = scan(module, module_size, pattern);
        if (hit == nullptr) {
            log_line(std::string("loot_variants: no AOB hit for the ") + site.name + " call site");
            continue;
        }
        std::uint8_t* call = hit + site.offset;
        if (*call != 0xE8) {
            log_line(std::string("loot_variants: the ") + site.name + " hit is not a call");
            continue;
        }
        std::int32_t displacement = 0;
        std::memcpy(&displacement, call + 1, sizeof(displacement));
        auto* resolved = reinterpret_cast<GiveItemFunction>(call + 5 + displacement);
        if (target == nullptr) {
            target = resolved;
        } else if (target != resolved) {
            log_line("loot_variants: the two call sites point at different functions - inert");
            return 0;
        }
    }
    if (target == nullptr) {
        log_line("loot_variants: no item-give call site found (unsupported game version?) - inert");
        return 0;
    }

    const std::vector<std::uint8_t*> calls = find_calls(exec_sections(module), target);
    if (calls.empty()) {
        log_line("loot_variants: no call to the give function found - inert");
        return 0;
    }

    std::uint8_t* relay = alloc_near(module, module_size, 64);
    if (relay == nullptr) {
        log_line("loot_variants: no memory within 2 GB of the game for the relay - inert");
        return 0;
    }
    // jmp qword ptr [rip+0] <address>
    const std::uint8_t stub[6] = {0xFF, 0x25, 0x00, 0x00, 0x00, 0x00};
    std::memcpy(relay, stub, sizeof(stub));
    const std::uint64_t destination = reinterpret_cast<std::uint64_t>(&detour);
    std::memcpy(relay + sizeof(stub), &destination, sizeof(destination));
    FlushInstructionCache(GetCurrentProcess(), relay, 14);

    g_original = target;
    std::size_t patched = 0;
    for (std::uint8_t* call : calls) {
        if (patch_call(call, relay)) {
            ++patched;
        }
    }
    if (patched == 0) {
        g_original = nullptr;
        log_line("loot_variants: no call site patched - inert");
        return 0;
    }
    {
        char done[256] = {};
        std::snprintf(done, sizeof(done),
                      "loot_variants: active, %zu call site(s), seed %llu, affinity %d, level %d, "
                      "ash %d%%, curve %d",
                      patched, static_cast<unsigned long long>(g_seed),
                      g_options.reroll_affinity ? 1 : 0, g_options.reroll_level ? 1 : 0,
                      g_options.ash_chance, g_options.level_curve);
        log_line(done);
    }
    return 0;
}

}  // namespace

BOOL WINAPI DllMain(HINSTANCE self, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_self = self;
        DisableThreadLibraryCalls(self);
        // The detour lives in this module: pin it so the game cannot unload code it is still calling.
        HMODULE pinned = nullptr;
        GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_PIN,
                           reinterpret_cast<LPCWSTR>(&DllMain), &pinned);
        const std::uint64_t now = static_cast<std::uint64_t>(GetTickCount64());
        g_seed = (now * 0x9E3779B97F4A7C15ull) ^ (static_cast<std::uint64_t>(GetCurrentProcessId()) << 32);
        HANDLE thread = CreateThread(nullptr, 0, init_thread, nullptr, 0, nullptr);
        if (thread != nullptr) {
            CloseHandle(thread);
        }
    }
    return TRUE;
}

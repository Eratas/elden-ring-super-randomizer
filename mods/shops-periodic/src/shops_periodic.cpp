// shops_periodic.cpp - the runtime mod that rerolls ShopLineupParam every N minutes.
//
// Staging version: reads and parses the manifest (src/manifest.h) and exposes the periodic tick.
// The write into the game's ShopLineupParam rows (the actual reroll) is the next probe step
// (run verify_aobs.py first); until then the mod stays inert by design.
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <string>

#include <windows.h>

#include "manifest.h"

using namespace shops_periodic;

namespace {

struct Config {
    std::atomic<bool> enabled{true};
    std::atomic<unsigned> every_minutes{15};
};

std::string read_ini(const char* path) {
    std::ifstream f(path);
    return std::string(std::istreambuf_iterator<char>(f), std::istreambuf_iterator<char>());
}

Config g_cfg;
Manifest g_manifest;
std::atomic<bool> g_running{false};
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
    std::printf("[shops_periodic] %s: %zu blocks, %u sellable slots, every %u min, manifest bind %016llx\n",
                why, g_manifest.shop_count(), slots, g_cfg.every_minutes.load(),
                (unsigned long long)g_manifest.bind);
    // --probe-step-- write rolled items into ShopLineupParam here; inert until the AOB is verified.
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
        }
    } else if (reason == DLL_PROCESS_DETACH) {
        shops_periodic_shutdown();
    }
    return TRUE;
}

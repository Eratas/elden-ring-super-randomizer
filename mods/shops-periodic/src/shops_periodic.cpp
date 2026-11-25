// shops_periodic.cpp - the runtime mod that rerolls ShopLineupParam every N minutes.
//
// Staging version: reads and parses the manifest (src/manifest.h) and exposes the periodic tick.
// The write into the game's ShopLineupParam rows (the actual reroll) is the next probe step
// (run verify_aobs.py first); until then the mod stays inert by design.
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <thread>
#include <chrono>

#include <windows.h>

#include "manifest.h"

using namespace shops_periodic;

namespace {

struct Config {
    std::atomic<bool> enabled{true};
    std::atomic<unsigned> every_minutes{15};
};

std::string ini_value(const char* ini_path, const char* section, const char* key, const char* fallback) {
    std::ifstream f(ini_path);
    if (!f) {
        return fallback;
    }
    std::string line, section_cur;
    while (std::getline(f, line)) {
        if (line.empty()) continue;
        if (line.front() == '[') {
            section_cur = line;
            continue;
        }
        if (section_cur != std::string("[") + section + "]" || line.find(':') == std::string::npos) {
            continue;
        }
        std::string k = line.substr(0, line.find(':'));
        std::string v = line.substr(line.find(':') + 1);
        while (!v.empty() && v.front() == ' ') v.erase(v.begin());
        while (!k.empty() && (k.back() == ' ' || k.back() == '\r')) k.pop_back();
        while (!v.empty() && v.back() == '\r') v.pop_back();
        if (k == key) {
            return v.empty() ? fallback : v;
        }
    }
    return fallback;
}

Config g_cfg;
Manifest g_manifest;
std::atomic<bool> g_running{false};
std::thread g_thread;

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

void worker() {
    while (g_running.load()) {
        unsigned minutes = g_cfg.every_minutes.load();
        std::this_thread::sleep_for(std::chrono::minutes(minutes));
        if (!g_running.load()) break;
        tick("periodic");
    }
}

}  // namespace

extern "C" __declspec(dllexport) bool shops_periodic_init(const char* manifest_path, const char* ini_path) {
    std::string err;
    if (!load_manifest(manifest_path, g_manifest, err)) {
        std::printf("[shops_periodic] inert: cannot load manifest %s (%s)\n", manifest_path, err.c_str());
        return false;
    }
    unsigned minutes = static_cast<unsigned>(std::strtoul(
        ini_value(ini_path, "general", "every_minutes", "15").c_str(), nullptr, 10));
    g_cfg.every_minutes = minutes > 0 ? minutes : 15;
    g_cfg.enabled = ini_value(ini_path, "general", "enabled", "1") != "0";
    if (!g_cfg.enabled) {
        std::printf("[shops_periodic] inert: enabled = 0 in ini\n");
        return true;
    }
    g_running = true;
    g_thread = std::thread(worker);
    tick("startup");
    return true;
}

extern "C" __declspec(dllexport) void shops_periodic_shutdown() {
    g_running = false;
    if (g_thread.joinable()) {
        g_thread.join();
    }
}

BOOL WINAPI DllMain(HMODULE, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_DETACH) {
        shops_periodic_shutdown();
    }
    return TRUE;
}

// bench_variants.cpp - measure the per-pickup roll on the host (no game required).
//
//   build.ps1 -Bench   builds and runs this after the correctness tests.
//
// The detour runs once per granted item, so a slow roll would show up as a hitch during loot
// drops.  This is a rough throughput check, not a profile of the game.  `roll_item` is pure and
// allocates nothing on the hot path except the first pool-cache insertion per (manifest, row,
// affinity).

#include "variant_logic.h"

#include <chrono>
#include <cstdio>
#include <string>

int main(int argc, char** argv) {
    const std::string text =
        "MADLOVE-LOOT-VARIANTS 2\n"
        "defaults 50 common 1 1\n"
        "weapon 1000000 25 8191 0 0 0 0 0 0 0 0 0 0 0 0 0\n"
        "weapon 1010000 10 8191 0 0 0 0 0 0 0 0 0 0 0 0 0\n"
        "armor 40000 10 12 40000 41000\n"
        "gems 0 10000 10100 10200 10300 10400\n";
    loot_variants::Manifest m;
    std::string error;
    if (!loot_variants::parse_manifest(text, m, error)) {
        std::printf("bench: bad manifest: %s\n", error.c_str());
        return 1;
    }
    if (m.armor.empty() || m.weapons.empty()) {
        std::printf("bench: manifest has no armour or weapon to roll\n");
        return 1;
    }
    loot_variants::Options options = m.defaults;
    options.ash_chance = 100;             // exercise the pool lookup as well
    loot_variants::Rng rng(12345);
    const int draws = argc > 1 ? std::atoi(argv[1]) : 1000000;

    // Warm up the thread-local pool cache and the branch predictor.
    for (int i = 0; i < 10000; ++i) {
        loot_variants::roll_item(1000000 + (i % 13) * 100 + (i % 26), m, options, rng);
        loot_variants::roll_item(loot_variants::kArmorBit | 40000, m, options, rng);
    }
    std::uint64_t sink = 0;
    const auto start = std::chrono::steady_clock::now();
    for (int i = 0; i < draws; ++i) {
        const loot_variants::Rolled r = loot_variants::roll_item(
            (i & 1) ? (loot_variants::kArmorBit | 40000)
                    : (1000000 + (i % 13) * 100 + (i % 26)),
            m, options, rng);
        sink += r.item_id + r.ash;
    }
    const auto end = std::chrono::steady_clock::now();
    const double ns = std::chrono::duration<double, std::nano>(end - start).count() / draws;
    std::printf("bench: %d rolls, %.1f ns/roll (sink=%llu)\n", draws, ns,
                static_cast<unsigned long long>(sink));
    return 0;
}

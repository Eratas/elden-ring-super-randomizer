// test_variants.cpp - host-side tests for the loot-variants roll, no game required.
//
// The DLL cannot be exercised headlessly (it patches a running Elden Ring), so everything that is
// *decided* rather than *wired* lives in variant_logic.h and is tested here: the manifest parser and
// the per-pickup reroll, including the tier arithmetic that has to match loot.py's _tier_range().
//
// Build and run: build.ps1 (MinGW g++).  Exit code 0 = every check passed.

#include "variant_logic.h"

#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>

namespace {

int g_failures = 0;

#define CHECK(cond)                                                                    \
    do {                                                                               \
        if (!(cond)) {                                                                 \
            std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);                \
            ++g_failures;                                                              \
        }                                                                              \
    } while (0)

#define CHECK_EQ(actual, expected)                                                     \
    do {                                                                               \
        const long long a_ = static_cast<long long>(actual);                           \
        const long long e_ = static_cast<long long>(expected);                         \
        if (a_ != e_) {                                                                \
            std::printf("FAIL %s:%d: %s == %s (%lld vs %lld)\n", __FILE__, __LINE__,   \
                        #actual, #expected, a_, e_);                                   \
            ++g_failures;                                                              \
        }                                                                              \
    } while (0)

const char* kManifest =
    "MADLOVE-LOOT-VARIANTS 1\n"
    "# a comment line\n"
    "defaults 40 legendary 1 1\n"
    "weapon 1000000 25 8191 0 0 0 0 0 0 0 0 0 0 0 0 0\n"
    "weapon 1010000 10 1 3 - - - - - - - - - - - -\n"
    "weapon 1020000 0 5 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1 -1\n"
    "gems 0 10000 10100 10200\n"
    "gems 3 20000\n";

void test_parser() {
    loot_variants::Manifest m;
    std::string error;
    CHECK(loot_variants::parse_manifest(kManifest, m, error));
    CHECK(error.empty());
    CHECK_EQ(m.bad_lines, 0);
    CHECK_EQ(m.weapons.size(), 3);
    CHECK_EQ(m.gems.size(), 2);
    CHECK_EQ(m.gems[0].size(), 3);
    CHECK_EQ(m.gems[3].size(), 1);

    CHECK_EQ(m.defaults.ash_chance, 40);
    CHECK_EQ(m.defaults.level_curve, loot_variants::kCurveLegendary);
    CHECK(m.defaults.reroll_affinity);
    CHECK(m.defaults.reroll_level);

    const loot_variants::Weapon& standard = m.weapons[1000000];
    CHECK_EQ(standard.max_level, 25);
    CHECK_EQ(standard.affinity_mask, 8191);
    CHECK_EQ(standard.gem_class[0], 0);
    CHECK_EQ(standard.gem_class[12], 0);

    const loot_variants::Weapon& somber = m.weapons[1010000];
    CHECK_EQ(somber.max_level, 10);
    CHECK_EQ(somber.affinity_mask, 1);
    CHECK_EQ(somber.gem_class[0], 3);
    CHECK_EQ(somber.gem_class[1], -1);

    const loot_variants::Weapon& unique = m.weapons[1020000];
    CHECK_EQ(unique.max_level, 0);
    CHECK_EQ(unique.affinity_mask, 5);
    CHECK_EQ(unique.gem_class[0], -1);

    // A malformed record is counted and skipped, never fatal: the game must still start.
    loot_variants::Manifest partial;
    const std::string broken = std::string("MADLOVE-LOOT-VARIANTS 1\n") +
                               "weapon 1000000 25 8191 0 0 0\n" +
                               "weapon 1000000 25 8191 0 0 0 0 0 0 0 0 0 0 0 0 0\n" +
                               "nonsense 1 2 3\n";
    CHECK(loot_variants::parse_manifest(broken, partial, error));
    CHECK_EQ(partial.bad_lines, 2);
    CHECK_EQ(partial.weapons.size(), 1);

    loot_variants::Manifest rejected;
    CHECK(!loot_variants::parse_manifest("MADLOVE-LOOT-VARIANTS 2\n", rejected, error));
    CHECK(!error.empty());
    CHECK(!loot_variants::parse_manifest("weapon 1 2 3\n", rejected, error));
    CHECK(!error.empty());
    // No weapons at all is not a usable manifest.
    CHECK(!loot_variants::parse_manifest("MADLOVE-LOOT-VARIANTS 1\n", rejected, error));
}

void test_bind_and_tokens() {
    const std::uint8_t bytes[] = {'a', 'b', 'c'};
    const std::uint64_t hash = loot_variants::fnv1a64(bytes, sizeof(bytes));
    char bind_line[80] = {};
    std::snprintf(bind_line, sizeof(bind_line), "bind 3 %016llx",
                  static_cast<unsigned long long>(hash));
    const std::string text = std::string("MADLOVE-LOOT-VARIANTS 1\n") + bind_line + "\n" +
                             "defaults 50 common 1 1\n" +
                             "weapon 1000000 25 1 0 - - - - - - - - - - - -\n" +
                             "gems 0 10000\n";
    loot_variants::Manifest m;
    std::string error;
    CHECK(loot_variants::parse_manifest(text, m, error));
    CHECK(m.has_bind);
    CHECK_EQ(m.bind_size, 3);
    CHECK_EQ(m.bind_hash, hash);
    CHECK(loot_variants::verify_bind(m, bytes, sizeof(bytes)));
    CHECK(!loot_variants::verify_bind(m, bytes, 2));
    const std::uint8_t changed[] = {'a', 'b', 'd'};
    CHECK(!loot_variants::verify_bind(m, changed, sizeof(changed)));

    loot_variants::Manifest unbound;
    CHECK(loot_variants::parse_manifest(
        "MADLOVE-LOOT-VARIANTS 1\nweapon 1000000 25 1 0 - - - - - - - - - - - -\n", unbound, error));
    CHECK(!unbound.has_bind);
    CHECK(loot_variants::verify_bind(unbound, nullptr, 0));   // older manifests still work

    // strtoul saturation on Windows used to turn both of these into 0xFFFFFFFF, which looks like
    // kNoAsh and silently drops the Ash.  On any platform they are malformed and must be rejected.
    const std::string bad = std::string("MADLOVE-LOOT-VARIANTS 1\n") +
                            "weapon 1000000 25 1 0 - - - - - - - - - - - -\n" +
                            "gems 0 99999999999999 -1\n";
    loot_variants::Manifest tokens;
    CHECK(loot_variants::parse_manifest(bad, tokens, error));
    CHECK_EQ(tokens.bad_lines, 2);
    CHECK(tokens.gems[0].empty());
}

void test_armor() {
    const std::string text =
        "MADLOVE-LOOT-VARIANTS 2\n"
        "weapon 1000000 25 1 0 - - - - - - - - - - - -\n"
        "armor 40000 10\n"
        "armor 50000 0\n"
        "armor 20000000 10\n";          // > 0x00FFFFFF: malformed, must be rejected
    loot_variants::Manifest m;
    std::string error;
    CHECK(loot_variants::parse_manifest(text, m, error));
    CHECK_EQ(m.bad_lines, 1);
    CHECK_EQ(m.armor.size(), 2);

    loot_variants::Options options;
    options.level_curve = loot_variants::kCurveEven;
    loot_variants::Rng rng(4242);
    bool seen[11] = {};
    for (int i = 0; i < 2000; ++i) {
        const loot_variants::Rolled rolled = loot_variants::roll_item(
            loot_variants::kArmorBit | 40000, m, options, rng);
        CHECK((rolled.item_id & loot_variants::kArmorBit) != 0);
        CHECK_EQ(rolled.item_id & loot_variants::kArmorIdMask, 40000);
        const std::uint32_t level = (rolled.item_id >> 24) & 0x0F;
        CHECK(level <= 10);
        CHECK_EQ(rolled.ash, loot_variants::kNoAsh);
        seen[level] = true;
    }
    for (int level = 0; level <= 10; ++level) {
        CHECK(seen[level]);
    }

    // An incoming +N armour id keeps its piece; the level is replaced, never added to.
    const loot_variants::Rolled from_upgraded = loot_variants::roll_item(
        loot_variants::kArmorBit | (7u << 24) | 40000, m, options, rng);
    CHECK_EQ(from_upgraded.item_id & loot_variants::kArmorIdMask, 40000);
    CHECK(((from_upgraded.item_id >> 24) & 0x0F) <= 10);

    // A piece that cannot be reinforced keeps its exact id, as does an unknown base.
    CHECK_EQ(loot_variants::roll_item(loot_variants::kArmorBit | 50000, m, options, rng).item_id,
             loot_variants::kArmorBit | 50000u);
    CHECK_EQ(loot_variants::roll_item(loot_variants::kArmorBit | 99999, m, options, rng).item_id,
             loot_variants::kArmorBit | 99999u);
    // Weapons, goods and accessory categories are untouched by the armour branch.
    CHECK_EQ(loot_variants::roll_item(3000005, m, options, rng).item_id, 3000005);
    CHECK_EQ(loot_variants::roll_item(0x40000000u | 10000, m, options, rng).item_id,
             0x40000000u | 10000u);

    // ini opt-out.
    loot_variants::Options off = options;
    off.reroll_armor = false;
    CHECK_EQ(loot_variants::roll_item(loot_variants::kArmorBit | 40000, m, off, rng).item_id,
             loot_variants::kArmorBit | 40000u);

    // A v1 manifest has no armour lines: an old manifest cannot reroll armour.
    loot_variants::Manifest old;
    CHECK(loot_variants::parse_manifest(
        "MADLOVE-LOOT-VARIANTS 1\nweapon 1000000 25 1 0 - - - - - - - - - - - -\n", old, error));
    CHECK(old.armor.empty());
    CHECK_EQ(loot_variants::roll_item(loot_variants::kArmorBit | 40000, old, options, rng).item_id,
             loot_variants::kArmorBit | 40000u);
}

void test_tiers() {
    using namespace loot_variants::detail;
    std::uint32_t lo = 0;
    std::uint32_t hi = 0;

    // loot.py's _tier_range(), common curve, +25 weapon: 0-2, 3-8, 9-14, 15-19, 20-25.
    const std::uint32_t expect25[5][2] = {{0, 2}, {3, 8}, {9, 14}, {15, 19}, {20, 25}};
    for (std::size_t t = 0; t < 5; ++t) {
        tier_range(loot_variants::kCurveCommon, t, 25, lo, hi);
        CHECK_EQ(lo, expect25[t][0]);
        CHECK_EQ(hi, expect25[t][1]);
    }
    // Somber +10: 0-1, 2-3, 4-5, 6-7, 8-10.
    const std::uint32_t expect10[5][2] = {{0, 1}, {2, 3}, {4, 5}, {6, 7}, {8, 10}};
    for (std::size_t t = 0; t < 5; ++t) {
        tier_range(loot_variants::kCurveCommon, t, 10, lo, hi);
        CHECK_EQ(lo, expect10[t][0]);
        CHECK_EQ(hi, expect10[t][1]);
    }
    // Legendary +25: 0-2, 3-7, 8-13, 14-19, 20-25.
    const std::uint32_t expectLegendary[5][2] = {{0, 2}, {3, 7}, {8, 13}, {14, 19}, {20, 25}};
    for (std::size_t t = 0; t < 5; ++t) {
        tier_range(loot_variants::kCurveLegendary, t, 25, lo, hi);
        CHECK_EQ(lo, expectLegendary[t][0]);
        CHECK_EQ(hi, expectLegendary[t][1]);
    }
    // Even covers the whole range in one tier.
    tier_range(loot_variants::kCurveEven, 0, 25, lo, hi);
    CHECK_EQ(lo, 0);
    CHECK_EQ(hi, 25);

    // Every level up to the ceiling is reachable.  For tiny ceilings (top=1 or 2) a tier can be
    // empty and loot.py clamps it to one level, so tiers may overlap there; only coverage and the
    // ceiling matter, and the C++ has to match that quirk rather than "fix" it.
    for (std::uint32_t top = 1; top <= 25; ++top) {
        bool covered[26] = {};
        for (std::size_t t = 0; t < 5; ++t) {
            tier_range(loot_variants::kCurveCommon, t, top, lo, hi);
            CHECK(hi >= lo);
            CHECK(lo <= top);
            CHECK(hi <= top);
            for (std::uint32_t level = lo; level <= hi; ++level) {
                covered[level] = true;
            }
        }
        for (std::uint32_t level = 0; level <= top; ++level) {
            CHECK(covered[level]);
        }
    }

    // Tier selection boundaries: 55% / 28% / 12% / 4% / 1%.
    CHECK_EQ(tier_index(loot_variants::kCurveCommon, 0), 0);
    CHECK_EQ(tier_index(loot_variants::kCurveCommon, 5499), 0);
    CHECK_EQ(tier_index(loot_variants::kCurveCommon, 5500), 1);
    CHECK_EQ(tier_index(loot_variants::kCurveCommon, 8299), 1);
    CHECK_EQ(tier_index(loot_variants::kCurveCommon, 8300), 2);
    CHECK_EQ(tier_index(loot_variants::kCurveCommon, 9499), 2);
    CHECK_EQ(tier_index(loot_variants::kCurveCommon, 9500), 3);
    CHECK_EQ(tier_index(loot_variants::kCurveCommon, 9899), 3);
    CHECK_EQ(tier_index(loot_variants::kCurveCommon, 9900), 4);
    CHECK_EQ(tier_index(loot_variants::kCurveCommon, 9999), 4);
}

void test_roll() {
    loot_variants::Manifest m;
    std::string error;
    CHECK(loot_variants::parse_manifest(kManifest, m, error));

    loot_variants::Options options;
    options.reroll_affinity = true;
    options.reroll_level = true;
    options.ash_chance = 100;
    options.level_curve = loot_variants::kCurveEven;

    loot_variants::Rng rng(12345);
    bool seen_affinity[loot_variants::kAffinities] = {};
    bool seen_level[26] = {};
    bool seen_gem[3] = {};
    std::uint64_t total = 0;
    std::uint64_t ash_count = 0;
    for (int i = 0; i < 5000; ++i) {
        const loot_variants::Rolled rolled = loot_variants::roll_item(1000000, m, options, rng);
        CHECK_EQ(rolled.item_id / 10000, 100);              // same weapon
        const std::uint32_t affinity = (rolled.item_id % 10000) / 100;
        const std::uint32_t level = rolled.item_id % 100;
        CHECK(affinity < loot_variants::kAffinities);
        CHECK(((m.weapons[1000000].affinity_mask >> affinity) & 1u) != 0);
        CHECK(level <= 25);
        seen_affinity[affinity] = true;
        seen_level[level] = true;
        if (rolled.ash != loot_variants::kNoAsh) {
            CHECK((rolled.ash & loot_variants::kAshFlag) != 0);
            const std::uint32_t gem = rolled.ash & ~loot_variants::kAshFlag;
            if (gem == 10000) {
                seen_gem[0] = true;
            } else if (gem == 10100) {
                seen_gem[1] = true;
            } else if (gem == 10200) {
                seen_gem[2] = true;
            } else {
                CHECK(false);                                 // an id that is not in the pool
            }
        }
        total += level;
        ash_count += rolled.ash == loot_variants::kNoAsh ? 0 : 1;
    }
    for (std::uint32_t a = 0; a < loot_variants::kAffinities; ++a) {
        CHECK(seen_affinity[a]);
    }
    for (std::uint32_t level = 0; level <= 25; ++level) {
        CHECK(seen_level[level]);
    }
    CHECK(seen_gem[0] && seen_gem[1] && seen_gem[2]);
    CHECK_EQ(ash_count, 5000);                               // ash chance 100%
    const double mean = static_cast<double>(total) / 5000.0;
    CHECK(mean > 11.5 && mean < 13.5);                       // even curve over 0..25 = 12.5

    // A weapon with two affinities, no upgrades and no Ash only changes affinity.
    for (int i = 0; i < 200; ++i) {
        const loot_variants::Rolled rolled = loot_variants::roll_item(1020000, m, options, rng);
        const std::uint32_t low = rolled.item_id % 10000;
        CHECK(low == 0 || low == 200);
        CHECK_EQ(rolled.item_id % 100, 0);
        CHECK_EQ(rolled.ash, loot_variants::kNoAsh);
    }

    // A malformed id at an affinity the single-row weapon does not have is brought back to its row.
    const loot_variants::Rolled clamped = loot_variants::roll_item(1010000 + 700, m, options, rng);
    CHECK_EQ(clamped.item_id - clamped.item_id % 10000, 1010000);

    // Unknown weapon, an affinity the game does not use, and a non-weapon id: untouched.
    CHECK_EQ(loot_variants::roll_item(9000000, m, options, rng).item_id, 9000000);
    CHECK_EQ(loot_variants::roll_item(1001300, m, options, rng).item_id, 1001300);
    CHECK_EQ(loot_variants::roll_item(0x40000000u, m, options, rng).item_id, 0x40000000u);

    // Affinity and level off: the id is kept, but a level above the weapon's ceiling is clamped.
    loot_variants::Options fixed;
    fixed.reroll_affinity = false;
    fixed.reroll_level = false;
    fixed.ash_chance = 0;
    CHECK_EQ(loot_variants::roll_item(1010000, m, fixed, rng).item_id, 1010000);
    CHECK_EQ(loot_variants::roll_item(1010000 + 25, m, fixed, rng).item_id, 1010010);
    CHECK_EQ(loot_variants::roll_item(1010000 + 7, m, fixed, rng).item_id, 1010007);

    // Ash chance 0 means the field is never touched, even on a row with a pool.
    loot_variants::Options no_ash = options;
    no_ash.ash_chance = 0;
    for (int i = 0; i < 200; ++i) {
        CHECK_EQ(loot_variants::roll_item(1000000, m, no_ash, rng).ash, loot_variants::kNoAsh);
    }

    // The common curve is top heavy: at most 2% of draws at +20 or better, most at +0..+2.
    loot_variants::Options common = options;
    common.level_curve = loot_variants::kCurveCommon;
    std::uint32_t low = 0;
    std::uint32_t high = 0;
    const int draws = 20000;
    for (int i = 0; i < draws; ++i) {
        const std::uint32_t level = loot_variants::roll_item(1000000, m, common, rng).item_id % 100;
        low += level <= 2 ? 1 : 0;
        high += level >= 20 ? 1 : 0;
    }
    const double low_share = static_cast<double>(low) / draws;
    const double high_share = static_cast<double>(high) / draws;
    CHECK(low_share > 0.52 && low_share < 0.58);
    CHECK(high_share > 0.005 && high_share < 0.02);
}

// With a path argument, validate a manifest the randomizer actually wrote instead of the small
// synthetic one above, and roll every one of its weapons.  This is the closest thing to an in-game
// check available without launching Elden Ring: `test_variants.exe loot_variants.txt`.
void test_real_manifest(const char* path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) {
        std::printf("FAIL cannot open %s\n", path);
        ++g_failures;
        return;
    }
    const std::string text((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    loot_variants::Manifest m;
    std::string error;
    if (!loot_variants::parse_manifest(text, m, error)) {
        std::printf("FAIL %s: %s\n", path, error.c_str());
        ++g_failures;
        return;
    }
    CHECK_EQ(m.bad_lines, 0);
    CHECK(m.weapons.size() > 100);
    CHECK(m.armor.size() > 100);
    std::printf("manifest: %zu weapons, %zu armour, %zu ash pools, ash %d%%, curve %d, bind=%d\n",
                m.weapons.size(), m.armor.size(),
                m.gems.size(), m.defaults.ash_chance, m.defaults.level_curve, m.has_bind ? 1 : 0);
    // The randomizer writes both files together; check the fingerprint against that regulation.
    // Derive the sibling path without <filesystem> so the test stays a single-header console program.
    const std::string p(path);
    const std::string::size_type slash = p.find_last_of("\\/");
    const std::string regulation_path =
        (slash == std::string::npos ? std::string() : p.substr(0, slash + 1)) + "regulation.bin";
    std::ifstream regulation(regulation_path, std::ios::binary);
    if (m.has_bind && regulation) {
        const std::string bytes((std::istreambuf_iterator<char>(regulation)),
                                std::istreambuf_iterator<char>());
        CHECK(loot_variants::verify_bind(m, reinterpret_cast<const std::uint8_t*>(bytes.data()),
                                         bytes.size()));
    }

    loot_variants::Options options = m.defaults;
    options.ash_chance = 100;                     // exercise every pool
    loot_variants::Rng rng(987654321);
    for (const auto& pair : m.weapons) {
        const loot_variants::Weapon& w = pair.second;
        CHECK((w.affinity_mask >> loot_variants::kAffinities) == 0);
        CHECK(w.max_level <= loot_variants::kMaxLevel);
        for (int i = 0; i < 40; ++i) {
            const std::uint32_t from = w.base + (i % 13) * 100;
            const loot_variants::Rolled rolled = loot_variants::roll_item(from, m, options, rng);
            CHECK(rolled.item_id - rolled.item_id % 10000 == w.base);
            const std::uint32_t affinity = (rolled.item_id % 10000) / 100;
            const std::uint32_t level = rolled.item_id % 100;
            CHECK(((w.affinity_mask >> affinity) & 1u) != 0);
            CHECK(level <= w.max_level);
            if (rolled.ash != loot_variants::kNoAsh) {
                const std::uint32_t gem = rolled.ash & ~loot_variants::kAshFlag;
                bool in_pool = false;
                const auto pool = m.gems.find(w.gem_class[affinity]);
                if (pool != m.gems.end()) {
                    for (std::uint32_t candidate : pool->second) {
                        in_pool = in_pool || candidate == gem;
                    }
                }
                CHECK(in_pool);
            }
        }
    }
}

}  // namespace

int main(int argc, char** argv) {
    if (argc > 1) {
        test_real_manifest(argv[1]);
    } else {
        test_parser();
        test_bind_and_tokens();
        test_armor();
        test_tiers();
        test_roll();
    }
    if (g_failures == 0) {
        std::printf("variant_logic: all checks passed\n");
        return 0;
    }
    std::printf("variant_logic: %d check(s) failed\n", g_failures);
    return 1;
}

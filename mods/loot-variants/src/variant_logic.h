// variant_logic.h - the part of the loot-variants mod that has no Windows in it.
//
// A manifest written by the randomizer's --loot-variants pass says, per weapon base, which affinity
// rows exist, the weapon's own upgrade ceiling and, per affinity, which pool of Ashes of War may be
// mounted.  This header parses that file and turns one granted item id into a rerolled one.
//
// Kept free of <windows.h> and of any global state on purpose: test_variants.cpp compiles this
// header into a console program, so the parse and the roll are tested on the host instead of by
// launching the game.
#pragma once

#include <cerrno>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <climits>
#include <map>
#include <string>
#include <vector>

namespace loot_variants {

constexpr std::uint32_t kNoAsh = 0xFFFFFFFFu;      // "no Ash mounted": the field's own empty value
constexpr std::uint32_t kAshFlag = 0x80000000u;    // the game's "this item has an Ash" bit
constexpr std::uint32_t kAffinities = 13;          // Standard, Heavy .. Occult
constexpr std::uint32_t kMaxLevel = 25;
constexpr int kCurveEven = 0;
constexpr int kCurveCommon = 1;
constexpr int kCurveLegendary = 2;

struct Weapon {
    std::uint32_t base = 0;
    std::uint32_t max_level = 0;
    std::uint32_t affinity_mask = 0;
    int gem_class[kAffinities] = {-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1};
};

// The knobs of one roll.  The manifest's `defaults` line fills these so a run keeps the curve the
// static tool used; the ini next to the DLL overrides any of them.
struct Options {
    bool reroll_affinity = true;
    bool reroll_level = true;
    int ash_chance = 50;          // percent
    int level_curve = kCurveCommon;
};

struct Manifest {
    std::map<std::uint32_t, Weapon> weapons;
    std::map<int, std::vector<std::uint32_t>> gems;
    Options defaults;
    bool has_bind = false;             // an old manifest has no bind line: warn, but still usable
    std::uint32_t bind_size = 0;
    std::uint64_t bind_hash = 0;
    std::size_t bad_lines = 0;
};

// xorshift64*: tiny, deterministic and identical in the DLL and the test.  Not cryptographic; it
// only decides which of a weapon's own variants a pickup shows.
struct Rng {
    std::uint64_t state = 0x9E3779B97F4A7C15ull;

    explicit Rng(std::uint64_t seed = 0x9E3779B97F4A7C15ull) : state(seed ? seed : 1) {}

    std::uint32_t next() {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        return static_cast<std::uint32_t>(state >> 32);
    }

    std::uint32_t below(std::uint32_t n) { return n ? next() % n : 0; }
};

struct Rolled {
    std::uint32_t item_id = 0;
    std::uint32_t ash = kNoAsh;     // kNoAsh = leave the item's Ash field alone
};

// --------------------------------------------------------------------------- parsing
namespace detail {

// On Windows `unsigned long` is 32 bits, so strtoul silently saturates on overflow and accepts a
// leading '-'.  strtoull into a 64-bit value with ERANGE checked makes the test host and the DLL
// agree: an oversized token is rejected, never turned into 0xFFFFFFFF (which would look like kNoAsh).
inline bool to_u32(const std::string& token, std::uint32_t& out) {
    if (token.empty() || token[0] == '-') {
        return false;
    }
    errno = 0;
    char* end = nullptr;
    const unsigned long long value = std::strtoull(token.c_str(), &end, 10);
    if (errno == ERANGE || end == token.c_str() || *end != '\0' || value > 0xFFFFFFFFull) {
        return false;
    }
    out = static_cast<std::uint32_t>(value);
    return true;
}

inline bool to_int(const std::string& token, int& out) {
    if (token.empty()) {
        return false;
    }
    errno = 0;
    char* end = nullptr;
    const long value = std::strtol(token.c_str(), &end, 10);
    if (errno == ERANGE || end == token.c_str() || *end != '\0' || value < INT_MIN || value > INT_MAX) {
        return false;
    }
    out = static_cast<int>(value);
    return true;
}

inline bool is_hex16(const std::string& token) {
    if (token.size() != 16) {
        return false;
    }
    for (char ch : token) {
        const bool digit = ch >= '0' && ch <= '9';
        const bool lower = ch >= 'a' && ch <= 'f';
        const bool upper = ch >= 'A' && ch <= 'F';
        if (!digit && !lower && !upper) {
            return false;
        }
    }
    return true;
}

inline std::vector<std::string> split(const std::string& line) {
    std::vector<std::string> out;
    std::size_t i = 0;
    while (i < line.size()) {
        while (i < line.size() && (line[i] == ' ' || line[i] == '\t')) {
            ++i;
        }
        const std::size_t start = i;
        while (i < line.size() && line[i] != ' ' && line[i] != '\t') {
            ++i;
        }
        if (i > start) {
            out.push_back(line.substr(start, i - start));
        }
    }
    return out;
}

}  // namespace detail

// Parse the manifest text.  A malformed line is counted and skipped: a manifest from a newer tool
// must never stop the game from starting, and the log says how many lines were not understood.
inline bool parse_manifest(const std::string& text, Manifest& out, std::string& error) {
    bool saw_header = false;
    std::size_t line_no = 0;
    std::size_t i = 0;
    while (i <= text.size()) {
        const std::size_t end = text.find('\n', i);
        std::string line = text.substr(i, end == std::string::npos ? std::string::npos : end - i);
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        ++line_no;
        i = (end == std::string::npos) ? text.size() + 1 : end + 1;

        const std::vector<std::string> tok = detail::split(line);
        if (tok.empty() || tok[0].rfind("#", 0) == 0) {
            continue;
        }
        if (tok[0] == "MADLOVE-LOOT-VARIANTS") {
            std::uint32_t version = 0;
            if (tok.size() < 2 || !detail::to_u32(tok[1], version) || version != 1) {
                error = "unsupported manifest version on line " + std::to_string(line_no);
                return false;
            }
            saw_header = true;
            continue;
        }
        if (tok[0] == "bind") {
            // bind <regulation size> <16 hex digits of FNV-1a>: a stale manifest must not be used
            if (tok.size() != 3 || !detail::to_u32(tok[1], out.bind_size) ||
                !detail::is_hex16(tok[2])) {
                ++out.bad_lines;
                continue;
            }
            errno = 0;
            char* end = nullptr;
            out.bind_hash = std::strtoull(tok[2].c_str(), &end, 16);
            if (errno == ERANGE || end != tok[2].c_str() + tok[2].size()) {
                ++out.bad_lines;
                continue;
            }
            out.has_bind = true;
            continue;
        }
        if (tok[0] == "defaults") {
            // defaults <ash chance %> <level curve> <reroll affinity 0|1> <reroll level 0|1>
            int ash = 0;
            int affinity = 0;
            int level = 0;
            if (tok.size() != 5 || !detail::to_int(tok[1], ash) || !detail::to_int(tok[3], affinity) ||
                !detail::to_int(tok[4], level)) {
                ++out.bad_lines;
                continue;
            }
            out.defaults.ash_chance = ash < 0 ? 0 : (ash > 100 ? 100 : ash);
            out.defaults.reroll_affinity = affinity != 0;
            out.defaults.reroll_level = level != 0;
            out.defaults.level_curve = tok[2] == "even" ? kCurveEven
                                      : tok[2] == "legendary" ? kCurveLegendary
                                                              : kCurveCommon;
            continue;
        }
        if (tok[0] == "weapon") {
            Weapon w;
            if (tok.size() != 4 + kAffinities || !detail::to_u32(tok[1], w.base) ||
                !detail::to_u32(tok[2], w.max_level) || !detail::to_u32(tok[3], w.affinity_mask) ||
                w.max_level > kMaxLevel || w.affinity_mask == 0 || (w.affinity_mask >> kAffinities) != 0) {
                ++out.bad_lines;
                continue;
            }
            bool ok = true;
            for (std::uint32_t a = 0; a < kAffinities && ok; ++a) {
                if (tok[4 + a] == "-") {
                    w.gem_class[a] = -1;
                } else {
                    ok = detail::to_int(tok[4 + a], w.gem_class[a]);
                }
            }
            if (!ok) {
                ++out.bad_lines;
                continue;
            }
            out.weapons[w.base] = w;
            continue;
        }
        if (tok[0] == "gems") {
            int cls = 0;
            if (tok.size() < 2 || !detail::to_int(tok[1], cls)) {
                ++out.bad_lines;
                continue;
            }
            std::vector<std::uint32_t>& ids = out.gems[cls];
            for (std::size_t t = 2; t < tok.size(); ++t) {
                std::uint32_t id = 0;
                if (detail::to_u32(tok[t], id)) {
                    ids.push_back(id);
                } else {
                    ++out.bad_lines;              // a bad gem id must show up in the log
                }
            }
            continue;
        }
        ++out.bad_lines;
    }
    if (!saw_header) {
        error = "not a loot-variants manifest (missing header line)";
        return false;
    }
    if (out.weapons.empty()) {
        error = "the manifest lists no weapons";
        return false;
    }
    return true;
}

// --------------------------------------------------------------------- regulation binding
inline std::uint64_t fnv1a64(const std::uint8_t* data, std::size_t size) {
    std::uint64_t hash = 0xCBF29CE484222325ull;
    for (std::size_t i = 0; i < size; ++i) {
        hash = (hash ^ static_cast<std::uint64_t>(data[i])) * 0x100000001B3ull;
    }
    return hash;
}

// A manifest from another run can describe affinity rows the current regulation does not have.
// `has_bind == false` means an older tool wrote the manifest; the caller logs a warning and proceeds.
inline bool verify_bind(const Manifest& manifest, const std::uint8_t* data, std::size_t size) {
    if (!manifest.has_bind) {
        return true;
    }
    return manifest.bind_size == size && manifest.bind_hash == fnv1a64(data, size);
}

// --------------------------------------------------------------------------- the roll
namespace detail {

// loot.py's TIERS: frac_lo, frac_hi, weight in ten-thousandths.  Half-open [lo, hi), the top tier
// includes the ceiling.
struct Tier {
    double lo;
    double hi;
    std::uint32_t weight;
};

inline const Tier* tier_table(int curve, std::size_t& count) {
    static const Tier kEven[] = {{0.0, 1.0, 10000}};
    static const Tier kCommon[] = {{0.00, 0.12, 5500}, {0.12, 0.36, 2800}, {0.36, 0.60, 1200},
                                   {0.60, 0.80, 400}, {0.80, 1.00, 100}};
    static const Tier kLegendary[] = {{0.00, 0.10, 7000}, {0.10, 0.32, 2000}, {0.32, 0.56, 700},
                                      {0.56, 0.80, 250}, {0.80, 1.00, 50}};
    if (curve == kCurveEven) {
        count = 1;
        return kEven;
    }
    if (curve == kCurveLegendary) {
        count = sizeof(kLegendary) / sizeof(kLegendary[0]);
        return kLegendary;
    }
    count = sizeof(kCommon) / sizeof(kCommon[0]);
    return kCommon;
}

// Which tier a draw of `roll` (0..9999) lands in.
inline std::size_t tier_index(int curve, std::uint32_t roll) {
    std::size_t count = 0;
    const Tier* tiers = tier_table(curve, count);
    std::uint32_t upto = 0;
    for (std::size_t t = 0; t < count; ++t) {
        upto += tiers[t].weight;
        if (roll < upto) {
            return t;
        }
    }
    return count - 1;
}

// Inclusive [lo, hi] of one tier at a given ceiling: ceil(frac * top - eps), the top tier includes
// `top`.  The same arithmetic as Loot._tier_range() in loot.py.
inline void tier_range(int curve, std::size_t index, std::uint32_t top, std::uint32_t& lo,
                       std::uint32_t& hi) {
    std::size_t count = 0;
    const Tier* tiers = tier_table(curve, count);
    const Tier& chosen = tiers[index < count ? index : count - 1];
    const double eps = 1e-9;
    lo = static_cast<std::uint32_t>(std::ceil(chosen.lo * static_cast<double>(top) - eps));
    hi = (chosen.hi >= 1.0)
             ? top
             : static_cast<std::uint32_t>(std::ceil(chosen.hi * static_cast<double>(top) - eps)) - 1;
    if (hi < lo) {
        hi = lo;
    }
    if (hi > top) {
        hi = top;
    }
}

inline std::uint32_t roll_level(std::uint32_t top, int curve, Rng& rng) {
    if (top == 0) {
        return 0;
    }
    std::uint32_t lo = 0;
    std::uint32_t hi = 0;
    tier_range(curve, tier_index(curve, rng.below(10000)), top, lo, hi);
    return lo + rng.below(hi - lo + 1);
}

inline std::uint32_t popcount(std::uint32_t v) {
    std::uint32_t n = 0;
    while (v) {
        v &= v - 1;
        ++n;
    }
    return n;
}

}  // namespace detail

// One granted item -> the id it becomes.  Leaves the id alone when the weapon has nothing to roll
// (one affinity, no upgrades, no Ash) or the id is outside the 0..12 affinity space the manifest
// describes.
inline Rolled roll_item(std::uint32_t item_id, const Manifest& manifest, const Options& options, Rng& rng) {
    Rolled out;
    out.item_id = item_id;
    const std::uint32_t base = item_id - item_id % 10000;
    const auto found = manifest.weapons.find(base);
    if (found == manifest.weapons.end()) {
        return out;
    }
    const Weapon& w = found->second;
    std::uint32_t affinity = (item_id % 10000) / 100;
    if (affinity >= kAffinities) {
        return out;                       // a cut row with an affinity the game does not use
    }
    if (options.reroll_affinity) {
        const std::uint32_t count = detail::popcount(w.affinity_mask);
        if (count == 1) {
            // A single-affinity weapon has one row: even a malformed incoming id with another
            // affinity must be brought back to a row that exists.
            for (std::uint32_t a = 0; a < kAffinities; ++a) {
                if ((w.affinity_mask >> a) & 1u) {
                    affinity = a;
                    break;
                }
            }
        } else if (count > 1) {
            std::uint32_t pick = rng.below(count);
            for (std::uint32_t a = 0; a < kAffinities; ++a) {
                if ((w.affinity_mask >> a) & 1u) {
                    if (pick == 0) {
                        affinity = a;
                        break;
                    }
                    --pick;
                }
            }
        }
    }
    std::uint32_t level = item_id % 100;
    if (options.reroll_level && w.max_level > 0) {
        level = detail::roll_level(w.max_level, options.level_curve, rng);
    } else if (level > w.max_level) {
        level = w.max_level;
    }
    out.item_id = base + affinity * 100 + level;

    const int cls = w.gem_class[affinity];
    if (cls >= 0 && options.ash_chance > 0 &&
        static_cast<int>(rng.below(100)) < options.ash_chance) {
        const auto pool = manifest.gems.find(cls);
        if (pool != manifest.gems.end() && !pool->second.empty()) {
            out.ash = kAshFlag | pool->second[rng.below(static_cast<std::uint32_t>(pool->second.size()))];
        }
    }
    return out;
}

}  // namespace loot_variants

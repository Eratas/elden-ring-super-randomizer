// manifest.h - the part of the shops-periodic mod that has no Windows in it.
//
// The static tool writes tools/shops.py::periodic_manifest(): a per-block list of sellable slot
// rows and the curated pool of each category.  This header parses that file and rolls new items
// for each slot; the Windows half (shops_periodic.cpp) uses it from the DLL.
//
// Kept free of <windows.h> and of global state on purpose: test_shops_periodic.cpp compiles this
// header into a console program, so the parse and the roll are tested on the host.
#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <utility>
#include <vector>

namespace shops_periodic {

struct Manifest {
    std::uint64_t bind = 0;                       // hash of the regulation this manifest was made for
    std::uint32_t every_minutes = 15;             // tick interval (ini can override)
    std::map<std::uint32_t, std::vector<std::uint32_t>> pools;   // category -> curated ids
    std::vector<std::vector<std::pair<std::uint32_t, std::uint32_t>>> shops;  // block -> [(slot id, cat)]

    bool valid() const { return !pools.empty() && !shops.empty(); }
    // Returns a random item id from the pool of `cat`, or 0 when the pool is empty (caller skips).
    template <typename Rng>
    std::uint32_t roll_item(std::uint32_t cat, Rng& rng) const {
        auto it = pools.find(cat);
        if (it == pools.end() || it->second.empty()) {
            return 0;
        }
        return it->second[static_cast<std::size_t>(rng()) % it->second.size()];
    }
    std::size_t shop_count() const { return shops.size(); }
};

// INI lookup on the whole file text: [section] headers, `key = value`, inline `;` / `#` comments.
// Kept here (not in the Windows half) so the host tests can verify `enabled = 0 ; ...` really means 0.
std::string ini_value(const std::string& text, const char* section, const char* key,
                      const std::string& fallback);

// Parse tools/shops.py::periodic_manifest output.  Returns false on the first malformed line and
// fills `error`.
bool load_manifest(const char* path, Manifest& out, std::string& error);

// Parse helpers (free for tests).
bool parse_bind(const char* line, std::uint64_t& out, std::string& error);
bool parse_pool(const char* line, std::uint32_t& cat, std::vector<std::uint32_t>& ids, std::string& error);
bool parse_shop(const char* line, std::size_t& idx, std::vector<std::pair<std::uint32_t, std::uint32_t>>& slots,
                std::string& error);

}  // namespace shops_periodic

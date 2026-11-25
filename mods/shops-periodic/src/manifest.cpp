// manifest.cpp - parses the periodic-shops manifest (tools/shops.py::periodic_manifest).
#include "manifest.h"

#include <cctype>
#include <cstdlib>
#include <fstream>
#include <sstream>

namespace shops_periodic {

namespace {

bool parse_u32(std::string_view tok, std::uint32_t& out) {
    if (tok.empty()) {
        return false;
    }
    for (char c : tok) {
        if (!std::isdigit(static_cast<unsigned char>(c))) {
            return false;
        }
    }
    out = static_cast<std::uint32_t>(std::strtoul(std::string(tok).c_str(), nullptr, 10));
    return true;
}

// Reads the next whitespace-separated token.
bool next_tok(std::istringstream& ss, std::string& tok) {
    if (!(ss >> tok)) {
        return false;
    }
    return true;
}

}  // namespace

bool parse_bind(const char* line, std::uint64_t& out, std::string& error) {
    std::istringstream ss(line);
    std::string kind, size_tok, hex;
    ss >> kind >> size_tok >> hex;
    if (kind != "bind" || size_tok.empty() || hex.empty()) {
        error = "expected: bind <size> <hex>";
        return false;
    }
    out = std::strtoull(hex.c_str(), nullptr, 16);
    return true;
}

bool parse_pool(const char* line, std::uint32_t& cat, std::vector<std::uint32_t>& ids, std::string& error) {
    std::istringstream ss(line);
    std::string kind;
    ss >> kind;
    if (kind != "pool") {
        error = "expected: pool <cat> <id>...";
        return false;
    }
    std::string cat_tok;
    if (!next_tok(ss, cat_tok) || !parse_u32(cat_tok, cat)) {
        error = "pool line has no category";
        return false;
    }
    std::uint32_t id;
    while (ss >> id) {
        ids.push_back(id);
    }
    if (ids.empty()) {
        error = "pool has no item ids";
        return false;
    }
    return true;
}

bool parse_shop(const char* line, std::size_t& idx,
                std::vector<std::pair<std::uint32_t, std::uint32_t>>& slots, std::string& error) {
    std::istringstream ss(line);
    std::string kind;
    ss >> kind;
    if (kind != "shop") {
        error = "expected: shop <idx> <id> <cat>...";
        return false;
    }
    std::string idx_tok;
    std::uint32_t idx32 = 0;
    if (!next_tok(ss, idx_tok) || !parse_u32(idx_tok, idx32)) {
        error = "shop line has no block index";
        return false;
    }
    idx = idx32;
    std::uint32_t id, cat;
    while (ss >> id) {
        if (!(ss >> cat)) {
            error = "shop line: a slot id has no following category";
            return false;
        }
        slots.emplace_back(id, cat);
    }
    return true;
}

bool load_manifest(const char* path, Manifest& out, std::string& error) {
    std::ifstream f(path);
    if (!f) {
        error = "cannot open manifest";
        return false;
    }
    std::string line;
    while (std::getline(f, line)) {
        std::istringstream ss(line);
        std::string first;
        ss >> first;
        if (first.empty() || first[0] == '#') {
            continue;
        }
        if (first == "bind") {
            std::string size_tok, hex;
            ss >> size_tok >> hex;
            out.bind = std::strtoull(hex.c_str(), nullptr, 16);
        } else if (first == "every") {
            std::string tok;
            if (!next_tok(ss, tok) || !parse_u32(tok, out.every_minutes)) {
                error = "every line has no minutes";
                return false;
            }
        } else if (first == "pool") {
            std::uint32_t cat;
            std::vector<std::uint32_t> ids;
            if (!parse_pool(line.c_str(), cat, ids, error)) {
                return false;
            }
            out.pools[cat] = std::move(ids);
        } else if (first == "shop") {
            std::size_t idx;
            std::vector<std::pair<std::uint32_t, std::uint32_t>> slots;
            if (!parse_shop(line.c_str(), idx, slots, error)) {
                return false;
            }
            if (idx >= out.shops.size()) {
                out.shops.resize(idx + 1);
            }
            out.shops[idx] = std::move(slots);
        }
    }
    return out.valid();
}

}  // namespace shops_periodic

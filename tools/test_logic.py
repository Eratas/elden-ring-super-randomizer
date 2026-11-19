"""Logic tests for the randomizer's pure helpers and binary core.

Everything here runs with no regulation.bin, no game install and no oo2core DLL, so it belongs in the
per-commit gate (tools/gate.py).  It pins the behaviour that, if it regressed, would produce *silently
wrong output in the field* rather than a crash:

  * derangement(n) terminates for every n (n < 2 used to loop forever) and is a fixed-point-free
    permutation for n >= 2 - both randomize.py and spells.py;
  * round_price / cap_total / new_prices (shuffle) - the shared price/quantity maths and the
    conservation invariant "a shuffle is a permutation, so no id is lost or duplicated";
  * the keep_sets armour coherence invariant in dropshuffle (a set that maps to itself must stay a
    coherent set - the bug fixed in run 20261118);
  * the erreg binary round-trips: DCX (zstd + deflate), AES-256-CBC encrypt/decrypt, and a BND4
    decoded and rebuilt byte-for-byte from the shipped msg archive (no DLL needed - it is zstd);
  * erreg robustness: truncated / corrupt input to read_bnd4, Param and read_dcx fails as a clean
    ValueError (no raw struct.error / IndexError, and never the read_bnd4 name-scan hang).

The set-coherence block mirrors dropshuffle.shuffle()'s keep_sets branch; keep the two in sync.
Run directly with `python tools/test_logic.py` or through tools/gate.py.
"""
from __future__ import annotations

import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import boss_scale
import dropshuffle
import durations
import enemy_drops
import erreg
import flasks
import gear
import gems
import goods
import oodle
import randomize
import runes
import shops
import spells
import start_items
import talkmsg
import textarchives
import weapon_names
import weapons
import zones
from dropshuffle import _set_key

_CHECKS = 0
_FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    """Record one assertion; `msg` describes what broke (expected vs actual) when it fails."""
    global _CHECKS
    _CHECKS += 1
    if not cond:
        _FAILS.append(msg)


# --------------------------------------------------------------------------- derangement
def test_derangement() -> None:
    # n < 2 has no fixed-point-free permutation; the code must return the identity, not loop forever.
    check(randomize.derangement(0, random.Random(1)) == [], "derangement(0) should be []")
    check(randomize.derangement(1, random.Random(1)) == [0], "derangement(1) should be [0] (must not hang)")
    check(spells.derangement(1, random.Random(1)) == [0], "spells.derangement(1) should be [0]")
    # n >= 2: a real permutation of range(n) with no fixed point, across seeds.
    for n in (2, 3, 4, 5, 8, 13, 40, 200):
        for seed in range(25):
            perm = randomize.derangement(n, random.Random(seed))
            check(sorted(perm) == list(range(n)),
                  f"derangement({n}) is not a permutation (seed {seed}): {perm[:8]}...")
            check(all(i != p for i, p in enumerate(perm)),
                  f"derangement({n}) has a fixed point (seed {seed})")


# --------------------------------------------------------------------------- round_price
def test_round_price() -> None:
    cases = {0: 1, 1: 1, 5: 5, 9: 9, 50: 50, 99: 99, 100: 100, 999: 1000,
             1234: 1200, 12345: 12000, 999999: 1000000, 1000000: 1000000}
    for v, want in cases.items():
        got = randomize.round_price(v)
        check(got == want, f"round_price({v}) = {got}, want {want}")
    # never below 1, and monotonic non-decreasing across a range
    prev = 0
    for v in range(0, 1500):
        got = randomize.round_price(v)
        check(got >= 1, f"round_price({v}) = {got} < 1")
        check(got >= prev, f"round_price not monotonic at {v}: {got} < {prev}")
        prev = got


# --------------------------------------------------------------------------- cap_total
def test_cap_total() -> None:
    under = {"str": 10, "dex": 20}
    check(weapons.cap_total(under, 100) is under or weapons.cap_total(under, 100) == under,
          "cap_total should return the input unchanged when its sum is under the cap")
    req = {"str": 30, "dex": 30, "int": 30}
    out = weapons.cap_total(req, 60)
    check(sum(out.values()) <= 60, f"cap_total sum {sum(out.values())} exceeds cap 60")
    check(all(v >= 0 for v in out.values()), "cap_total produced a negative requirement")
    check(out == {"str": 20, "dex": 20, "int": 20}, f"cap_total not proportional: {out}")
    # a single value already at the cap is left alone (int(v*cap/tot) == v)
    check(weapons.cap_total({"int": 99}, 99) == {"int": 99}, "cap_total should keep a value equal to the cap")


# --------------------------------------------------------------------------- new_prices conservation
def test_new_prices() -> None:
    rng = random.Random(7)
    # shuffle mode is a permutation: no id lost or duplicated, length preserved (conservation).
    for old in ([5], [3, 1, 4, 1, 5, 9, 2, 6], [100, 200, 300], list(range(1, 60)), [7] * 10):
        new = randomize.new_prices(list(old), rng, "shuffle", None, None, "test")
        check(sorted(new) == sorted(old), f"new_prices('shuffle') broke conservation for {old[:6]}")
        check(len(new) == len(old), "new_prices('shuffle') changed the length")
    # range mode: same length, every value >= 1 and rounded to two significant digits
    old = [1000, 2000, 5000, 40000]
    new = randomize.new_prices(old, random.Random(3), "range", None, None, "test")
    check(len(new) == len(old), "new_prices('range') changed the length")
    check(all(v >= 1 for v in new), "new_prices('range') produced a price below 1")
    check(all(randomize.round_price(v) == v for v in new), "new_prices('range') returned un-rounded prices")


# --------------------------------------------------------------------------- dropshuffle keep_sets
def _set_aware_shuffle(found, names, rng):
    """Mirror of dropshuffle.shuffle()'s keep_sets armour branch (lines ~95-123).  found[n] is a
    mutable one-cell list [iid]; returns nothing, mutates found in place."""
    groups: dict[str, list[int]] = {}
    for n, cell in enumerate(found):
        key = _set_key(names.get(cell[0], ""))
        if key:
            groups.setdefault(key, []).append(n)
    sets = [v for v in groups.values() if len(v) > 1]
    by_size: dict[int, list[list[int]]] = {}
    for group in sets:
        by_size.setdefault(len(group), []).append(group)
    moved: set[int] = set()
    for size in sorted(by_size):
        bucket = by_size[size]
        donors = bucket[:]
        rng.shuffle(donors)
        for group, donor in zip(bucket, donors):
            if group is donor:
                moved.update(group)            # the fix: hold a self-mapped set out of `rest`
                continue
            data = [found[t][0] for t in donor]
            for n, iid in zip(group, data):
                found[n][0] = iid
                moved.add(n)
    rest = [n for n in range(len(found)) if n not in moved]
    ids = [found[n][0] for n in rest]
    rng.shuffle(ids)
    for n, iid in zip(rest, ids):
        found[n][0] = iid


def test_dropshuffle_sets() -> None:
    # One 4-piece set "Alpha" + loose single pieces: with keep_sets the set must stay coherent
    # (its four slots all hold Alpha pieces) while the loose items shuffle among themselves.
    names = {100: "Alpha Helm", 101: "Alpha Armor", 102: "Alpha Gauntlets", 103: "Alpha Greaves",
             200: "Ragged Cloak", 201: "Travel Cloth", 202: "Worn Sandals", 203: "Old Hood"}
    for seed in range(40):
        found = [[iid] for iid in (100, 101, 102, 103, 200, 201, 202, 203)]
        _set_aware_shuffle(found, names, random.Random(seed))
        alpha_slots = [found[n][0] for n in range(4)]
        check(all(_set_key(names.get(i, "")) == "Alpha" for i in alpha_slots),
              f"keep_sets split the Alpha set (seed {seed}): slots 0-3 hold {alpha_slots}")
        # conservation: the eight ids are still exactly the eight we started with
        check(sorted(c[0] for c in found) == [100, 101, 102, 103, 200, 201, 202, 203],
              f"keep_sets lost/duplicated an id (seed {seed})")

    # Several same-size sets: every set's slots end holding exactly one single set (never a mix).
    # Each piece name must end in a SLOT_WORDS word so dropshuffle._set_key groups the set.
    piece_words = ("Helm", "Armor", "Gauntlets")
    names2 = {}
    specs = []
    iid = 1000
    for s in range(6):                      # 6 sets of 3 pieces
        for p in range(3):
            names2[iid] = f"Set{s} {piece_words[p]}"
            specs.append(iid)
            iid += 1
    for seed in range(40):
        found = [[i] for i in specs]
        _set_aware_shuffle(found, names2, random.Random(seed))
        # group slots by their ORIGINAL set (every 3 consecutive slots) and check each holds one set
        for s in range(6):
            slots = [found[s * 3 + p][0] for p in range(3)]
            keys = {_set_key(names2.get(i, "")) for i in slots}
            check(len(keys) == 1 and None not in keys,
                  f"keep_sets mixed sets in a 3-piece group (seed {seed}): {slots} -> {keys}")


# --------------------------------------------------------------------------- erreg round-trips
def test_erreg_roundtrip() -> None:
    # DCX zstd: write then read returns the exact payload (no DLL involved).
    payload = bytes(range(256)) * 8
    r = erreg.read_dcx(erreg.write_dcx(erreg.Dcx(16, payload, erreg.CODEC_ZSTD)))
    check(r.data == payload, "DCX zstd round-trip changed the payload")
    check(r.codec == erreg.CODEC_ZSTD and r.level == 16, "DCX zstd round-trip lost codec/level")
    # DCX deflate (zlib): the read-only path the other randomizers' msgbnd uses.
    rd = erreg.read_dcx(erreg.write_dcx(erreg.Dcx(9, payload, erreg.CODEC_DEFLATE)))
    check(rd.data == payload, "DCX deflate round-trip changed the payload")

    # AES-256-CBC: decrypt(encrypt(x)) reproduces x plus PKCS#7 padding; the IV is preserved.
    iv = bytes(range(16))
    enc = erreg.encrypt_regulation(payload, iv)
    dec = erreg.decrypt_regulation(enc)
    n = 16 - len(payload) % 16
    check(enc[:16] == iv, "encrypt_regulation did not keep the IV")
    check(dec[:len(payload)] == payload, "AES round-trip changed the data")
    check(dec[len(payload):] == bytes([n]) * n, "AES round-trip has wrong PKCS#7 padding")

    # BND4: the shipped msg archive is a zstd DCX holding a BND4; decoding and rebuilding it must be
    # byte-for-byte identical (this is the "unmodified params are written back verbatim" guarantee).
    archive = textarchives.MSG_DIR / "engus" / textarchives.ITEM_ARCHIVE
    if not archive.is_file():
        check(True, "")                     # archive not shipped in this checkout: skip, not a failure
        return
    dcx = erreg.read_dcx(archive.read_bytes())
    bnd = erreg.read_bnd4(dcx.data)
    check(erreg.write_bnd4(bnd) == dcx.data,
          f"BND4 round-trip not byte-exact ({len(bnd.files)} files, {len(dcx.data)} bytes)")
    check(len(bnd.files) > 0, "BND4 round-trip found no files")


# --------------------------------------------------------------------------- main
def _make_named_bnd() -> bytes:
    # Minimal BND4 with one unicode file name, built so a mid-name truncation exercises the name scan
    # that used to loop forever.  1 file, 32-bit offsets, no ids, name table right after the headers.
    name = "Test\0".encode("utf-16-le")                       # 10 bytes, ends with \0\0
    data = b"hello"
    fhs, table_end = 24, 0x40 + 24                           # one 24-byte file header
    name_off = table_end
    data_off = name_off + len(name)
    buf = bytearray(data_off + len(data))
    buf[0:4] = b"BND4"
    struct.pack_into("<i", buf, 0x0C, 1)                     # file_count
    struct.pack_into("<q", buf, 0x20, fhs)                   # file_header_size
    struct.pack_into("<q", buf, 0x28, table_end)             # file_headers_end
    buf[0x30] = 1                                            # unicode
    buf[0x31] = 0x0C                                         # raw_fmt: has_names, no reverse/long_off/compress
    struct.pack_into("<q", buf, 0x40 + 8, len(data))         # csize
    struct.pack_into("<I", buf, 0x40 + 16, data_off)         # doff (32-bit)
    struct.pack_into("<i", buf, 0x40 + 20, name_off)         # noff
    buf[name_off:name_off + len(name)] = name
    buf[data_off:] = data
    return bytes(buf)


def test_erreg_malformed() -> None:
    # Every truncated / corrupt input must fail as a clean ValueError, never a raw struct.error /
    # IndexError / UnicodeDecodeError and never a hang.  Regression guard for the read_bnd4 name-scan
    # infinite loop (a truncated BND4 left noff past the buffer) and the header bounds checks.  Uses
    # the shipped zstd msg archive (no DLL, no game file).
    archive = textarchives.MSG_DIR / "engus" / textarchives.ITEM_ARCHIVE
    if not archive.is_file():
        check(True, "")                     # archive not shipped in this checkout: skip, not a failure
        return
    dcx_bytes = archive.read_bytes()
    bnd = erreg.read_dcx(dcx_bytes).data    # sanity: the real archive decodes (zstd, no DLL)
    pd = erreg.load_paramdef(HERE / "paramdef" / "NpcParam.xml")

    def expect(fn, label: str) -> None:
        try:
            fn()
        except BaseException as e:          # noqa: BLE001 - classify the failure mode
            check(type(e) is ValueError, f"{label}: raised {type(e).__name__}, want ValueError")
            return
        check(False, f"{label}: unexpectedly succeeded on corrupt input")

    # read_bnd4: short / bad-magic / truncated headers + absurd file_count (the hang driver)
    expect(lambda: erreg.read_bnd4(b""), "read_bnd4 empty")
    expect(lambda: erreg.read_bnd4(b"NOPE"), "read_bnd4 bad magic")
    for n in (1, 4, 0x24, 0x40, 0x100):
        expect(lambda k=n: erreg.read_bnd4(bnd[:k]), f"read_bnd4 trunc@{n}")
    for fc in (0x7FFFFFFF, 1_000_000, -1):
        b = bytearray(bnd[:0x8000]); struct.pack_into("<i", b, 0x0C, fc)
        expect(lambda bb=bytes(b): erreg.read_bnd4(bb), f"read_bnd4 file_count={fc}")
    # a synthetic NAMED BND4 guards the name-scan hang portably (the shipped msg archive has no names):
    # cutting the buffer just before the name terminator used to loop forever; now it must ValueError
    named = _make_named_bnd()
    check(erreg.read_bnd4(named).files[0].name == "Test", "synthetic named BND4 name parsed")
    expect(lambda: erreg.read_bnd4(named[:0x60]), "read_bnd4 name-scan cut off (hang guard)")
    check(len(erreg.read_bnd4(bnd).files) > 0, "read_bnd4 full buffer should still parse")

    # Param: short buffers must fail cleanly, not IndexError on buf[0x2D] / struct.error on the row table
    for buf in (b"", b"\0" * 8, b"\0" * 0x20, bnd[:0x20]):
        expect(lambda b=buf: erreg.Param(b, pd), f"Param len={len(buf)}")

    # read_dcx: bad magic + header-only truncation (the truncated-file DCX case)
    expect(lambda: erreg.read_dcx(b""), "read_dcx empty")
    expect(lambda: erreg.read_dcx(b"XXXX" + dcx_bytes[4:]), "read_dcx bad magic")
    expect(lambda: erreg.read_dcx(dcx_bytes[:0x4C]), "read_dcx header-only")
    check(erreg.read_dcx(dcx_bytes).data == bnd, "read_dcx full should round-trip to the BND4")


# --------------------------------------------------------------------------- writer round-trip (item 1)
def test_erreg_writer() -> None:
    # The writer must round-trip: whatever read_dcx / read_bnd4 / decrypt_regulation reads back must
    # equal what was written, across sizes, content patterns and both portable codecs.
    rng = random.Random(99)
    payloads = [b"", b"\0", b"\0" * 15, b"\0" * 16, b"\0" * 17, bytes(range(256)),
                b"\xff" * 1000, bytes(rng.randrange(256) for _ in range(65536)), b"ABCD" * 4096]
    for codec, levels in ((erreg.CODEC_ZSTD, (16, 19)), (erreg.CODEC_DEFLATE, (9,))):
        for i, payload in enumerate(payloads):
            for level in levels:
                r = erreg.read_dcx(erreg.write_dcx(erreg.Dcx(level, payload, codec), 16))
                check(r.data == payload, f"write_dcx/read_dcx {codec} lvl{level} payload#{i} changed data")
                check(r.codec == codec and r.level == level,
                      f"write_dcx/read_dcx {codec} lvl{level} lost codec/level")
    # AES-256-CBC round-trip across sizes and IVs (decrypt does not unpad -> check data + PKCS#7)
    for i, payload in enumerate(payloads):
        iv = bytes(rng.randrange(256) for _ in range(16))
        enc = erreg.encrypt_regulation(payload, iv)
        dec = erreg.decrypt_regulation(enc)
        n = 16 - len(payload) % 16
        check(enc[:16] == iv, f"encrypt_regulation payload#{i} dropped the IV")
        check(dec[:len(payload)] == payload, f"AES round-trip payload#{i} changed data")
        check(dec[len(payload):] == bytes([n]) * n, f"AES round-trip payload#{i} bad PKCS#7 padding")
    # BND4 write->read round-trip (byte-exact) and with randomised file contents of the same length
    archive = textarchives.MSG_DIR / "engus" / textarchives.ITEM_ARCHIVE
    if archive.is_file():
        bnd = erreg.read_dcx(archive.read_bytes()).data
        b0 = erreg.read_bnd4(bnd)
        check(erreg.write_bnd4(b0) == bnd, "write_bnd4(read_bnd4(x)) is not byte-exact")
        b1 = erreg.read_bnd4(bnd)
        for k in range(len(b1.datas)):
            b1.datas[k] = bytes(rng.randrange(256) for _ in range(len(b1.datas[k])))
        rebuilt = erreg.read_bnd4(erreg.write_bnd4(b1))
        check(len(rebuilt.datas) == len(b1.datas)
              and all(a == b for a, b in zip(rebuilt.datas, b1.datas)),
              "write_bnd4 randomised round-trip lost or changed file data")


# --------------------------------------------------------------------------- corrupt input (item 5)
def test_corrupt_input() -> None:
    # A truncated / garbage input must fail fast and cleanly, never hang. This is the path the GUI
    # worker runs (randomize.main(argv)); the read_bnd4 name-scan hang lived exactly here, so the CLI
    # run is guarded by a subprocess timeout - a hang shows up as a failure, not a frozen test.
    tmp = Path(tempfile.mkdtemp(prefix="er_corrupt_"))
    try:
        cases = {
            "empty.bin": b"",
            "short.bin": b"DCX\0" + b"\0" * 10,
            "garbage.bin": bytes(random.randrange(256) for _ in range(4096)),
            "fake_bnd.bin": b"BND4" + b"\0" * 60,
        }
        for name, data in cases.items():
            pth = tmp / name
            pth.write_bytes(data)
            try:
                erreg.Regulation(pth)
            except ValueError:
                check(True, "")
            except BaseException as e:                       # noqa: BLE001
                check(False, f"Regulation({name}) raised {type(e).__name__}, want ValueError")
            else:
                check(False, f"Regulation({name}) unexpectedly succeeded on garbage")
        # the full CLI path (what the GUI worker calls) must exit non-zero quickly, never hang
        try:
            res = subprocess.run(
                [sys.executable, "-I", str(HERE / "randomize.py"),
                 "--input", str(tmp / "garbage.bin"), "--output", str(tmp / "out.bin"), "--dry-run"],
                capture_output=True, timeout=30)
            check(res.returncode != 0, "randomize.py on garbage input should exit non-zero")
        except subprocess.TimeoutExpired:
            check(False, "randomize.py HUNG on garbage input (a parser infinite loop)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------- real-file fuzz (items 4 + 9)
def _all_lot_ids(reg: "erreg.Regulation") -> list[int]:
    """Every item id referenced by an enemy lot, map lot or shop - dropshuffle permutes these, so the
    sorted multiset must be identical before and after a shuffle."""
    ids: list[int] = []
    lot_pd = erreg.load_paramdef(HERE / "paramdef" / "ItemLotParam.xml")   # shared by enemy + map lots
    for pname in ("ItemLotParam_enemy", "ItemLotParam_map"):
        P = reg.param(pname, lot_pd)
        fields = [f"lotItemId0{i}" for i in range(1, 9) if f"lotItemId0{i}" in P.pd]
        for r in P.rows:
            for f in fields:
                v = P.get(r, f)
                if v:
                    ids.append(v)
    S = reg.param("ShopLineupParam", erreg.load_paramdef(HERE / "paramdef" / "ShopLineupParam.xml"))
    for r in S.rows:
        v = S.get(r, "equipId")
        if v:
            ids.append(v)
    return ids


def test_real_file(path: str) -> None:
    # Real-data parser fuzz + dropshuffle conservation. Needs the oo2core DLL for a KRAK regulation;
    # skips cleanly (not a failure) if the file cannot be loaded. Run with:
    #   python tools/test_logic.py --fuzz <regulation.bin>      (or set ER_REGULATION_BIN)
    try:
        reg = erreg.Regulation(path)
    except BaseException as e:                               # noqa: BLE001
        print(f"  (real-file tests skipped: cannot load {path}: {type(e).__name__}: {e})")
        return
    dec = erreg.decrypt_regulation(open(path, "rb").read())
    bnd_prefix = erreg.read_dcx(dec).data[:0x8000]
    param_prefix = reg.raw("NpcParam")[:0x8000]
    pd = erreg.load_paramdef(HERE / "paramdef" / "NpcParam.xml")

    def expect(fn, label: str) -> None:
        try:
            fn()
        except BaseException as e:                           # noqa: BLE001
            check(type(e) is ValueError, f"realfuzz {label}: raised {type(e).__name__}, want ValueError")
            return
        check(False, f"realfuzz {label}: unexpectedly succeeded")

    for n in (0, 1, 4, 0x24, 0x40, 0x100):
        expect(lambda k=n: erreg.read_bnd4(bnd_prefix[:k]), f"read_bnd4 trunc@{n}")
    b = bytearray(bnd_prefix); struct.pack_into("<i", b, 0x0C, 0x7FFFFFFF)
    expect(lambda: erreg.read_bnd4(bytes(b)), "read_bnd4 file_count=0x7FFFFFFF")
    for buf in (b"", b"\0" * 0x20, param_prefix[:0x20]):
        expect(lambda x=buf: erreg.Param(x, pd), f"Param len={len(buf)}")
    expect(lambda: erreg.read_dcx(dec[:0x4C]), "read_dcx header-only")
    check(len(reg.files) > 0, "real regulation should have parsed >0 BND4 files")
    # the 32 KB prefix is a truncated BND4 (the name table sits at the end of the full 89 MB), so the
    # bounded name scan must reject it cleanly rather than loop
    expect(lambda: erreg.read_bnd4(bnd_prefix), "read_bnd4 32KB prefix (name table cut off)")

    # dropshuffle conservation (item 9): a shuffle permutes lot ids, never loses or duplicates one
    for kind in ("weapon", "armor", "talisman", "goods", "ashes"):
        before = _all_lot_ids(reg)
        dropshuffle.shuffle(reg, random.Random(1), kind, kind == "armor")
        after = _all_lot_ids(reg)
        check(sorted(before) == sorted(after),
              f"dropshuffle {kind}: lot ids not conserved ({len(before)} before, {len(after)} after)")

    # enemy_drops: randomize_hp in shuffle mode permutes the hp values -> the multiset is conserved
    N = reg.param("NpcParam", erreg.load_paramdef(HERE / "paramdef" / "NpcParam.xml"))
    hp_before = sorted(N.get(r, "hp") for r in N.rows if N.get(r, "hp") > 0)
    enemy_drops.randomize_hp(reg, random.Random(3), "shuffle", None, None)
    hp_after = sorted(N.get(r, "hp") for r in N.rows if N.get(r, "hp") > 0)
    check(hp_before == hp_after, "enemy_drops.randomize_hp shuffle did not conserve the hp multiset")

    # weapons: somber_infusable + random_movesets must not drop or rename an original EquipParamWeapon row
    wp = weapons.Weapons(reg)
    before_ids = {r.id for r in wp.W.rows}
    wp.somber_infusable()
    wp.random_movesets(random.Random(2))
    after_ids = {r.id for r in wp.W.rows}
    check(before_ids.issubset(after_ids),
          f"weapons: passes dropped/renamed an original row id ({len(before_ids)} -> {len(after_ids)})")

    # gems (Ashes of War): skill and effect shuffles permute within weapon-type groups -> multisets conserved
    ashes = gems.Ashes(reg)
    sk_before = sorted(ashes.P.get(r, "swordArtsParamId") for r in ashes.P.rows)
    ashes.randomize_skills(random.Random(4))
    sk_after = sorted(ashes.P.get(r, "swordArtsParamId") for r in ashes.P.rows)
    check(sk_before == sk_after, "gems.randomize_skills did not conserve the skill multiset")
    fx_before = sorted(tuple(ashes.P.get(r, f"spEffectId{i}") for i in range(3)) for r in ashes.P.rows)
    ashes.randomize_effects(random.Random(5))
    fx_after = sorted(tuple(ashes.P.get(r, f"spEffectId{i}") for i in range(3)) for r in ashes.P.rows)
    check(fx_before == fx_after, "gems.randomize_effects did not conserve the effect-triple multiset")

    # spells: shuffle mode deranges the effect bundle -> the bundle multiset is conserved
    sp = spells.Spells(reg)
    sp_fields = spells.EFFECT_FIELDS
    sp_before = sorted(tuple(sp.P.get(r, f) for f in sp_fields) for r in sp.pool)
    sp.randomize_effects(random.Random(6), "shuffle", None)
    sp_after = sorted(tuple(sp.P.get(r, f) for f in sp_fields) for r in sp.pool)
    check(sp_before == sp_after, "spells.randomize_effects shuffle did not conserve the effect-bundle multiset")

    # spells.random_stats: costs stay in their tiers, requirements stay a capped vanilla set, slots 1
    sp.random_stats(random.Random(7))
    fp_max = max(hi for (lo, hi), _ in spells.FP_TIERS)
    st_max = max(hi for (lo, hi), _ in spells.STAMINA_TIERS)
    vanilla_max = [max(v[i] for v in sp.vanilla_req) for i in range(len(spells.REQ_STATS))]
    check(all(sum(sp.P.get(r, f) for f in spells.REQ_STATS) <= spells.REQ_TOTAL_MAX for r in sp.pool),
          f"spells.random_stats: a requirement sum exceeds {spells.REQ_TOTAL_MAX}")
    check(all(all(sp.P.get(r, f) >= 0 for f in spells.REQ_STATS) for r in sp.pool),
          "spells.random_stats: a negative requirement")
    check(all(all(sp.P.get(r, f) <= vanilla_max[i] for i, f in enumerate(spells.REQ_STATS)) for r in sp.pool),
          "spells.random_stats: a requirement exceeds the vanilla envelope")
    check(all(sp.P.get(r, "slotLength") == 1 for r in sp.pool), "spells.random_stats: a spell did not get slotLength 1")
    check(all(0 <= sp.P.get(r, "mp") <= fp_max for r in sp.pool), "spells.random_stats: an FP cost is out of tier range")
    check(all(0 <= sp.P.get(r, "stamina") <= st_max for r in sp.pool), "spells.random_stats: a stamina cost is out of tier range")

    # runes: shuffle mode permutes the getSoul bounties -> the multiset is conserved
    N2 = reg.param("NpcParam", erreg.load_paramdef(HERE / "paramdef" / "NpcParam.xml"))
    rune_before = sorted(N2.get(r, "getSoul") for r in N2.rows if N2.get(r, "getSoul") > 0)
    runes.randomize(reg, random.Random(8), "shuffle", None, None)
    rune_after = sorted(N2.get(r, "getSoul") for r in N2.rows if N2.get(r, "getSoul") > 0)
    check(rune_before == rune_after, "runes.randomize shuffle did not conserve the rune multiset")

    # boss_scale (item): range scaling keeps values positive; --couple recomputes bounty from final HP
    boss = boss_scale.boss_ids(N2, 0)
    if boss:
        van = {r.id: (N2.get(r, "hp"), N2.get(r, "getSoul")) for r in N2.rows if r.id in boss}
        boss_scale.apply(reg, random.Random(9), boss, {}, (0.75, 1.5), (0.75, 1.5), False)
        check(all(N2.get(r, "hp") >= 1 for r in N2.rows if r.id in boss), "boss_scale: a boss hp dropped below 1")
        check(all(N2.get(r, "getSoul") >= 1 for r in N2.rows if r.id in boss), "boss_scale: a boss rune bounty dropped below 1")
        # couple: getSoul = round(hp_final * vanilla_soul / vanilla_hp) for every boss with a vanilla hp
        boss_scale.apply(reg, random.Random(10), boss, van, (1.0, 1.0), (1.0, 1.0), couple=True)
        ok = True
        for r in N2.rows:
            if r.id in boss and r.id in van and van[r.id][0] > 0:
                oh, os_ = van[r.id]
                expected = round(N2.get(r, "hp") * os_ / oh)
                if N2.get(r, "getSoul") != expected:
                    ok = False
                    break
        check(ok, "boss_scale couple did not recompute the bounty from the final HP")

    # goods: the (maxNum, maxRepositoryNum) pair is permuted among stackable items -> pair multiset conserved
    G = reg.param("EquipParamGoods", erreg.load_paramdef(HERE / "paramdef" / "EquipParamGoods.xml"))
    goods_names = erreg.load_names(HERE / "names" / "EquipParamGoods.txt")
    gp_before = sorted((G.get(r, "maxNum"), G.get(r, "maxRepositoryNum")) for r in G.rows)
    goods.randomize(reg, goods_names, random.Random(10))
    gp_after = sorted((G.get(r, "maxNum"), G.get(r, "maxRepositoryNum")) for r in G.rows)
    check(gp_before == gp_after, "goods.randomize did not conserve the (maxNum, maxRepositoryNum) pair multiset")

    # armour: each ARMOR_COLUMNS value is permuted within its slot -> every column's multiset is conserved
    arm = gear.Armour(reg)
    arm_cols = {f: sorted(arm.P.get(r, f) for r in arm.P.rows) for f in gear.ARMOR_COLUMNS}
    arm.randomize(random.Random(11))
    check(all(arm_cols[f] == sorted(arm.P.get(r, f) for r in arm.P.rows) for f in gear.ARMOR_COLUMNS),
          "gear.Armour.randomize did not conserve a column's value multiset")

    # talismans: whole rows are permuted -> the row-bytes multiset is conserved
    tal = gear.Talismans(reg)
    tal_before = sorted(bytes(r.data) for r in tal.P.rows)
    tal.randomize(random.Random(12))
    tal_after = sorted(bytes(r.data) for r in tal.P.rows)
    check(tal_before == tal_after, "gear.Talismans.randomize did not conserve the row-bytes multiset")

    # armour fresh (item 9): every rolled value stays within its slot's vanilla range
    arm2 = gear.Armour(reg)
    fresh_ranges: dict = {}
    for cat, rows in arm2.rows().items():
        for f in gear.ARMOR_COLUMNS:
            vals = [arm2.P.get(r, f) for r in rows]
            if vals and max(vals) > min(vals):
                fresh_ranges[(cat, f)] = (min(vals), max(vals))
    arm2.randomize_fresh(random.Random(14), True)
    check(all(fresh_ranges[(cat, f)][0] <= arm2.P.get(r, f) <= fresh_ranges[(cat, f)][1]
              for cat, rows in arm2.rows().items() for r in rows
              for f in gear.ARMOR_COLUMNS if (cat, f) in fresh_ranges),
          "gear.Armour.randomize_fresh rolled a value outside its slot's range")

    # shops (item 8): only equipId changes; equipType and price are preserved; rerolled slots get a valid item
    S = reg.param("ShopLineupParam", erreg.load_paramdef(HERE / "paramdef" / "ShopLineupParam.xml"))
    s_before = {r.id: (S.get(r, "equipType"), S.get(r, "value")) for r in S.rows}
    pools = shops._pools(reg, set(shops.SHOP_FOR.values()))
    shops.randomize(reg, random.Random(13))
    s_after = {r.id: (S.get(r, "equipType"), S.get(r, "value")) for r in S.rows}
    check(s_before == s_after, "shops.randomize changed equipType or price (only equipId may change)")
    check(all(S.get(r, "equipId") == 0 or S.get(r, "equipId") in pools[shops.SHOP_FOR[S.get(r, "equipType")]]
              for r in S.rows if shops.SHOP_FOR.get(S.get(r, "equipType")) in pools),
          "shops.randomize put an item of the wrong category in a shop slot")

    # talkmsg + weapon_names (item 8): patch an FMG text into a shipped archive and read it back
    archive = textarchives.MSG_DIR / "engus" / textarchives.ITEM_ARCHIVE
    if archive.is_file():
        fm0 = weapon_names.read_fmgs(archive)
        check(len(weapon_names.affixes(fm0["WeaponName"])) == 12, "weapon_names.affixes did not learn all 12 affinities")
        wid = next(iter(fm0["WeaponName"]))
        patched, written = talkmsg.patch_fmgs(archive, {"WeaponName": {wid: "ZZ RoundTrip Test"}}, None)
        tmp = Path(tempfile.mkdtemp(prefix="er_fmg_")) / "rt.msgbnd.dcx"
        tmp.write_bytes(patched)
        try:
            fm1 = weapon_names.read_fmgs(tmp)
            check(fm1["WeaponName"].get(wid) == "ZZ RoundTrip Test", "talkmsg.patch_fmgs did not round-trip the FMG text")
            check(sum(written.values()) >= 1, "talkmsg.patch_fmgs wrote to no FMG")
        finally:
            shutil.rmtree(tmp.parent, ignore_errors=True)

    # weapon_names (item 8): every affixed name keeps its base name (prefix + base + suffix)
    wn = weapon_names.WeaponNames(reg, [str(a) for a in weapon_names.shipped_archives()])
    wn.prepare()
    if wn.patches:
        _src, wtexts, _anchor = wn.patches[0]
        fm = weapon_names.read_fmgs(_src)
        base_names = set(fm[weapon_names.FMG_NAME].values())
        check(all(any(bn in nn for bn in base_names)
                  for nn in wtexts.get(weapon_names.FMG_NAME, {}).values()),
              "weapon_names: an affixed name does not contain its base name")

    # durations (item 9): shuffle mode permutes the per-buff durations -> the multiset is conserved
    D = durations.Durations(reg)
    d_before = sorted(int(round(D.duration(u.effects[0]))) for u in D.units if D.duration(u.effects[0]) is not None)
    D.randomize(random.Random(15), "shuffle", None, None)
    d_after = sorted(int(round(D.duration(u.effects[0]))) for u in D.units if D.duration(u.effects[0]) is not None)
    check(d_before == d_after, "durations.randomize shuffle did not conserve the duration multiset")

    # flasks (item 4): the swap moves the two flasks into valid candidate slots, and the
    # first-grace lots hand out the swapped item instead (the flask is gone from its own lot).
    F = flasks.Flasks(reg)
    franges = [(lo, hi) for lo, hi in flasks.FLASK_LOTS.values()]
    L = reg.param("ItemLotParam_map", erreg.load_paramdef(HERE / "paramdef" / "ItemLotParam.xml"))

    def _flask_count() -> int:
        c = sum(1 for r in L.rows for i in range(1, 9)
                if any(lo <= L.get(r, f"lotItemId0{i}") <= hi for lo, hi in franges))
        c += sum(1 for r in F.S.rows if any(lo <= F.S.get(r, "equipId") <= hi for lo, hi in franges))
        return c

    fc_before = _flask_count()
    flask_ids = {L.get(L.by_id[lot], "lotItemId01") for lot in flasks.FLASK_LOTS if L.by_id.get(lot) is not None}

    def _flask_spots() -> set:
        s = set()
        for r in L.rows:
            if any(L.get(r, f"lotItemId0{i}") in flask_ids for i in range(1, 9)):
                s.add(("lot", r.id))
        for r in F.S.rows:
            if F.S.get(r, "equipId") in flask_ids:
                s.add(("shop", r.id))
        return s

    pool = F.lot_spots() + F.merchants()
    valid = ({("lot", s.row.id) for s in pool if isinstance(s, flasks.Spot)}
             | {("lot", x.id) for s in pool if isinstance(s, flasks.Spot) for x in s.alternatives}
             | {("shop", slot.row.id) for m in pool if isinstance(m, flasks.Merchant) for slot in m.slots})
    before = _flask_spots()
    F.randomize(random.Random(17), "anywhere")
    check(_flask_count() == fc_before, "flasks.randomize changed the number of flasks (lost or duplicated)")
    after = _flask_spots()
    check({("lot", lot) for lot in flasks.FLASK_LOTS} <= (before - after),
          "a flask stayed in its own first-grace lot (swap did not move it)")
    check((after - before) <= valid, f"flask landed outside a candidate slot: {after - before - valid}")

    # start_items (item 9): the bell/lantern are appended with a flag, and re-running adds no duplicate
    start_items.give(reg, ["bell", "lantern"])

    def _has_item(gid: int) -> bool:
        return any(L.get(r, "lotItemId01") == gid and L.get(r, "getItemFlagId") != 0
                   for r in L.rows if 2000 <= r.id <= 2010)

    check(_has_item(8158) and _has_item(2070), "start_items.give did not place the bell/lantern with a flag")
    n1 = len([r for r in L.rows if 2000 <= r.id <= 2010])
    start_items.give(reg, ["bell", "lantern"])
    n2 = len([r for r in L.rows if 2000 <= r.id <= 2010])
    check(n1 == n2, "start_items.give is not idempotent (duplicate rows)")

    # oodle (item 8): the ctypes compress/decompress boundary round-trips, and a wrong raw_len is rejected
    for data in (b"x", b"hello world" * 100, bytes(range(256)) * 4096, random.Random(1).randbytes(200000)):
        comp = oodle.compress(data, oodle.KRAKEN, oodle.LEVEL_FAST)
        check(oodle.decompress(comp, len(data)) == data, f"oodle KRAK round-trip failed for {len(data)} bytes")
    try:
        oodle.decompress(oodle.compress(b"abc" * 1000, oodle.KRAKEN, oodle.LEVEL_FAST), 999999)
        check(False, "oodle.decompress accepted a wrong raw_len")
    except RuntimeError:
        check(True, "")                     # the intended failure mode for a bad length

    # Param.loose (item 8): the no-paramdef path (talismans) builds a readable Param
    loose = erreg.Param.loose(reg, "EquipParamAccessory")
    check(len(loose.rows) > 0, "Param.loose built no rows for EquipParamAccessory")

    # dropshuffle non-set path (item 8): keep_sets=False permutes ids within each category -> conserved
    for kind in ("weapon", "armor", "talisman", "goods", "ashes"):
        before = sorted(_all_lot_ids(reg))
        dropshuffle.shuffle(reg, random.Random(20), kind, keep_sets=False)
        after = sorted(_all_lot_ids(reg))
        check(before == after, f"dropshuffle {kind} (non-set): lot ids not conserved")

    # weapons.random_stats (item 8): a stat-reroll must not change what the weapon IS (structural fields)
    wp2 = weapons.Weapons(reg)
    struct_before = {r.id: (wp2.W.get(r, "wepType"), wp2.W.get(r, "behaviorVariationId")) for r in wp2.W.rows}
    wp2.random_stats(random.Random(21))
    struct_after = {r.id: (wp2.W.get(r, "wepType"), wp2.W.get(r, "behaviorVariationId")) for r in wp2.W.rows}
    check(struct_before == struct_after, "weapons.random_stats changed wepType/behaviorVariationId")
    check(len(wp2.W.rows) == len(struct_before), "weapons.random_stats added/removed rows")
    print(f"  (real-file fuzz + dropshuffle/enemy-drops/weapons/gems/spells/runes/boss-scale/goods/gear/shops/talkmsg/durations/flasks/start-items/oodle/non-set-shuffle/weapon-stats ran on {path})")


# --------------------------------------------------------------------------- main
def test_erreg_cap() -> None:
    # D2: a DCX whose declared uncompressed size is far smaller than the zstd frame's content size is
    # rejected (the one-shot decompress + content-size cap stops a corrupt/hostile expanding frame)
    w = bytearray(erreg.write_dcx(erreg.Dcx(16, b"x" * 5000, erreg.CODEC_ZSTD)))
    struct.pack_into(">I", w, 0x1C, 10)           # lie: uncomp=10, but the frame content size is 5000
    try:
        erreg.read_dcx(bytes(w))
        check(False, "DCX with an oversized frame content size was accepted")
    except ValueError:
        check(True, "")


# --------------------------------------------------------------------------- main
def test_zones() -> None:
    # the zone classifier maps known locations to the right tier, and the cap scales with the zone (item 5)
    check(zones.zone_of("[Stormveil - Godrick] Godrick's Great Rune") == 0, "zone_of Stormveil/Limgrave != 0")
    check(zones.zone_of("[Leyndell - Morgott] Remembrance of the Omen King") == 1, "zone_of Leyndell != 1")
    check(zones.zone_of("[Farum Azula - Maliketh] Remembrance of the Black Blade") == 2, "zone_of Farum Azula != 2")
    check(zones.zone_of("Heart of Bayle") == 3, "zone_of Land of Shadow != 3")
    check(zones.zone_of("base") == 1, "zone_of an unknown location should default to the middle tier")
    check(zones.max_share(0) < zones.max_share(2), "early-zone cap should be lower than the late-zone cap")
    check(zones.ZONE_CURVE_SHIFT.get(2, 0) > zones.ZONE_CURVE_SHIFT.get(0, 0),
          "later zones should shift the rarity curve toward even (stronger average, not just a higher cap)")


# --------------------------------------------------------------------------- main
# Tests that run inside a frozen PyInstaller bundle: no subprocess, no game file, no DLL.  gui.py
# --self-test uses this to prove the bundle (modules + shipped data) is intact before shipping.
SELF_TEST_FNS = (test_derangement, test_round_price, test_cap_total, test_new_prices,
                 test_dropshuffle_sets, test_erreg_roundtrip, test_erreg_malformed, test_erreg_writer,
                 test_erreg_cap, test_zones)


def run_self_test() -> tuple[int, int]:
    """Run the in-bundle-safe logic tests. Returns (checks, failures). No subprocess, no game file, no DLL."""
    global _CHECKS, _FAILS
    _CHECKS = 0
    _FAILS = []
    for fn in SELF_TEST_FNS:
        fn()
    return _CHECKS, len(_FAILS)


def main() -> int:
    args = sys.argv[1:]
    fuzz_path = os.environ.get("ER_REGULATION_BIN")
    if "--fuzz" in args:
        i = args.index("--fuzz")
        if i + 1 < len(args):
            fuzz_path = args[i + 1]

    for fn in SELF_TEST_FNS + (test_corrupt_input,):
        fn()
    if fuzz_path:
        print(f"real-file fuzz on {fuzz_path} ...")
        test_real_file(fuzz_path)

    if _FAILS:
        print(f"LOGIC FAIL - {_CHECKS} checks, {len(_FAILS)} failed:")
        for msg in _FAILS[:40]:
            print(f"  - {msg}")
        if len(_FAILS) > 40:
            print(f"  ... and {len(_FAILS) - 40} more")
        return 1
    extra = " + writer + corrupt-input" + (" + real-file" if fuzz_path else "")
    print(f"LOGIC PASS - {_CHECKS} checks green "
          f"(derangement, round_price, cap_total, new_prices, dropshuffle sets, erreg round-trips + malformed{extra})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
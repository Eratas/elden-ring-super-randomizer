"""Logic tests for the randomizer's pure helpers and binary core.

Everything here runs with no regulation.bin, no game install and no oo2core DLL, so it belongs in the
per-commit gate (tools/gate.py).  It pins the behaviour that, if it regressed, would produce *silently
wrong output in the field* rather than a crash:

  * derangement(n) terminates for every n (n < 2 used to loop forever) and is a fixed-point-free
    permutation for n >= 2 - both randomize.py and spells.py;
  * round_price / cap_total / new_prices (shuffle) - the shared price/quantity maths and the
    conservation invariant "a shuffle is a permutation, so no id is lost or duplicated";
 * the keep_sets armour coherence invariant in dropshuffle (a set that maps to itself must stay a
     coherent set - the bug fixed in run 20261118); this test drives dropshuffle.set_plan itself, not
     a copy of it;
 * the erreg binary round-trips: DCX (zstd + deflate), AES-256-CBC encrypt/decrypt, and a BND4
     decoded and rebuilt byte-for-byte from the shipped msg archive (no DLL needed - it is zstd);
 * erreg robustness: truncated / corrupt input to read_bnd4, Param and read_dcx fails as a clean
     ValueError (no raw struct.error / IndexError, and never the read_bnd4 name-scan hang);
 * the options dict -> argv -> dict round trip for EVERY option, again over hundreds of random
     *combinations* of options, and once for every *pair* of options: the GUI builds the command line
     with options.argv_from_values() and runs it verbatim, so an option it forgets to emit is silently
     ignored by the engine (--goods, --spells, --loot-rarity and --no-backup-replace all were);
 * the backup-and-replace round trip in a temp dir: make_backup is byte-exact and non-destructive,
     restore undoes a replacement, prune keeps the newest N - the only pass that overwrites the user's
     own files;
 * the Nexus description (tools/md2nexus.py): the Markdown -> BBCode mapping case by case, the three
     invariants a generated page must satisfy (only known tags, no leftover Markdown, balanced BBCode),
     that the README holds no literal BBCode, that both checked-in artifacts are current - and a fuzz of
     300 random Markdown documents through both the normal and the strict renderer;
 * empty pools: new_prices, the price passes and talkmsg.read_fmg must report "nothing to do", not
     crash on a regulation.bin that does not fill them;
 * version.py vs version_info.txt: the window footer and the exe's PE resource must not drift.

Run directly with `python tools/test_logic.py` or through tools/gate.py.
"""
from __future__ import annotations

import os
import random
import re
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
import loot
import oodle
import options
import randomize
import runes
import shops
import spells
import start_items
import talkmsg
import textarchives
import version
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
    """Apply the production dropshuffle.set_plan to a list of one-cell lists (the fixture shape).

    This used to be a hand-written copy of the keep_sets branch.  The copy read the mutable cells
    (`found[t][0]`) where the real branch reads the original ids (`found[t][3]`), so the two produced
    different assignments on 200 of 200 seeds while both "passed" - the test guarded a copy of the
    logic, not the logic.  It now calls the real function, so a regression in set_plan fails here.
    """
    plan = dropshuffle.set_plan([cell[0] for cell in found], names, rng)
    for cell, new in zip(found, plan):
        cell[0] = new


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
    # a KRAK header with no payload: the game's own regulation.bin is KRAK, so this is the truncation a
    # user actually hits.  oodle.decompress raises RuntimeError (bad stream, or no DLL); it must surface
    # as the same ValueError the zstd/DFLT branches raise, not a different exception type.
    krak = bytearray(0x4C)
    krak[0:4] = b"DCX\0"
    struct.pack_into(">II", krak, 0x1C, 1 << 20, 64)          # uncompressed size, compressed size
    krak[0x28:0x2C] = b"KRAK"
    krak[0x30] = 6
    expect(lambda: erreg.read_dcx(bytes(krak)), "read_dcx KRAK header-only")
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
    # Each flask must have left its own lot.  A swap between the two flask lots is a legitimate outcome -
    # lot 2000 then holds the *other* flask - so this tests the item in the row, not the mere presence of
    # a flask in the spot (the old spot-level form failed on exactly that swap).
    for lot, (lo, hi) in flasks.FLASK_LOTS.items():
        row = L.by_id.get(lot)
        if row is None:
            continue
        check(not lo <= L.get(row, "lotItemId01") <= hi,
              f"flask lot {lot} still holds a flask from its own range {lo}..{hi} (swap did not move it)")
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


# --------------------------------------------------------------------------- argv round trip
# The window does not call the engine itself: it builds a command line with options.argv_from_values()
# and hands that to randomize.main().  An option that function forgets to emit therefore looks ticked
# in the window, appears ticked in the saved preset, and does nothing at all - which is exactly how
# --goods, --spells, --loot-rarity and --no-backup-replace shipped dead.  This locks the contract
# from the module docstring ("dict -> argv -> dict") for every option, not just the ones that broke.
_ARGV_SKIP = {"input", "output", "archives", "weapon_names", "repack", "dry_run", "simulate",
              "weapons", "no_weapon_names"}          # not a pass switch: handled by their own tests
# (key, value) overrides that a single option needs to survive validate() on its own
_ARGV_NEEDS = {"random_prices": {"price_mode": "shuffle"}, "random_runes": {"rune_mode": "shuffle"},
               "random_enemy_hp": {"hp_mode": "shuffle"}, "random_durations": {"duration_mode": "shuffle"},
               "random_stats": {"stat_groups": "attack"}, "somber_infusable": {"no_weapon_names": True},
               "loot_rarity": {"random_loot_levels": True},
               "loot_boss_bonus": {"random_loot_levels": True},
               "loot_max_level": {"random_loot_levels": True},
               # these are only part of the command line in their own mode; in the default mode they are
               # correctly left out, so the test has to ask for the mode that uses them
               "price_min": {"price_mode": "range"}, "price_max": {"price_mode": "range"},
               "sell_min": {"price_mode": "range"}, "sell_max": {"price_mode": "range"},
               "rune_min": {"rune_mode": "range"}, "rune_max": {"rune_mode": "range"},
               "hp_min": {"hp_mode": "range"}, "hp_max": {"hp_mode": "range"},
               "duration_min": {"duration_mode": "range"}, "duration_max": {"duration_mode": "range"},
               "moveset_variety": {"moveset_mode": "bound"},
               "enemy_drop_chance": {"enemy_drop_rolls": 3}}
_ARGV_INT = {"zstd_window": 18, "max_size": 2_000_000}     # the defaults are not "a different value"


# One parser for every argv test.  build_argparse() rebuilds ~100 arguments, which costs far more than the
# parse itself - and the pair sweep parses thousands of command lines.
_ARGV_PARSER = options.build_argparse(prog="t")


def _argv_dict() -> dict:
    d = {o.key: o.default for o in options.OPTIONS}
    d.update({"input": "in.bin", "output": "out/regulation.bin", "repack": False,
              "dry_run": False, "simulate": None})
    return d


def _argv_value(o, d: dict):
    """A value for `o` that differs from its default (or None when there is no such value)."""
    if o.kind == "bool":
        return not o.default
    if o.kind == "enum":
        return next((c for c in o.choices if c != o.default), None)
    if o.kind == "int":
        return _ARGV_INT.get(o.key, 7)
    if o.kind == "pair":
        return (0.5, 1.5)
    if o.kind == "groups":
        return ",".join(list(o.items)[:2])
    if o.kind == "paths":
        return ()
    return "X"


def _argv_normalize(o, value):
    """Compare groups as a set (order is not part of the contract) and everything else verbatim.

    Two spellings of "no restriction" are one value: an empty group list is the documented "every item"
    (options.py: `default=""`, randomize.py: `_kinds("")` -> None), and `loot_max_level` 0 is the
    documented "no cap" (loot.py: `min(top, cap) if cap else top`).
    """
    if o.kind == "groups":
        picked = set(x for x in str(value or "").split(",") if x)
        return set(o.items) if not picked else picked
    if o.key == "loot_max_level":
        return None if not value else value
    return value


def test_argv_roundtrip() -> None:
    # 1. every option: set it apart from its default, argv it, parse it back - the value must survive
    for o in options.OPTIONS:
        if o.key in _ARGV_SKIP or o.kind == "paths":
            continue
        d = _argv_dict()
        for k in o.needs:                       # a dependent option needs its master on
            d[k] = True
        d.update(_ARGV_NEEDS.get(o.key, {}))
        d[o.key] = _argv_value(o, d)
        v = options.validate(d)
        argv = options.argv_from_values(v)
        back = options.validate(options.values_from_args(_ARGV_PARSER.parse_args(argv)))
        check(_argv_normalize(o, v.get(o.key)) == _argv_normalize(o, back.get(o.key)),
              f"argv round trip lost {o.key}: {v.get(o.key)!r} -> {back.get(o.key)!r} (argv: {argv})")

    # 2. the switches that were dead: they must appear in the command line verbatim
    argv = options.argv_from_values(options.validate(dict(_argv_dict(), goods=True, spells=True)))
    check("--goods" in argv, f"--goods missing from the argv of a goods run: {argv}")
    check("--spells" in argv, f"--spells missing from the argv of a spell run: {argv}")

    # 3. --no-backup-replace must reach the engine, or the opt-out silently overwrites the user's files
    for repack in (False, True):
        argv = options.argv_from_values(dict(_argv_dict(), repack=repack, backup_replace=False))
        check("--no-backup-replace" in argv,
              f"--no-backup-replace missing (repack={repack}): {argv}")
    check("--no-backup-replace" not in options.argv_from_values(dict(_argv_dict(), backup_replace=True)),
          "--no-backup-replace emitted for a run that asked for a backup")

    # 4. compression: the CLI default is the table default, so every other value must be passed.  The
    # old test compared against a sibling value and so inverted both knobs ("fast" meant "max",
    # "auto" meant "kraken").
    for level in ("fast", "max"):
        for codec in ("auto", "kraken", "zstd"):
            argv = options.argv_from_values(dict(_argv_dict(), compression_level=level, compression=codec))
            back = options.values_from_args(_ARGV_PARSER.parse_args(argv))
            check((back["compression_level"], back["compression"]) == (level, codec),
                  f"compression {level}/{codec} became {back['compression_level']}/{back['compression']}")

    # 5. loot: rarity / boss bonus / level cap hang off --random-loot-levels, not off --zone-loot-levels
    argv = options.argv_from_values(options.validate(
        dict(_argv_dict(), random_loot_levels=True, loot_rarity="even",
             loot_boss_bonus="same", loot_max_level=12)))
    for flag, value in (("--loot-rarity", "even"), ("--loot-boss-bonus", "same"), ("--loot-max-level", "12")):
        check(flag in argv and value in argv, f"{flag} {value} missing without --zone-loot-levels: {argv}")

    # 6. a groups value may be the comma string of the GUI var or a list; list() on a string would
    #    split it into characters and emit "--stat-groups a,t,t,a,c,k,..."
    argv = options.argv_from_values(dict(_argv_dict(), random_stats=True, stat_groups="attack,guard"))
    check("--stat-groups" in argv and argv[argv.index("--stat-groups") + 1] == "attack,guard",
          f"stat_groups string was not passed through verbatim: {argv}")

    # 7. a raw (unvalidated) dict must not crash: a pair option's default is still the string "1.0,1.0"
    argv = options.argv_from_values(_argv_dict())
    check(isinstance(argv, list) and "--input" in argv, "argv_from_values crashed on a raw value dict")


# --------------------------------------------------------------------------- argv fuzz
# The per-option test above proves each switch survives on its own.  This one throws random *sets* of
# options at the same round trip, because the interesting failures are interactions: a master switch
# that turns off, a group list plus its master, the --weapons shorthand, two options whose emission
# gates collide.  Deterministic (fixed seed), so a failure is reproducible from the seed in the message.
_ARGV_FUZZ_SEED = 20261119
_ARGV_FUZZ_SAMPLES = 600
# options that are only part of the command line in one mode: (mode key, the value that uses them)
_ARGV_FUZZ_MODES = {"price_min": ("price_mode", "range"), "price_max": ("price_mode", "range"),
                    "sell_min": ("price_mode", "range"), "sell_max": ("price_mode", "range"),
                    "rune_min": ("rune_mode", "range"), "rune_max": ("rune_mode", "range"),
                    "hp_min": ("hp_mode", "range"), "hp_max": ("hp_mode", "range"),
                    "duration_min": ("duration_mode", "range"), "duration_max": ("duration_mode", "range"),
                    "moveset_variety": ("moveset_mode", "bound")}
_ARGV_FUZZ_INTS = {"zstd_window": [16, 18, 22], "max_size": [None, 2_000_000, 2_359_296],
                   "seed": [None, "", 0, 1, 12345], "boss_min_runes": [0, 3000, 9000],
                   "loot_max_level": [None, 0, 5, 12], "enemy_drop_rolls": [None, 1, 3, 8],
                   "enemy_drop_chance": [1, 25, 50, 90, 100],
                   "price_min": [None, 1, 10, 500], "price_max": [None, 100, 900, 99999],
                   "sell_min": [None, 1, 10], "sell_max": [None, 100, 9999],
                   "rune_min": [None, 1, 100], "rune_max": [None, 500, 99999],
                   "hp_min": [None, 1, 100], "hp_max": [None, 500, 99999],
                   "duration_min": [None, 5, 30], "duration_max": [None, 60, 600],
                   "moveset_variety": [1, 2, 3, 4],
                   "stamina_rate": [(0.8, 1.2), (0.5, 1.0), (1.0, 2.0)],
                   "boss_hp_scale": [(1.0, 1.0), (1.2, 1.4), (0.5, 2.0)],
                   "boss_rune_scale": [(1.0, 1.0), (1.2, 1.4), (0.5, 2.0)]}


def _argv_random_dict(rng: random.Random) -> dict:
    """A random value dict: masters, enums, ints, pairs and group lists all over the place."""
    d = _argv_dict()
    for o in options.OPTIONS:
        if o.key in _ARGV_SKIP or o.kind == "paths":
            continue
        if o.kind == "bool":
            # both directions, explicitly: an option whose default is True (backup_replace,
            # armour_keep_sets) is only exercised by a False, and that is exactly where a dropped
            # --no-<flag> hides
            d[o.key] = rng.random() < 0.5
        elif o.kind == "enum":
            d[o.key] = rng.choice(o.choices)
        elif o.kind == "int":
            d[o.key] = rng.choice(_ARGV_FUZZ_INTS.get(o.key, [None, 1, 7]))
        elif o.kind == "pair":
            d[o.key] = rng.choice(_ARGV_FUZZ_INTS[o.key])
        elif o.kind == "groups":
            items = list(o.items)
            if rng.random() < 0.6:
                d[o.key] = rng.choice(items + [",".join(rng.sample(items, rng.randint(1, len(items))))])
        elif o.kind in ("str", "path"):
            d[o.key] = rng.choice([None, "X"])
    return d


def _argv_gated(o, gui: dict) -> bool:
    """True when `o` is legitimately absent from the command line in this configuration."""
    if not options.is_active(o, gui):           # its master switch is off
        return True
    if o.key in _ARGV_FUZZ_MODES:
        mode_key, wanted = _ARGV_FUZZ_MODES[o.key]
        return gui.get(mode_key) != wanted
    if o.key == "enemy_drop_chance":            # only meaningful together with explicit rolls
        return gui.get("enemy_drop_rolls") in (None, "")
    return False


def test_argv_fuzz() -> None:
    rng = random.Random(_ARGV_FUZZ_SEED)
    valid = 0
    for i in range(_ARGV_FUZZ_SAMPLES):
        try:
            gui = options.validate(_argv_random_dict(rng))
        except (ValueError, SystemExit):
            continue                            # a combination the rules reject is not a round trip
        valid += 1
        argv = options.argv_from_values(gui)
        try:
            back = options.validate(options.values_from_args(
                _ARGV_PARSER.parse_args(argv)))
        except SystemExit as e:
            check(False, f"argv fuzz #{i} (seed {_ARGV_FUZZ_SEED}) produced an unparsable argv "
                         f"({e}): {argv}")
            continue
        for o in options.OPTIONS:
            if o.key in _ARGV_SKIP or o.kind == "paths":
                continue
            if _argv_normalize(o, gui.get(o.key)) != _argv_normalize(o, back.get(o.key)) \
                    and not _argv_gated(o, gui):
                check(False, f"argv fuzz #{i} (seed {_ARGV_FUZZ_SEED}) lost {o.key}: "
                             f"{gui.get(o.key)!r} -> {back.get(o.key)!r} in {argv}")
    check(valid >= _ARGV_FUZZ_SAMPLES // 3,
          f"only {valid} of {_ARGV_FUZZ_SAMPLES} random option sets were valid - the generator or "
          f"validate() changed shape and the fuzz is no longer covering the space")


# --------------------------------------------------------------------------- argv pairs
def test_argv_pairs() -> None:
    """Every *pair* of options, set together.

    The random fuzz samples sets; this one guarantees coverage.  For each unordered pair both options are
    set to a non-default value and the round trip is checked.  Gates that only collide in combination -
    a group list next to the master it belongs to, two modes that share one limit, a shorthand next to
    the switches it expands to - are exactly what a sampled fuzz can miss.
    """
    visible = [o for o in options.OPTIONS if o.key not in _ARGV_SKIP and o.kind != "paths"]
    total = len(visible) * (len(visible) - 1) // 2
    checked = 0
    for i, first in enumerate(visible):
        for second in visible[i + 1:]:
            d = _argv_dict()
            for o in (first, second):
                d.update(_ARGV_NEEDS.get(o.key, {}))
                for k in o.needs:
                    d[k] = True
                d[o.key] = _argv_value(o, d)
            try:
                gui = options.validate(d)
            except (ValueError, SystemExit):
                continue                            # a pair the rules reject is not a round trip
            checked += 1
            argv = options.argv_from_values(gui)
            try:
                back = options.validate(options.values_from_args(
                    _ARGV_PARSER.parse_args(argv)))
            except SystemExit as e:
                check(False, f"argv pair {first.key}+{second.key} produced an unparsable argv "
                             f"({e}): {argv}")
                continue
            for o in (first, second):
                if _argv_normalize(o, gui.get(o.key)) != _argv_normalize(o, back.get(o.key)) \
                        and not _argv_gated(o, gui):
                    check(False, f"argv pair {first.key}+{second.key} lost {o.key}: "
                                 f"{gui.get(o.key)!r} -> {back.get(o.key)!r} in {argv}")
    check(checked >= total // 4,
          f"only {checked} of {total} option pairs were valid - the generator or validate() changed "
          f"shape and the pair sweep is no longer covering the space")


# --------------------------------------------------------------------------- dropshuffle set_plan
def _plan_groups(iids: list[int], names: dict[int, str]) -> dict[str, list[int]]:
    """The slot groups dropshuffle.set_plan builds: set key -> the slots that hold its pieces."""
    groups: dict[str, list[int]] = {}
    for n, iid in enumerate(iids):
        key = dropshuffle._set_key(names.get(iid, ""))
        if key:
            groups.setdefault(key, []).append(n)
    return groups


def test_dropshuffle_plan_fuzz() -> None:
    """Property fuzz for dropshuffle.set_plan - the keep_sets branch.

    The invariant that already broke once (run 20261118): a set that maps to itself must stay a coherent
    set, and no set may ever be split.  Checked over 300 random synthetic wardrobes:

      * the plan is a permutation - no item lost, none duplicated;
      * every slot of a set receives items from exactly ONE set, of the SAME size (so a helm, chest,
        gauntlets and greaves all become one other set, never a mixture);
      * a loose slot only ever receives a loose item;
      * one seed always gives one plan (reproducibility).

    Names deliberately include words `_set_key` does not know ("Odd 3 Sword"), because those must count as
    loose - the piece-word list is the only thing that defines a set.
    """
    check(dropshuffle.set_plan([], {}, random.Random(1)) == [], "set_plan([]) should return []")

    rng = random.Random(4242)
    words = list(dropshuffle.SLOT_WORDS)
    for case in range(300):
        names: dict[int, str] = {}
        ids: list[int] = []
        next_id = 100000

        def take() -> int:
            nonlocal next_id
            iid = next_id
            next_id += rng.randint(1, 7)
            return iid

        for s in range(rng.randint(0, 6)):                 # 0..5 real sets, each 2..5 pieces
            key = f"Set{case}-{s}"
            for _ in range(rng.randint(2, 5)):
                iid = take()
                names[iid] = f"{key} {rng.choice(words)}"
                ids.append(iid)
        for j in range(rng.randint(0, 10)):                # loose items
            iid = take()
            names[iid] = rng.choice([f"Loose {j}", f"Odd {j} Sword", f"Thing {j}"])
            ids.append(iid)
        if not ids:
            continue

        plan = dropshuffle.set_plan(ids, names, random.Random(case))
        check(sorted(plan) == sorted(ids),
              f"plan fuzz case {case}: not a permutation ({len(plan)} slots, {len(ids)} items)")

        groups = _plan_groups(ids, names)
        size_of = {k: len(v) for k, v in groups.items()}
        grouped_slots = {n for v in groups.values() for n in v}
        for key, slots in groups.items():
            got = {dropshuffle._set_key(names.get(plan[n], "")) for n in slots}
            check(len(got) == 1, f"plan fuzz case {case}: set {key!r} was split across {got}")
            donor = next(iter(got), None)
            check(donor is not None and size_of.get(donor) == len(slots),
                  f"plan fuzz case {case}: set {key!r} ({len(slots)} pieces) received items from "
                  f"{donor!r} of size {size_of.get(donor)}")
        for n in range(len(ids)):
            if n in grouped_slots:
                continue
            check(dropshuffle._set_key(names.get(plan[n], "")) is None,
                  f"plan fuzz case {case}: loose slot {n} received the set item "
                  f"{names.get(plan[n])!r}")

        check(dropshuffle.set_plan(ids, names, random.Random(case)) == plan,
              f"plan fuzz case {case}: set_plan is not reproducible for one seed")


# --------------------------------------------------------------------------- backup
def test_backup() -> None:
    """Backup-and-replace is the only pass that overwrites the user's own files, so it gets a round trip.

    Everything happens in a temp dir (backup.program_dir is redirected, so nothing touches the repo):

      * make_backup copies byte-for-byte, leaves the originals untouched, and names each file's origin;
      * make_backup returns None when there is nothing to back up;
      * restore puts every file back byte-for-byte after they were clobbered;
      * prune_backups keeps only the newest N and reports how many it removed;
      * backup_and_replace really replaces the input with the generated output (and the msg archive with
        the patched copy), and restore really undoes both.
    """
    import json

    import backup

    root = Path(tempfile.mkdtemp(prefix="backup-test-"))
    saved = backup.program_dir
    backup.program_dir = lambda: root            # keep the sandbox out of the repo
    try:
        src = root / "regulation.bin"
        archive = root / "msg" / "engus" / backup.ARCHIVE_NAME
        archive.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(b"ORIGINAL-BYTES" * 100)
        archive.write_bytes(b"ARCHIVE-BYTES" * 50)
        original = {src.resolve(): src.read_bytes(), archive.resolve(): archive.read_bytes()}

        made = backup.make_backup([src, archive])
        check(made is not None and made.is_dir(), "make_backup did not create a folder")
        check(src.read_bytes() == original[src.resolve()]
              and archive.read_bytes() == original[archive.resolve()],
              "make_backup modified the files it was asked to back up")
        entries = json.loads((made / backup.MANIFEST).read_text(encoding="utf-8"))
        check(len(entries) == 2, f"the manifest lists {len(entries)} files, expected 2")
        for entry in entries:
            key = Path(entry["original"])
            check(key in original, f"the manifest names an unknown original: {key}")
            copied = made / entry["name"]
            check(copied.is_file() and copied.read_bytes() == original.get(key),
                  f"{entry['name']} is not a byte-for-byte copy of its original")

        check(backup.make_backup([root / "does-not-exist.bin"]) is None,
              "make_backup should return None when no file exists")

        src.write_bytes(b"CLOBBERED")
        archive.write_bytes(b"CLOBBERED")
        restored = backup.restore(made)
        check(len(restored) == 2, f"restore reported {len(restored)} files, expected 2")
        check(src.read_bytes() == original[src.resolve()],
              "restore did not put regulation.bin back byte-for-byte")
        check(archive.read_bytes() == original[archive.resolve()],
              "restore did not put the msg archive back byte-for-byte")

        for _ in range(5):
            backup.make_backup([src])
        check(len(backup.list_backups()) == 6, "expected 6 backups before pruning")
        removed = backup.prune_backups(keep=2)
        check(removed == 4, f"prune removed {removed} backups, expected 4")
        check(len(backup.list_backups()) == 2, "prune did not leave exactly 2 backups")

        out = root / "out" / "regulation.bin"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"GENERATED" * 200)
        patched = root / "out" / "msg" / "engus" / backup.ARCHIVE_NAME
        patched.parent.mkdir(parents=True, exist_ok=True)
        patched.write_bytes(b"PATCHED-ARCHIVE" * 20)
        made = backup.backup_and_replace(src, out, [root / "msg"])
        check(made is not None, "backup_and_replace returned None")
        check(src.read_bytes() == out.read_bytes(),
              "backup_and_replace did not copy the generated file over the input")
        check(archive.read_bytes() == patched.read_bytes(),
              "backup_and_replace did not copy the patched archive over the source")
        backup.restore(made)
        check(src.read_bytes() == original[src.resolve()],
              "restore after backup_and_replace did not undo the regulation.bin replacement")
        check(archive.read_bytes() == original[archive.resolve()],
              "restore after backup_and_replace did not undo the archive replacement")
    finally:
        backup.program_dir = saved
        shutil.rmtree(root, ignore_errors=True)


# --------------------------------------------------------------------------- empty pools
def test_empty_pools() -> None:
    """A pool the regulation.bin does not fill must be a no-op, not a crash.

    `new_prices(range)` derives its limits from the pool, so an empty one used to raise
    "min() iterable argument is empty" - naming neither the pass nor the file.  read_fmg is fed
    user-supplied archives (--weapon-names <folder>), so a truncated one must be a clean ValueError.
    """
    for mode in ("shuffle", "range"):
        check(randomize.new_prices([], random.Random(1), mode, None, None, "price") == [],
              f"new_prices([], {mode!r}) should return [], not raise")
    check(randomize.new_prices([], random.Random(1), "range", 10, 90, "price") == [],
          "new_prices([], 'range') with explicit limits should still return []")

    class _Empty:                                   # a param table whose rows are all filtered out
        rows: list = []

        def get(self, r, f):
            return 0

    class _Reg:
        def param(self, name, pd):
            return _Empty()

    for mode in ("shuffle", "range"):
        lines = randomize.randomize_prices(_Reg(), random.Random(1), mode, None, None, sell=True)
        check(any("left alone" in x for x in lines),
              f"randomize_prices on an empty pool should say so (mode {mode!r}): {lines}")
        lines = randomize.randomize_equipment_sell(_Reg(), random.Random(1), mode, None, None)
        check(any("left alone" in x for x in lines),
              f"randomize_equipment_sell on an empty pool should say so (mode {mode!r}): {lines}")

    for buf in (b"", b"\x00", b"\x00\x00\x02", b"\x00\x00\x02" + b"\x00" * 36):
        try:
            talkmsg.read_fmg(buf)
        except ValueError:
            continue
        except BaseException as e:                  # IndexError, struct.error: the raw failures
            check(False, f"read_fmg({buf!r}) raised {type(e).__name__}: {e} (expected ValueError)")
        else:
            check(False, f"read_fmg({buf!r}) returned instead of raising ValueError")


# --------------------------------------------------------------------------- version resource
def test_version_resource() -> None:
    """tools/version.py and tools/version_info.txt are two spellings of one number.

    Both files say they must stay in step and nothing checked it: bump one and the exe reports a
    version the window does not (or the other way round), which also breaks the offline update check,
    since it compares latest_version.txt against __version__.  Skipped inside a frozen bundle, which
    consumes version_info.txt at build time and does not ship it.
    """
    path = HERE / "version_info.txt"
    if not path.is_file():
        return
    want = tuple(int(x) for x in version.__version__.split("."))
    text = path.read_text(encoding="utf-8")
    for field in ("filevers", "prodvers", "FileVersion", "ProductVersion"):
        match = re.search(rf"{field}\s*=?\s*\(?([\d,\s.'\"]+)", text)
        check(match is not None, f"version_info.txt has no {field}")
        if not match:
            continue
        got = tuple(int(x) for x in re.findall(r"\d+", match.group(1)))
        check(got[:len(want)] == want,
              f"version_info.txt {field} {got} != version.py {want}")


# --------------------------------------------------------------------------- Nexus description
def test_nexus_doc() -> None:
    """README.md -> Nexus BBCode (tools/md2nexus.py).

    Nexus Mods' description editor takes BBCode, not Markdown, so the mod page is generated from the
    README.  These checks are about the *renderer*: the mapping itself, the invariants that catch the two
    ways a generated description silently breaks (an unknown tag the site may not render, and a leftover
    Markdown marker - an orphaned ** is bold that never opened), and the staleness of the checked-in file.
    """
    try:
        import md2nexus
    except ImportError:                              # source-only: not bundled in the frozen exe
        return

    cases = [
        ("# Title", "[heading]Title[/heading]"),
        ("## Section", "[heading]Section[/heading]"),
        ("### Sub", "[b]Sub[/b]"),
        ("**bold**", "[b]bold[/b]"),
        ("*it*", "[i]it[/i]"),
        ("a `code` b", "a code b"),                   # Nexus has no inline code tag
        ("**b `c` b**", "[b]b c b[/b]"),              # a code span inside bold must not orphan the **
        ("[text](https://x/y)", "[url=https://x/y]text[/url]"),
        ("---", "[line]"),
        ("- one\n- two", "[list]\n[*] one\n[*] two\n[/list]"),
        ("1. one\n2. two", "[list=1]\n[*] one\n[*] two\n[/list]"),
        ("| a | b |\n|---|---|\n| 1 | 2 |", "[list]\n[*] [b]a | b[/b]\n[*] 1 | 2\n[/list]"),
        ("```\nx = 1\n```", "[code]\nx = 1\n[/code]"),
        ("para one\nstill one\n\npara two", "para one still one\n\npara two"),
    ]
    for source, want in cases:
        got = md2nexus.render(source).strip()
        check(got == want, f"md2nexus.render({source!r}) = {got!r}, want {want!r}")

    got = md2nexus.render("- first line\n  continued here\n- second").strip()
    check(got == "[list]\n[*] first line continued here\n[*] second\n[/list]",
          f"a wrapped list item split into two: {got!r}")

    check(md2nexus.problems(md2nexus.render("# T\n\nplain text")) == [],
          f"a clean document reported problems: {md2nexus.problems(md2nexus.render('# T'))}")
    check(any("bold" in p for p in md2nexus.problems("plain ** text")),
          "problems() did not flag a stray ** outside a code block")
    check(any("unbalanced" in p for p in md2nexus.problems("[list]\n[*] x")),
          "problems() did not flag an unclosed [list]")
    check(any("allowed" in p for p in md2nexus.problems("[table]x[/table]")),
          "problems() did not flag a tag outside the allowed set")

    # a literal BBCode tag in the source is markup nobody wrote, and inline code does NOT hide it:
    # Nexus has no inline code tag, so the backticks are stripped and the brackets reach the page
    check(md2nexus.stray_source_tags("a [b]bold[/b] word") == ["b"],
          "stray_source_tags did not flag a literal [b] in prose")
    check(md2nexus.stray_source_tags("[b](https://example.com)") == [],
          "stray_source_tags mistook a Markdown link for BBCode")
    check(md2nexus.stray_source_tags("```\n[b]x[/b]\n```") == [],
          "stray_source_tags flagged markup inside a fenced block")
    check(md2nexus.stray_source_tags("the [Preview] button") == [],
          "stray_source_tags flagged a bracket that is not a BBCode tag")

    if md2nexus.SOURCE.is_file() and md2nexus.TARGET.is_file():
        source = md2nexus.SOURCE.read_text(encoding="utf-8")
        check(md2nexus.stray_source_tags(source) == [],
              f"README.md contains literal BBCode outside a fenced block: "
              f"{md2nexus.stray_source_tags(source)}")
        for target, strict in ((md2nexus.TARGET, False), (md2nexus.STRICT_TARGET, True)):
            if not target.is_file():
                check(False, f"{target.name} is missing - run: python tools/md2nexus.py")
                continue
            rendered = md2nexus.render(source, strict=strict)
            check(target.read_text(encoding="utf-8") == rendered,
                  f"{target.name} is stale - run: python tools/md2nexus.py")
            check(md2nexus.problems(rendered, strict=strict) == [],
                  f"{target.name} has problems: {md2nexus.problems(rendered, strict=strict)}")
    else:
        print("  (NEXUS_DESCRIPTION check skipped: README.md or the generated files are missing)")


# --------------------------------------------------------------------------- md2nexus fuzz
_MD_WORDS = ("alpha", "Beta", "gamma-2", "file.bin", "x=1", "--flag", "v1.2.3", "Regulation",
             "oo2core_6_win64.dll", "a_b", "ZSTD", "longer-word", "42")
_MD_FENCES = ("```", "~~~")


def _md_inline(rng: random.Random) -> str:
    parts: list[str] = []
    for _ in range(rng.randint(1, 4)):
        word = rng.choice(_MD_WORDS)
        roll = rng.random()
        if roll < 0.15:
            parts.append(f"**{word}**")
        elif roll < 0.25:
            parts.append(f"*{word}*")
        elif roll < 0.36:
            parts.append(f"`{word}`")
        elif roll < 0.43:
            parts.append("`a|b`")                 # a pipe inside a code span must not split a table
        elif roll < 0.50:
            parts.append(f"[{word}](https://example.com/{word})")
        else:
            parts.append(word)
    return " ".join(parts)


def _md_block(rng: random.Random) -> str:
    roll = rng.random()
    if roll < 0.10:
        return "#" * rng.randint(1, 4) + " " + _md_inline(rng)
    if roll < 0.16:
        return rng.choice(["---", "***", "___"])
    if roll < 0.32:                                      # fenced block, sometimes with a language hint
        body = [_md_inline(rng) for _ in range(rng.randint(0, 4))]
        if rng.random() < 0.5:
            # markup that must stay literal inside the block
            body.append(rng.choice(["[b]not bold[/b]", "[Preview] [Repack only]", "[list] fake",
                                    "[extension.regulation]", "`tick`"]))
        fence = rng.choice(_MD_FENCES)
        info = rng.choice(["", "", "", "bash", "toml"])
        return f"{fence}{info}\n" + "\n".join(body) + f"\n{fence}"
    if roll < 0.50:                                      # table
        cols = rng.randint(1, 4)
        rows = ["| " + " | ".join(_md_inline(rng) for _ in range(cols)) + " |",
                "|" + "|".join(["---"] * cols) + "|"]
        rows += ["| " + " | ".join(_md_inline(rng) for _ in range(cols)) + " |"
                 for _ in range(rng.randint(0, 3))]
        return "\n".join(rows)
    if roll < 0.68:                                      # bullet list, some items wrapped
        items = []
        for _ in range(rng.randint(1, 4)):
            text = _md_inline(rng)
            if rng.random() < 0.3:
                text += "\n  " + _md_inline(rng)
            items.append("- " + text)
        return "\n".join(items)
    if roll < 0.80:                                      # numbered list
        return "\n".join(f"{i}. {_md_inline(rng)}" for i in range(1, rng.randint(1, 4) + 1))
    return _md_inline(rng)                               # paragraph


def _md_fences(doc: str) -> list[tuple[str, str]]:
    """(info string, body) for every fenced block in a Markdown document."""
    return [(m.group(1).strip(), m.group(2))
            for m in re.finditer(r"^[`~]{3,}([^\n]*)\n(.*?)^[`~]{3,}\s*$", doc, flags=re.S | re.M)]


def _md_without_fences(doc: str) -> str:
    return re.sub(r"^[`~]{3,}[^\n]*\n.*?^[`~]{3,}\s*$", "", doc, flags=re.S | re.M)


_MD_DOCS = 5000          # random documents per run; ~2 s, and the whole generator is deterministic


def test_md2nexus_fuzz() -> None:
    """Random Markdown through the Nexus renderer: the output must always satisfy the invariants.

    A renderer has more ways to be wrong than a function has branches, and every one of them shows up on
    the mod page rather than in a traceback.  Over `_MD_DOCS` random documents (headings, wrapped list
    items, tables with pipes inside code spans, fenced blocks that contain markup which must stay literal,
    rules, links, bold/italic) assert, for both the normal and the strict render:

      * problems() is empty - only allowed tags, no leftover Markdown, balanced BBCode;
      * the render is deterministic - same input, same bytes;
      * no fenced content is dropped (a block's language hint is dropped by design: Nexus code blocks
        have no language, and a caption would be markup the tag cannot carry);
      * no word outside a fenced block is lost.

    One check per document, not per property: the corpus is a *property* sample, and counting every
    assertion would let 5,000 documents outweigh every hand-written test in the file put together.
    """
    try:
        import md2nexus
    except ImportError:                                  # source-only: not bundled in the frozen exe
        return

    rng = random.Random(90210)
    for case in range(_MD_DOCS):
        doc = "\n\n".join(_md_block(rng) for _ in range(rng.randint(1, 8))) + "\n"
        # rules (--- / *** / ___) are markup, not words: drop those lines before harvesting vocabulary
        outside = re.sub(r"^\s*([-*_])\1{2,}\s*$", "", _md_without_fences(doc), flags=re.M)
        words = {w for w in re.findall(r"[A-Za-z0-9_][A-Za-z0-9_.\-/]*", outside) if len(w) >= 3}
        fenced = _md_fences(doc)
        head = f"md2nexus fuzz #{case}"
        for strict in (False, True):
            label = f"{head} (strict={strict})"
            out = md2nexus.render(doc, strict=strict)
            bad = md2nexus.problems(out, strict=strict)
            bad += ["render is not deterministic"] if md2nexus.render(doc, strict=strict) != out else []
            missing = sorted(w for w in words if w not in out)
            if missing:
                bad.append(f"words lost: {missing[:8]}")
            for _info, body in fenced:
                bad += [f"fenced line dropped: {line!r}" for line in body.splitlines()
                        if line.strip() and line not in out]
            if bad:
                shown = doc if len(doc) <= 1200 else doc[:1200] + "\n... (truncated)"
                check(False, f"{label}: {bad[:4]}\n--- markdown ---\n{shown}")
            else:
                check(True, "")


# --------------------------------------------------------------------------- loot zone cap + tiers
def test_loot_zone_cap() -> None:
    # LL-001: a zone cap must never collapse to 0 (0 means "no cap" to Loot._top and rolls the FULL
    # ceiling, ignoring both the zone and the user's --loot-max-level).  max(1, int(top*share)) fixes it.
    zc = loot.Loot._zone_cap
    check(zc(25, 0.15, None) == 3, f"_zone_cap(25, 0.15, None) = {zc(25, 0.15, None)}, want 3")
    check(zc(5, 0.15, 5) == 1, f"_zone_cap(5, 0.15, 5) = {zc(5, 0.15, 5)}, want 1 (not 0)")
    check(zc(25, 0.5, None) == 12, f"_zone_cap(25, 0.5, None) = {zc(25, 0.5, None)}, want 12")
    # no zone (share == 1.0): max_level passes through unchanged (None / 0 / a positive cap)
    check(zc(25, 1.0, 5) == 5, "zone share 1.0 should return max_level 5")
    check(zc(25, 1.0, None) is None, "zone share 1.0 should return None (no cap)")
    check(zc(25, 1.0, 0) == 0, "zone share 1.0 with max_level 0 should stay 0 (no cap)")
    # the cap is actually honoured by the roll: cap=1 -> level 0 or 1 only
    L = loot.Loot.__new__(loot.Loot)
    L._ceilings = {1000: 25}
    rng = random.Random(3)
    check(all(L._roll(1000, rng, "common", 1)[1] <= 1 for _ in range(500)),
          "_roll with cap=1 produced a level > 1")


def test_loot_tiers() -> None:
    # LL-002: the half-open tier ranges must cover every level 0..top with no gap (every upgrade
    # level reachable), and at realistic ceilings each level belongs to exactly one tier (a closed-
    # interval ceil/floor double-counted boundary levels such as +3/+9/+15/+20 of a +25 weapon).
    for top in (1, 2, 3, 5, 7, 10, 13, 25):
        for curve, tiers in loot.TIERS.items():
            counts: dict[int, int] = {}
            for chosen in tiers:
                lo, hi = loot.Loot._tier_range(chosen, top)
                check(0 <= lo <= hi <= top,
                      f"{curve} top={top} tier {chosen}: bad range {lo}..{hi} (want 0<={lo}<={hi}<={top})")
                for lv in range(lo, hi + 1):
                    counts[lv] = counts.get(lv, 0) + 1
            missing = [lv for lv in range(top + 1) if lv not in counts]
            check(not missing, f"{curve} top={top}: upgrade levels never reachable: {missing}")
            # tiny ceilings (<=3 levels, fewer than the tiers) unavoidably overlap; at >=5 they must not
            if top >= 5:
                dups = sorted(lv for lv, n in counts.items() if n > 1)
                check(not dups, f"{curve} top={top}: boundary levels double-counted: {dups}")


# --------------------------------------------------------------------------- dropshuffle protection
def test_dropshuffle_protection() -> None:
    # DS-001: shuffle() must NOT move a one-time flagged row or a row that holds a key item, and must
    # leave the items it does move conserved (a permutation).  Drives the real shuffle() with a fake
    # EnemyDrops (no regulation.bin), the same shape test_dropshuffle_sets uses for set_plan.
    class _Row:
        def __init__(self, rid: int) -> None:
            self.id = rid
            self.data: dict[str, int] = {}

    class _P:
        def __init__(self, rows: list) -> None:
            self.rows = rows
            self.by_id = {r.id: r for r in rows}

        def get(self, row, field): return row.data.get(field, 0)
        def set(self, row, field, val): row.data[field] = val

    captured: dict = {}

    class _Ed:
        def __init__(self, reg) -> None:
            self.r1 = _Row(1); self.r1.data = {"lotItemCategory01": 1, "lotItemId01": 100, "lotItemBasePoint01": 10,
                                              "lotItemCategory02": 1, "lotItemId02": 101, "lotItemBasePoint02": 10}
            self.r2 = _Row(2); self.r2.data = {"getItemFlagId": 777,
                                              "lotItemCategory01": 1, "lotItemId01": 200, "lotItemBasePoint01": 10}
            self.r3 = _Row(3); self.r3.data = {"lotItemCategory01": 1, "lotItemId01": 300, "lotItemBasePoint01": 10}
            self.L = _P([self.r1, self.r2, self.r3]); self.M = _P([]); self.S = _P([])
            captured["ed"] = self

        def lots(self): return [1]
        def run(self, first): return [self.r1, self.r2, self.r3]
        def protected(self, r): return "one-time drop" if r.id == 2 else ""

    orig = dropshuffle.EnemyDrops
    dropshuffle.EnemyDrops = lambda reg: _Ed(reg)
    try:
        dropshuffle.shuffle(object(), random.Random(1), "goods", keep_sets=False)
    finally:
        dropshuffle.EnemyDrops = orig
    ed = captured["ed"]
    check(ed.r2.data.get("lotItemId01") == 200,
          f"protected one-time row slot moved: {ed.r2.data.get('lotItemId01')} != 200")
    unprotected = sorted([ed.r1.data.get("lotItemId01"), ed.r1.data.get("lotItemId02"),
                          ed.r3.data.get("lotItemId01")])
    check(unprotected == [100, 101, 300],
          f"unprotected slots not conserved: {unprotected} != [100, 101, 300]")


# --------------------------------------------------------------------------- main
# Tests that run inside a frozen PyInstaller bundle: no subprocess, no game file, no DLL.
# --self-test uses this to prove the bundle (modules + shipped data) is intact before shipping.
SELF_TEST_FNS = (test_derangement, test_round_price, test_cap_total, test_new_prices,
                 test_dropshuffle_sets, test_dropshuffle_plan_fuzz, test_loot_zone_cap, test_loot_tiers,
                 test_erreg_roundtrip, test_erreg_malformed, test_erreg_writer, test_erreg_cap, test_zones,
                 test_argv_roundtrip, test_argv_fuzz, test_argv_pairs, test_backup, test_empty_pools,
                 test_version_resource)


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

    for fn in SELF_TEST_FNS + (test_corrupt_input, test_nexus_doc, test_md2nexus_fuzz,
                               test_dropshuffle_protection):
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
          f"(derangement, round_price, cap_total, new_prices, dropshuffle sets + plan fuzz + "
          f"protection, loot zone cap + tier coverage, erreg round-trips + malformed, argv round trip "
          f"+ fuzz + pairs, backup, empty pools, nexus description + fuzz{extra})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
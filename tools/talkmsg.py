#!/usr/bin/env python3
"""Read and write the FMG text files inside the game's msgbnd archives.

An archive (msg/<language>/item_dlc02.msgbnd.dcx and friends) is a DCX-compressed BND4 of FMG files;
an FMG is a table of {text id: string}.  This module reads one FMG, writes one back, and patches a
set of {FMG prefix: {id: text}} into an archive while copying every other file through byte for byte.

`tools/weapon_names.py` is the only caller: it adds the names of the affinity rows that
--somber-infusable creates.  The DCX is written as DFLT (zlib), which is what the other randomizers
write and what the game reads for these files.
"""
from __future__ import annotations

import struct
from pathlib import Path

import erreg


def read_fmg(buf: bytes) -> dict[int, str]:
    """FMG version 2 (DS3 / Elden Ring, UTF-16): groups of consecutive ids pointing into an offset table."""
    if buf[0] != 0 or buf[1] != 0 or buf[2] != 2:
        raise ValueError("not a little-endian FMG version 2")
    groups, strings = struct.unpack_from("<ii", buf, 0x0C)
    offsets_at = struct.unpack_from("<q", buf, 0x18)[0]
    text: dict[int, str] = {}
    pos = 0x28
    for _ in range(groups):
        first_index, first_id, last_id = struct.unpack_from("<iii", buf, pos)
        pos += 0x10
        for i in range(last_id - first_id + 1):
            off = struct.unpack_from("<q", buf, offsets_at + 8 * (first_index + i))[0]
            if off == 0:
                continue
            end = buf.index(b"\0\0", off - off % 2) if off % 2 == 0 else off
            while end % 2:                               # the terminator must sit on a UTF-16 boundary
                end = buf.index(b"\0\0", end + 1)
            text[first_id + i] = buf[off:end].decode("utf-16-le")
    return text


def write_fmg(entries: dict[int, str]) -> bytes:
    """FMG version 2 as SoulsFormats writes it: runs of consecutive ids become groups, every entry has a
       string (callers drop ids they do not want instead of writing null offsets)."""
    ids = sorted(entries)
    groups: list[list[int]] = []
    for i in ids:
        if groups and groups[-1][1] + 1 == i:
            groups[-1][1] = i
        else:
            groups.append([i, i])
    offsets_at = 0x28 + 0x10 * len(groups)
    data_at = offsets_at + 8 * len(ids)
    strings = bytearray()
    offsets = []
    for i in ids:
        offsets.append(data_at + len(strings))
        strings += entries[i].encode("utf-16-le") + b"\0\0"
    head = bytearray(struct.pack("<BBBBiBBBBiiiqq", 0, 0, 2, 0, 0, 1, 0, 0, 0, len(groups), len(ids), 0xFF, offsets_at, 0))
    index = 0
    for first, last in groups:
        head += struct.pack("<iiii", index, first, last, 0)
        index += last - first + 1
    out = bytes(head) + b"".join(struct.pack("<q", o) for o in offsets) + bytes(strings)
    return struct.pack("<i", len(out)).join((out[:4], out[8:]))


def fmg_name(f) -> str:
    """The file name of a BND4 entry, whatever separator the archive uses."""
    return f.name.replace("\\", "/").rsplit("/", 1)[-1]


def _open(path: Path):
    raw = path.read_bytes()
    bnd = erreg.read_bnd4(erreg.read_dcx(raw).data if raw[:4] == b"DCX\0" else raw)
    return bnd


def patch_fmgs(src: Path, texts: dict[str, dict[int, str]], anchor: dict[int, int] | None = None
               ) -> tuple[bytes, dict[str, int]]:
    """The archive `src` (DCX around a BND4 of FMGs) with `texts` = {FMG prefix: {id: text}} written into its FMGs
       of that prefix (<prefix>.fmg, <prefix>_dlc01.fmg ...): an id one of them already holds is replaced there (in
       every one that has it); a new id goes to the FMG that holds anchor[id] (the base weapon of an affinity row:
       WeaponName.fmg for the base game, WeaponName_dlc01.fmg for Shadow of the Erdtree), else to <prefix>.fmg.
       Returns the DCX DFLT bytes and {fmg name: entries written}; every other file is copied byte for byte."""
    bnd = _open(src)
    names = {f.index: fmg_name(f) for f in bnd.files}
    fmgs: dict[int, dict[int, str]] = {}
    written: dict[str, int] = {}
    changed: set[int] = set()
    for prefix, entries in texts.items():
        low = prefix.lower()
        idx = [i for i, n in names.items()
               if n.lower() == low + ".fmg" or (n.lower().startswith(low + "_") and n.lower().endswith(".fmg"))]
        if not idx:
            raise SystemExit(f"{src}: no {prefix}*.fmg inside")
        for i in idx:
            fmgs.setdefault(i, read_fmg(bnd.datas[i]))
        base = next((i for i in idx if names[i].lower() == low + ".fmg"), idx[0])
        for tid, text in entries.items():
            wheres = [i for i in idx if tid in fmgs[i]]
            if not wheres and anchor and tid in anchor:
                wheres = [i for i in idx if anchor[tid] in fmgs[i]][:1]
            for where in wheres or [base]:
                fmgs[where][tid] = text
                changed.add(where)
                written[names[where]] = written.get(names[where], 0) + 1
    datas = list(bnd.datas)
    for i in changed:
        datas[i] = write_fmg(fmgs[i])
    data = erreg.write_bnd4(erreg.Bnd4(bnd.head, bnd.files, datas, bnd.file_header_size,
                                       bnd.has_compression, bnd.long_offsets))
    return erreg.write_dcx(erreg.Dcx(9, data, erreg.CODEC_DEFLATE)), written
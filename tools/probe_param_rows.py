#!/usr/bin/env python3
"""Read-only reconnaissance for the runtime ShopLineupParam row geometry.

The static scanner (verify_aobs.py) proves where the ParamRepository singleton slot lives, but the
offset from the live repository object to its param array is only visible in process memory.  This
tool attaches to a running Elden Ring, follows that slot, and reports candidate array bases and the
two UTF-16 name anchors.  It NEVER writes to the process: OpenProcess asks only for VM_READ and
QUERY_INFORMATION, and every address is checked with VirtualQueryEx before a read.

    python tools/probe_param_rows.py                 # auto-detect eldenring.exe
    python tools/probe_param_rows.py --pid 1234      # a specific process
    python tools/probe_param_rows.py --json          # machine-readable summary

The game must be running with a save loaded; before that the singleton slot may still be null.  Output
is evidence for filling [param] in shops_periodic.ini, not a claim that the DLL writes correctly.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import struct
from ctypes import wintypes

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
MEM_COMMIT = 0x00001000
PAGE_NOACCESS = 0x00000001
PAGE_GUARD = 0x00000100

# Verified against C:\Games\ELDEN RING\Game\eldenring.exe this session by tools/verify_aobs.py and
# by chasing the UTF-16 param-name table.  Override them if a future game build moves them.
SLOT_RVA = 0x03D87DB8
NAME_RVA = 0x02BB7E38
TABLE_RVA = 0x03B437B0
SHOP_PARAM_ID = 0x1A

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("glblcntUsage", wintypes.DWORD),
        ("proccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.c_size_t),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", ctypes.c_size_t),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * 260),
    ]


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_size_t),
        ("AllocationBase", ctypes.c_size_t),
        ("AllocationProtect", wintypes.DWORD),
        ("PartitionId", wintypes.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


def find_process(name: str) -> int | None:
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == ctypes.c_void_p(-1).value:
        return None
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel32.Process32FirstW(snap, ctypes.byref(entry)):
            return None
        while True:
            if entry.szExeFile.lower() == name.lower():
                return int(entry.th32ProcessID)
            if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                return None
    finally:
        kernel32.CloseHandle(snap)


def module_base(pid: int, name: str) -> tuple[int, int] | None:
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == ctypes.c_void_p(-1).value:
        return None
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if not kernel32.Module32FirstW(snap, ctypes.byref(entry)):
            return None
        while True:
            if entry.szModule.lower() == name.lower():
                return int(entry.modBaseAddr), int(entry.modBaseSize)
            if not kernel32.Module32NextW(snap, ctypes.byref(entry)):
                return None
    finally:
        kernel32.CloseHandle(snap)


class ProcessReader:
    """Small read-only wrapper: cached page rights plus bounded ReadProcessMemory."""

    def __init__(self, handle: int) -> None:
        self.handle = handle
        self._pages: dict[int, bool] = {}
        self._regions: dict[int, tuple[int, int]] = {}

    def region(self, address: int) -> tuple[int, int] | None:
        page = address >> 12
        if page in self._regions:
            return self._regions[page]
        info = MEMORY_BASIC_INFORMATION()
        got = kernel32.VirtualQueryEx(self.handle, ctypes.c_void_p(address),
                                      ctypes.byref(info), ctypes.sizeof(info))
        if got == 0:
            self._regions[page] = None
            return None
        region = (int(info.BaseAddress), int(info.RegionSize))
        self._regions[page] = region
        return region

    def readable(self, address: int, size: int = 8) -> bool:
        if address == 0 or size == 0:
            return False
        key = address >> 12
        cached = self._pages.get(key)
        if cached is not None and not cached:
            return False
        region = self.region(address)
        if region is None:
            self._pages[key] = False
            return False
        base, length = region
        if not (base <= address and address + size <= base + length):
            self._pages[key] = False
            return False
        info = MEMORY_BASIC_INFORMATION()
        if kernel32.VirtualQueryEx(self.handle, ctypes.c_void_p(address),
                                   ctypes.byref(info), ctypes.sizeof(info)) == 0:
            self._pages[key] = False
            return False
        ok = info.State == MEM_COMMIT and (info.Protect & PAGE_NOACCESS) == 0
        if info.Protect & PAGE_GUARD:
            ok = False
        self._pages[key] = ok
        return ok

    def read(self, address: int, size: int) -> bytes:
        if size <= 0 or not self.readable(address, size):
            return b""
        buffer = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        ok = kernel32.ReadProcessMemory(self.handle, ctypes.c_void_p(address), buffer,
                                        size, ctypes.byref(got))
        return buffer.raw[:got.value] if ok else b""

    def u64(self, address: int) -> int:
        raw = self.read(address, 8)
        return struct.unpack("<Q", raw)[0] if len(raw) == 8 else 0

    def window(self, address: int, maximum: int) -> tuple[int, bytes]:
        region = self.region(address)
        if region is None:
            return address, b""
        base, length = region
        size = min(maximum, max(0, base + length - address))
        # A region can be large; never ask ReadProcessMemory for more than one page at a time.
        chunks: list[bytes] = []
        done = 0
        while done < size:
            piece = self.read(address + done, min(4096, size - done))
            if not piece:
                break
            chunks.append(piece)
            done += len(piece)
        return address, b"".join(chunks)


def hexdump(data: bytes, base: int, limit: int = 96) -> list[str]:
    lines = []
    for offset in range(0, min(len(data), limit), 16):
        chunk = data[offset:offset + 16]
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{base + offset:016x}  {chunk.hex(' '):<47}  {text}")
    return lines


def probe(reader: ProcessReader, module: int, param_id: int, limit: int) -> dict:
    result: dict = {
        "module_base": module,
        "slot_rva": SLOT_RVA,
        "slot_address": module + SLOT_RVA,
        "param_id": param_id,
        "warnings": [],
    }
    slot = reader.u64(module + SLOT_RVA)
    result["repository"] = slot
    if slot == 0:
        result["warnings"].append("singleton slot is null - load a save before probing")
        return result

    # Cross-check the static name table in live memory before trusting its index.
    entry = module + TABLE_RVA + param_id * 16
    live_id = reader.u64(entry)
    live_name = reader.u64(entry + 8)
    expected_name = module + NAME_RVA
    result["name_table"] = {
        "entry": entry,
        "id": live_id,
        "name_pointer": live_name,
        "expected_name_pointer": expected_name,
        "matches": live_id == param_id and live_name == expected_name,
    }
    if not result["name_table"]["matches"]:
        result["warnings"].append("param-name table does not match this build - geometry below is unverified")

    start, blob = reader.window(slot, 1 << 18)
    result["window"] = {"address": start, "bytes": len(blob)}
    if not blob:
        result["warnings"].append("repository memory is not readable")
        return result

    anchors = {
        "name_string": expected_name,
        "name_entry": entry,
        "name_pointer_slot": entry + 8,
    }
    hits: dict[str, list[int]] = {key: [] for key in anchors}
    for offset in range(0, len(blob) - 7, 8):
        value = struct.unpack_from("<Q", blob, offset)[0]
        for key, wanted in anchors.items():
            if value == wanted and len(hits[key]) < limit:
                hits[key].append(start + offset)
    result["anchor_hits"] = hits

    # Candidate pointer arrays: at base+i*8 the i-th entry is a readable pointer.  The param-id
    # slot must also be a readable pointer.  Rank by how many of the first 32 entries look valid.
    candidates: list[dict] = []
    stride_bytes = 8
    need = max(param_id + 1, 8) * stride_bytes
    for offset in range(0, len(blob) - need, stride_bytes):
        first = struct.unpack_from("<Q", blob, offset)[0]
        target = struct.unpack_from("<Q", blob, offset + param_id * stride_bytes)[0]
        if not (reader.readable(first, 8) and reader.readable(target, 8)):
            continue
        valid = 0
        for i in range(min(32, param_id + 1)):
            value = struct.unpack_from("<Q", blob, offset + i * stride_bytes)[0]
            if reader.readable(value, 8):
                valid += 1
        candidates.append({
            "offset_from_repository": offset,
            "address": start + offset,
            "param_pointer": target,
            "readable_prefix": valid,
        })
    candidates.sort(key=lambda c: (-c["readable_prefix"], c["offset_from_repository"]))
    result["array_candidates"] = candidates[:limit]
    result["dump"] = hexdump(blob, start, limit)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--process", default="eldenring.exe", help="game process name")
    ap.add_argument("--pid", type=int, help="probe a specific process id")
    ap.add_argument("--param-id", type=int, default=SHOP_PARAM_ID,
                    help=f"param index to look for (default {SHOP_PARAM_ID:#x})")
    ap.add_argument("--limit", type=int, default=12, help="maximum candidates / dump lines to print")
    ap.add_argument("--json", action="store_true", help="emit a JSON summary")
    args = ap.parse_args(argv)

    pid = args.pid or find_process(args.process)
    if pid is None:
        print(f"# error: {args.process} is not running (start the game and load a save)")
        return 1
    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        print(f"# error: OpenProcess({pid}) failed with Win32 error {ctypes.get_last_error()}")
        return 1
    try:
        found = module_base(pid, args.process)
        if found is None:
            print(f"# error: cannot find the {args.process} module in pid {pid}")
            return 1
        module, _size = found
        reader = ProcessReader(handle)
        result = probe(reader, module, args.param_id, args.limit)
    finally:
        kernel32.CloseHandle(handle)

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    print(f"# pid {pid}, module {module:#x}, param id {args.param_id:#x}")
    print(f"# singleton slot {result['slot_address']:#x} -> ParamRepository {result['repository']:#x}")
    table = result.get("name_table")
    if table:
        print(f"# name entry {table['entry']:#x}: id={table['id']:#x}, "
              f"name={table['name_pointer']:#x} (expected {table['expected_name_pointer']:#x}), "
              f"matches={table['matches']}")
    window = result.get("window", {})
    print(f"# scanned {window.get('bytes', 0):,} bytes from {window.get('address', 0):#x}")
    for warning in result["warnings"]:
        print(f"# warning: {warning}")
    for key, addresses in result.get("anchor_hits", {}).items():
        print(f"  anchor {key}: " + (", ".join(hex(a) for a in addresses) if addresses else "none"))
    for candidate in result.get("array_candidates", []):
        print(f"  candidate: repo+{candidate['offset_from_repository']:#x} -> "
              f"param {candidate['param_pointer']:#x}, readable prefix {candidate['readable_prefix']}/32")
    print("  repository head:")
    for line in result.get("dump", []):
        print("    " + line)
    print("# read-only probe: no game memory was modified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

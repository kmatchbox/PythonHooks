#!/usr/bin/env python3
"""
qt_metadata.py — Read and write QuickTime metadata keys in .mov and .mp4 files.

Supports the Apple QuickTime metadata key namespace, e.g.:
    com.apple.quicktime.comment
    com.apple.quicktime.description
    com.apple.quicktime.title
    ... and any other com.apple.quicktime.* key

QuickTime Metadata specification:
    https://developer.apple.com/documentation/quicktime-file-format/quicktime_metadata_keys

Both .mov and .mp4 / .m4v / .m4a files are supported.  The script handles:
  - MOV:  moov → udta → meta (version/flags) → keys + ilst
  - MP4:  moov → udta → meta  OR  moov → meta  (both locations checked)
  - stco / co64 chunk-offset fixup so media data is never corrupted
  - 'free' padding atom reuse to minimise rewrites
  - Streaming writes: mdat and other large atoms are NEVER loaded into RAM.
    Only the moov atom (metadata/index, typically <1 MB) is parsed fully.
    The file is written by streaming large atoms directly from the source.

Usage (CLI):
    python qt_metadata.py read  input.mov
    python qt_metadata.py read  input.mp4
    python qt_metadata.py read  input.mp4 com.apple.quicktime.comment
    python qt_metadata.py write input.mp4 com.apple.quicktime.comment "Hello"
    python qt_metadata.py write input.mp4 com.apple.quicktime.comment "Hello" --output out.mp4
    python qt_metadata.py remove input.mp4 com.apple.quicktime.comment

Usage (API):
    from qt_metadata import QuickTimeFile

    qt = QuickTimeFile("input.mp4")
    print(qt.get_metadata("com.apple.quicktime.comment"))
    qt.set_metadata("com.apple.quicktime.comment", "My comment")
    qt.save("output.mp4")   # or qt.save() to overwrite in place
"""

import struct
import os
import sys
import shutil
import tempfile
import argparse
from typing import Optional, Dict, List, Tuple, Any

# ---------------------------------------------------------------------------
# Type-indicator constants  (Table 2-4 of the QT file format spec)
# ---------------------------------------------------------------------------
TYPE_BINARY  = 0
TYPE_UTF8    = 1
TYPE_UTF16   = 2
TYPE_JPEG    = 13
TYPE_PNG     = 14
TYPE_FLOAT32 = 23
TYPE_FLOAT64 = 24
TYPE_INT8    = 65
TYPE_INT16   = 66
TYPE_INT32   = 67
TYPE_INT64   = 74
TYPE_UINT8   = 75
TYPE_UINT16  = 76
TYPE_UINT32  = 77
TYPE_UINT64  = 78

APPLE_QT_NAMESPACE = b"mdta"

# Atoms whose payload is purely child atoms (no version/flags prefix).
# 'meta' is intentionally absent — it has a 4-byte prefix before its children.
CONTAINER_ATOMS = {
    b"moov", b"trak", b"mdia", b"minf", b"dinf", b"stbl",
    b"udta", b"ilst", b"edts",
}

# Atoms that can be very large (mdat is the video/audio payload).
# We NEVER read their payload into RAM; we stream them on write.
STREAM_ATOMS = {b"mdat", b"wide"}

_COPY_CHUNK = 1 << 20   # 1 MiB copy buffer


# ---------------------------------------------------------------------------
# Low-level binary helpers
# ---------------------------------------------------------------------------

def read_atom_header(stream) -> Optional[Tuple[int, bytes, int]]:
    """Read one atom header.  Returns (total_size, type, header_size) or None."""
    raw = stream.read(8)
    if len(raw) < 8:
        return None
    size32, atom_type = struct.unpack(">I4s", raw)
    if size32 == 1:
        ext = stream.read(8)
        if len(ext) < 8:
            return None
        return struct.unpack(">Q", ext)[0], atom_type, 16
    if size32 == 0:
        cur = stream.tell() - 8
        stream.seek(0, 2)
        eof = stream.tell()
        stream.seek(cur + 8)
        return eof - cur, atom_type, 8
    return size32, atom_type, 8


def iter_atoms(stream, end_offset: int):
    """Yield (offset, size, atom_type, header_size) for atoms up to end_offset."""
    while stream.tell() < end_offset:
        offset = stream.tell()
        hdr = read_atom_header(stream)
        if hdr is None:
            break
        size, atom_type, header_size = hdr
        if size < header_size:
            break
        yield offset, size, atom_type, header_size
        stream.seek(offset + size)


# ---------------------------------------------------------------------------
# Atom classes
# ---------------------------------------------------------------------------

class Atom:
    """
    Generic small atom — payload stored in memory.
    Never used for mdat or other large atoms.
    """
    __slots__ = ("offset", "size", "atom_type", "header_size", "payload")

    def __init__(self, offset, size, atom_type, header_size, payload: bytes):
        self.offset      = offset
        self.size        = size
        self.atom_type   = atom_type
        self.header_size = header_size
        self.payload     = payload

    def serialize(self) -> bytes:
        total = 8 + len(self.payload)
        return struct.pack(">I4s", total, self.atom_type) + self.payload

    def write_to(self, out_stream) -> None:
        out_stream.write(self.serialize())

    def __repr__(self):
        return f"<Atom {self.atom_type!r} size={self.size}>"


class PassthroughAtom(Atom):
    """
    Large atom (typically mdat) whose payload is NEVER loaded into RAM.
    On write, the bytes are streamed directly from the source file.
    """
    __slots__ = ("offset", "size", "atom_type", "header_size", "payload",
                 "_src_path", "_payload_offset", "_payload_size")

    def __init__(self, offset, size, atom_type, header_size,
                 src_path: str, payload_offset: int, payload_size: int):
        super().__init__(offset, size, atom_type, header_size, b"")
        self._src_path      = src_path
        self._payload_offset = payload_offset
        self._payload_size   = payload_size

    def serialize(self) -> bytes:
        # Materialise only when explicitly requested (e.g. in tests).
        # Normal save() uses write_to() which streams instead.
        with open(self._src_path, "rb") as f:
            f.seek(self._payload_offset)
            payload = f.read(self._payload_size)
        total = self._payload_size + self.header_size
        if self.header_size == 16:
            hdr = struct.pack(">I4sQ", 1, self.atom_type, total)
        else:
            hdr = struct.pack(">I4s", total, self.atom_type)
        return hdr + payload

    def write_to(self, out_stream) -> None:
        """Stream the atom header + payload to out_stream without loading all of it.
        Preserves extended 64-bit size headers (header_size=16) exactly as found."""
        total_size = self._payload_size + self.header_size
        if self.header_size == 16:
            # Extended 64-bit size: size32=1, type, then 8-byte size64
            out_stream.write(struct.pack(">I4sQ", 1, self.atom_type, total_size))
        else:
            # Standard 8-byte header
            out_stream.write(struct.pack(">I4s", total_size, self.atom_type))
        remaining = self._payload_size
        with open(self._src_path, "rb") as src:
            src.seek(self._payload_offset)
            while remaining > 0:
                chunk = src.read(min(_COPY_CHUNK, remaining))
                if not chunk:
                    break
                out_stream.write(chunk)
                remaining -= len(chunk)

    def __repr__(self):
        return f"<PassthroughAtom {self.atom_type!r} size={self.size}>"


class ContainerAtom(Atom):
    """Atom whose payload is entirely child atoms."""

    def __init__(self, offset, size, atom_type, header_size, children):
        super().__init__(offset, size, atom_type, header_size, b"")
        self.children: List[Atom] = children

    def find(self, atom_type: bytes) -> List[Atom]:
        return [c for c in self.children if c.atom_type == atom_type]

    def find_first(self, atom_type: bytes) -> Optional[Atom]:
        r = self.find(atom_type)
        return r[0] if r else None

    def serialize(self) -> bytes:
        child_bytes = b"".join(c.serialize() for c in self.children)
        return struct.pack(">I4s", 8 + len(child_bytes), self.atom_type) + child_bytes

    def write_to(self, out_stream) -> None:
        out_stream.write(self.serialize())

    def __repr__(self):
        return f"<ContainerAtom {self.atom_type!r} children={len(self.children)}>"


class MetaAtom(ContainerAtom):
    """meta atom: 4-byte version/flags prefix before children."""

    def __init__(self, offset, size, atom_type, header_size, version_flags, children):
        super().__init__(offset, size, atom_type, header_size, children)
        self.version_flags: bytes = version_flags

    def serialize(self) -> bytes:
        child_bytes = b"".join(c.serialize() for c in self.children)
        total = 8 + 4 + len(child_bytes)
        return struct.pack(">I4s", total, self.atom_type) + self.version_flags + child_bytes

    def write_to(self, out_stream) -> None:
        out_stream.write(self.serialize())


# ---------------------------------------------------------------------------
# Atom reader
# ---------------------------------------------------------------------------

def read_atom(stream, offset: int, size: int, atom_type: bytes,
              header_size: int, src_path: str) -> Atom:
    payload_offset = offset + header_size
    payload_size   = size   - header_size

    if atom_type in STREAM_ATOMS:
        # Never read the payload — record location for streaming on write.
        return PassthroughAtom(offset, size, atom_type, header_size,
                               src_path, payload_offset, payload_size)

    if atom_type == b"meta":
        stream.seek(payload_offset)
        raw_vf = stream.read(4)
        vf = raw_vf if len(raw_vf) == 4 else b"\x00\x00\x00\x00"
        children = _read_children(stream, payload_offset + 4, offset + size, src_path)
        return MetaAtom(offset, size, atom_type, header_size, vf, children)

    if atom_type in CONTAINER_ATOMS:
        children = _read_children(stream, payload_offset, offset + size, src_path)
        return ContainerAtom(offset, size, atom_type, header_size, children)

    # Small atom — read fully into memory.
    stream.seek(payload_offset)
    payload = stream.read(payload_size)
    return Atom(offset, size, atom_type, header_size, payload)


def _read_children(stream, start: int, end: int, src_path: str) -> List[Atom]:
    children = []
    stream.seek(start)
    for c_off, c_size, c_type, c_hdr in iter_atoms(stream, end):
        child = read_atom(stream, c_off, c_size, c_type, c_hdr, src_path)
        children.append(child)
        stream.seek(c_off + c_size)
    return children


def read_top_level(stream, src_path: str) -> List[Atom]:
    """Read all top-level atoms.  Large atoms (mdat) are not loaded into RAM."""
    stream.seek(0, 2)
    file_size = stream.tell()
    stream.seek(0)
    atoms: List[Atom] = []
    for offset, size, atom_type, header_size in iter_atoms(stream, file_size):
        atom = read_atom(stream, offset, size, atom_type, header_size, src_path)
        atoms.append(atom)
        stream.seek(offset + size)
    return atoms


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def detect_format(atoms: List[Atom]) -> str:
    for a in atoms:
        if a.atom_type == b"ftyp":
            brand = a.payload[:4] if len(a.payload) >= 4 else b""
            return "mov" if brand == b"qt  " else "mp4"
    return "mov"


# ---------------------------------------------------------------------------
# Metadata key / value codec
# ---------------------------------------------------------------------------

def parse_keys_atom(payload: bytes) -> List[Tuple[bytes, bytes]]:
    if len(payload) < 8:
        return []
    entry_count = struct.unpack_from(">I", payload, 4)[0]
    pos, keys = 8, []
    for _ in range(entry_count):
        if pos + 8 > len(payload):
            break
        key_size  = struct.unpack_from(">I", payload, pos)[0]
        namespace = payload[pos+4:pos+8]
        key_value = payload[pos+8:pos+key_size]
        keys.append((namespace, key_value))
        pos += key_size
    return keys


def build_keys_atom(keys: List[Tuple[bytes, bytes]]) -> bytes:
    entries = b"".join(
        struct.pack(">I", 8 + len(kv)) + ns + kv for ns, kv in keys)
    inner = b"\x00\x00\x00\x00" + struct.pack(">I", len(keys)) + entries
    return struct.pack(">I4s", 8 + len(inner), b"keys") + inner


def _find_data_atoms_in_payload(payload: bytes) -> List[Atom]:
    result, pos = [], 0
    while pos + 8 <= len(payload):
        size  = struct.unpack_from(">I", payload, pos)[0]
        atype = payload[pos+4:pos+8]
        if size < 8:
            break
        if atype == b"data":
            result.append(Atom(0, size, atype, 8, payload[pos+8:pos+size]))
        pos += size
    return result


def parse_ilst_children(payload: bytes) -> List[Atom]:
    children, pos = [], 0
    while pos + 8 <= len(payload):
        size  = struct.unpack_from(">I", payload, pos)[0]
        atype = payload[pos+4:pos+8]
        if size < 8:
            break
        data_children = _find_data_atoms_in_payload(payload[pos+8:pos+size])
        children.append(ContainerAtom(0, size, atype, 8, data_children))
        pos += size
    return children


def parse_ilst_values(children: List[Atom], key_count: int) -> Dict[int, bytes]:
    values: Dict[int, bytes] = {}
    for child in children:
        key_index = struct.unpack(">I", child.atom_type)[0]
        if not (1 <= key_index <= key_count):
            continue
        da_list = (child.find(b"data") if isinstance(child, ContainerAtom)
                   else _find_data_atoms_in_payload(child.payload))
        for da in da_list:
            if isinstance(da, Atom) and len(da.payload) >= 8:
                values[key_index] = da.payload
                break
    return values


def decode_data_atom(raw_payload: bytes) -> Tuple[int, Any]:
    if len(raw_payload) < 8:
        return TYPE_BINARY, raw_payload
    ti = struct.unpack_from(">I", raw_payload, 0)[0]
    vb = raw_payload[8:]
    if ti == TYPE_UTF8:   return ti, vb.decode("utf-8",    errors="replace")
    if ti == TYPE_UTF16:  return ti, vb.decode("utf-16-be", errors="replace")
    if ti == TYPE_INT8:   return ti, struct.unpack_from(">b", vb)[0]  if vb             else 0
    if ti == TYPE_INT16:  return ti, struct.unpack_from(">h", vb)[0]  if len(vb) >= 2   else 0
    if ti == TYPE_INT32:  return ti, struct.unpack_from(">i", vb)[0]  if len(vb) >= 4   else 0
    if ti == TYPE_INT64:  return ti, struct.unpack_from(">q", vb)[0]  if len(vb) >= 8   else 0
    if ti == TYPE_UINT8:  return ti, struct.unpack_from(">B", vb)[0]  if vb             else 0
    if ti == TYPE_UINT16: return ti, struct.unpack_from(">H", vb)[0]  if len(vb) >= 2   else 0
    if ti == TYPE_UINT32: return ti, struct.unpack_from(">I", vb)[0]  if len(vb) >= 4   else 0
    if ti == TYPE_UINT64: return ti, struct.unpack_from(">Q", vb)[0]  if len(vb) >= 8   else 0
    if ti == TYPE_FLOAT32:return ti, struct.unpack_from(">f", vb)[0]  if len(vb) >= 4   else 0.0
    if ti == TYPE_FLOAT64:return ti, struct.unpack_from(">d", vb)[0]  if len(vb) >= 8   else 0.0
    return ti, vb


def encode_data_atom(value: Any, type_indicator: int = TYPE_UTF8) -> bytes:
    locale = b"\x00\x00\x00\x00"
    ti = type_indicator
    if   ti == TYPE_UTF8:   enc = (value.encode("utf-8")    if isinstance(value, str) else bytes(value))
    elif ti == TYPE_UTF16:  enc = (value.encode("utf-16-be") if isinstance(value, str) else bytes(value))
    elif ti == TYPE_INT8:   enc = struct.pack(">b", int(value))
    elif ti == TYPE_INT16:  enc = struct.pack(">h", int(value))
    elif ti == TYPE_INT32:  enc = struct.pack(">i", int(value))
    elif ti == TYPE_INT64:  enc = struct.pack(">q", int(value))
    elif ti == TYPE_UINT8:  enc = struct.pack(">B", int(value))
    elif ti == TYPE_UINT16: enc = struct.pack(">H", int(value))
    elif ti == TYPE_UINT32: enc = struct.pack(">I", int(value))
    elif ti == TYPE_UINT64: enc = struct.pack(">Q", int(value))
    elif ti == TYPE_FLOAT32:enc = struct.pack(">f", float(value))
    elif ti == TYPE_FLOAT64:enc = struct.pack(">d", float(value))
    else: enc = value if isinstance(value, (bytes, bytearray)) else str(value).encode("utf-8")
    inner = struct.pack(">I", ti) + locale + enc
    return struct.pack(">I4s", 8 + len(inner), b"data") + inner


def build_ilst_bytes(keys: List[Tuple[bytes, bytes]],
                     values: Dict[int, bytes]) -> bytes:
    entries = b""
    for idx, data_payload in sorted(values.items()):
        child_type = struct.pack(">I", idx)
        data_atom  = struct.pack(">I4s", 8 + len(data_payload), b"data") + data_payload
        entries   += struct.pack(">I4s", 8 + len(data_atom), child_type) + data_atom
    return struct.pack(">I4s", 8 + len(entries), b"ilst") + entries


def build_hdlr_atom() -> bytes:
    """
    Build an hdlr atom declaring handler_type='mdta' (Apple QuickTime metadata).

    Required as the first child of meta by ISO 14496-12 and enforced by
    macOS 26+ / QuickTime Player.  Structure (33 bytes):
      4  version+flags (0)
      4  pre_defined   (0)
      4  handler_type  ('mdta')
      12 reserved      (0)
      1  name          ('\x00'  — empty null-terminated string)
    """
    payload = (
        b"\x00\x00\x00\x00"   # version + flags
        b"\x00\x00\x00\x00"   # pre_defined
        b"mdta"                   # handler_type
        b"\x00\x00\x00\x00"   # reserved[0]
        b"\x00\x00\x00\x00"   # reserved[1]
        b"\x00\x00\x00\x00"   # reserved[2]
        b"\x00"                  # name (empty, null-terminated)
    )
    return struct.pack(">I4s", 8 + len(payload), b"hdlr") + payload


# ---------------------------------------------------------------------------
# Size measurement
# ---------------------------------------------------------------------------

def _measure(atom: Atom) -> int:
    if isinstance(atom, MetaAtom):
        return 8 + 4 + sum(_measure(c) for c in atom.children)
    if isinstance(atom, ContainerAtom):
        return 8 + sum(_measure(c) for c in atom.children)
    if isinstance(atom, PassthroughAtom):
        return atom.header_size + atom._payload_size
    return 8 + len(atom.payload)


# ---------------------------------------------------------------------------
# stco / co64 fixup — operates on serialised moov bytes only
# ---------------------------------------------------------------------------

def _patch_stco_co64(moov_bytes: bytearray, delta: int) -> None:
    """
    Adjust every stco/co64 entry in the serialised moov bytes by *delta*.
    Only moov bytes are passed in; we never touch mdat.
    """
    def _scan(pos: int, end: int) -> None:
        while pos + 8 <= end:
            size32 = struct.unpack_from(">I", moov_bytes, pos)[0]
            atype  = moov_bytes[pos+4:pos+8]
            size   = (struct.unpack_from(">Q", moov_bytes, pos+8)[0] if size32 == 1
                      else (end - pos if size32 == 0 else size32))
            hdr    = 16 if size32 == 1 else 8
            if size < hdr or pos + size > end:
                break

            if atype == b"stco":
                pay = pos + hdr
                if pay + 8 <= end:
                    count = struct.unpack_from(">I", moov_bytes, pay + 4)[0]
                    for i in range(count):
                        o = pay + 8 + i * 4
                        if o + 4 > end: break
                        old = struct.unpack_from(">I", moov_bytes, o)[0]
                        struct.pack_into(">I", moov_bytes, o, (old + delta) & 0xFFFFFFFF)

            elif atype == b"co64":
                pay = pos + hdr
                if pay + 8 <= end:
                    count = struct.unpack_from(">I", moov_bytes, pay + 4)[0]
                    for i in range(count):
                        o = pay + 8 + i * 8
                        if o + 8 > end: break
                        old = struct.unpack_from(">Q", moov_bytes, o)[0]
                        struct.pack_into(">Q", moov_bytes, o, old + delta)

            elif atype in (b"moov", b"trak", b"mdia", b"minf", b"stbl",
                           b"udta", b"edts", b"dinf"):
                _scan(pos + hdr, pos + size)

            pos += size

    _scan(0, len(moov_bytes))


# ---------------------------------------------------------------------------
# High-level QuickTimeFile class
# ---------------------------------------------------------------------------

class QuickTimeFile:
    """
    Read and write QuickTime / MPEG-4 metadata keys.
    Supports .mov, .mp4, .m4v, .m4a.
    mdat is never loaded into RAM — only moov is parsed.

    Example
    -------
    qt = QuickTimeFile("clip.mp4")
    print(qt.get_metadata("com.apple.quicktime.comment"))
    qt.set_metadata("com.apple.quicktime.comment", "Nice shot!")
    qt.save("clip_tagged.mp4")   # or qt.save() to overwrite in place
    """

    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        with open(self.path, "rb") as f:
            self._atoms: List[Atom] = read_top_level(f, self.path)
        self.format: str = detect_format(self._atoms)
        _m = self._moov()
        # True on-disk moov size — never modified by set_metadata().
        # Used by save() to compute the offset delta for stco/co64 fixup.
        self._disk_moov_size: int = _m.size if _m is not None else 0

    # ------------------------------------------------------------------
    # Internal navigation
    # ------------------------------------------------------------------

    def _moov(self) -> Optional[ContainerAtom]:
        for a in self._atoms:
            if a.atom_type == b"moov" and isinstance(a, ContainerAtom):
                return a
        return None

    def _find_meta(self, moov: ContainerAtom) -> Optional[MetaAtom]:
        # moov → udta → meta  (standard)
        udta = moov.find_first(b"udta")
        if udta and isinstance(udta, ContainerAtom):
            for c in udta.children:
                if c.atom_type == b"meta" and isinstance(c, MetaAtom):
                    return c
        # moov → meta  (some MP4 encoders)
        for c in moov.children:
            if c.atom_type == b"meta" and isinstance(c, MetaAtom):
                return c
        return None

    def _ensure_meta(self, moov: ContainerAtom) -> MetaAtom:
        meta = self._find_meta(moov)
        if meta is not None:
            return meta
        udta = moov.find_first(b"udta")
        if udta is None or not isinstance(udta, ContainerAtom):
            udta = ContainerAtom(0, 8, b"udta", 8, [])
            moov.children.append(udta)
        hdlr_bytes = build_hdlr_atom()
        hdlr_atom  = Atom(0, len(hdlr_bytes), b"hdlr", 8, hdlr_bytes[8:])
        meta = MetaAtom(0, 8, b"meta", 8, b"\x00\x00\x00\x00", [hdlr_atom])
        udta.children.append(meta)
        return meta

    def _parse_meta(self, meta: MetaAtom
                    ) -> Tuple[List[Tuple[bytes, bytes]], Dict[int, bytes]]:
        keys_atom = meta.find_first(b"keys")
        keys: List[Tuple[bytes, bytes]] = []
        if keys_atom is not None:
            keys = parse_keys_atom(keys_atom.payload)
        values: Dict[int, bytes] = {}
        for c in meta.children:
            if c.atom_type == b"ilst":
                ch = (c.children if isinstance(c, ContainerAtom)
                      else parse_ilst_children(c.payload))
                values = parse_ilst_values(ch, len(keys))
                break
        return keys, values

    def _write_meta(self, meta: MetaAtom,
                    keys: List[Tuple[bytes, bytes]],
                    values: Dict[int, bytes]) -> None:
        new_keys_bytes = build_keys_atom(keys)
        new_keys_atom  = Atom(0, len(new_keys_bytes), b"keys", 8, new_keys_bytes[8:])
        new_ilst_bytes    = build_ilst_bytes(keys, values)
        new_ilst_children = parse_ilst_children(new_ilst_bytes[8:])
        new_ilst_atom     = ContainerAtom(0, len(new_ilst_bytes), b"ilst", 8,
                                          new_ilst_children)

        # Preserve the hdlr child (required first child of meta per ISO 14496-12).
        # If none exists yet, create one — this fixes files that were written
        # without hdlr (accepted by macOS ≤15 but rejected by macOS 26+).
        hdlr = next((c for c in meta.children if c.atom_type == b"hdlr"), None)
        if hdlr is None:
            hdlr_bytes = build_hdlr_atom()
            hdlr = Atom(0, len(hdlr_bytes), b"hdlr", 8, hdlr_bytes[8:])

        # Rebuild children: hdlr first, then keys, then ilst, drop old copies.
        other = [c for c in meta.children
                 if c.atom_type not in (b"hdlr", b"keys", b"ilst")]
        meta.children = [hdlr] + other + [new_keys_atom, new_ilst_atom]

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def all_metadata(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        moov = self._moov()
        if not moov:
            return result
        meta = self._find_meta(moov)
        if not meta:
            return result
        keys, values = self._parse_meta(meta)
        for i, (ns, kv) in enumerate(keys, start=1):
            if i in values:
                _, v = decode_data_atom(values[i])
                result[kv.decode("utf-8", errors="replace")] = v
        return result

    def get_metadata(self, key: str) -> Optional[Any]:
        return self.all_metadata().get(key)

    # ------------------------------------------------------------------
    # Public write API
    # ------------------------------------------------------------------

    def set_metadata(self, key: str, value: Any,
                     type_indicator: int = TYPE_UTF8) -> None:
        moov = self._moov()
        if moov is None:
            raise ValueError("No 'moov' atom — not a valid QuickTime/MP4 file.")
        meta         = self._ensure_meta(moov)
        keys, values = self._parse_meta(meta)
        key_bytes = key.encode("utf-8")
        idx: Optional[int] = None
        for i, (ns, kv) in enumerate(keys, start=1):
            if kv == key_bytes:
                idx = i; break
        if idx is None:
            keys.append((APPLE_QT_NAMESPACE, key_bytes))
            idx = len(keys)
        values[idx] = encode_data_atom(value, type_indicator)[8:]
        self._write_meta(meta, keys, values)

    def set_multiple_metadata(self, entries: Dict[str, Any],
                               type_indicators: Optional[Dict[str, int]] = None) -> None:
        ti = type_indicators or {}
        for key, val in entries.items():
            self.set_metadata(key, val, ti.get(key, TYPE_UTF8))

    def remove_metadata(self, key: str) -> bool:
        moov = self._moov()
        if not moov: return False
        meta = self._find_meta(moov)
        if not meta: return False
        keys, values = self._parse_meta(meta)
        key_bytes = key.encode("utf-8")
        found_idx: Optional[int] = None
        for i, (ns, kv) in enumerate(keys, start=1):
            if kv == key_bytes:
                found_idx = i; break
        if found_idx is None:
            return False
        new_keys, new_values, new_i = [], {}, 0
        for old_i, (ns, kv) in enumerate(keys, start=1):
            if old_i == found_idx: continue
            new_i += 1
            new_keys.append((ns, kv))
            if old_i in values:
                new_values[new_i] = values[old_i]
        self._write_meta(meta, new_keys, new_values)
        return True

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self, output_path: Optional[str] = None) -> None:
        """
        Write the file to *output_path* (or overwrite the source if None).

        Strategy
        --------
        1. Serialise moov (small, in memory) and compute its new size.
        2. Compute delta = new_moov_size - original_on_disk_moov_size.
        3. If delta != 0 and moov precedes mdat:
           a. If a 'free' padding atom follows moov and can absorb the delta,
              resize it so mdat does not move and stco/co64 need no adjustment.
           b. Otherwise patch stco/co64 in the serialised moov bytes.
        4. Write the file atom by atom, streaming mdat directly from the
           source file — it is never loaded into RAM.
        5. Re-read moov from the newly written file to refresh internal state
           (stco values, disk_moov_size) for any subsequent save() calls.
        """
        dest = os.path.abspath(output_path or self.path)
        moov = self._moov()

        # ── Serialise moov to bytes ──────────────────────────────────────────
        moov_bytes = bytearray(moov.serialize()) if moov is not None else None

        # ── Compute delta and patch stco/co64 if needed ──────────────────────
        if moov_bytes is not None and self._moov_before_mdat():
            new_moov_size = len(moov_bytes)
            delta = new_moov_size - self._disk_moov_size

            if delta != 0:
                free_atom = self._free_after_moov()

                if free_atom is not None:
                    new_free_size = free_atom.size - delta
                    if new_free_size == 0:
                        # Free atom exactly fills the gap — drop it.
                        self._atoms = [a for a in self._atoms if a is not free_atom]
                        free_atom = None
                        # delta absorbed; no stco fixup needed
                    elif new_free_size >= 8:
                        # Resize free atom — absorbed, no stco fixup.
                        free_atom.payload = b"\x00" * (new_free_size - 8)
                        free_atom.size    = new_free_size
                        # delta absorbed
                    else:
                        # Cannot resize to a valid atom — remove and include in delta.
                        effective_delta = delta + free_atom.size
                        self._atoms = [a for a in self._atoms if a is not free_atom]
                        free_atom = None
                        _patch_stco_co64(moov_bytes, effective_delta)
                else:
                    # No free atom — full stco/co64 fixup.
                    _patch_stco_co64(moov_bytes, delta)

        # ── Write atomically via temp file, streaming large atoms ────────────
        # IMPORTANT ORDERING: all atom.write_to() calls (including PassthroughAtom
        # which streams mdat by reading from self._src_path, which may be the same
        # file as dest) are completed and the output file is fully flushed and
        # closed BEFORE shutil.move replaces dest.  This is what makes
        # qt.save(same_path_as_source) safe — we finish reading the original
        # before we overwrite it.
        dest_dir = os.path.dirname(dest) or "."
        tmp_fd, tmp_path = tempfile.mkstemp(dir=dest_dir)
        try:
            with os.fdopen(tmp_fd, "wb") as out:
                for atom in self._atoms:
                    if moov_bytes is not None and atom.atom_type == b"moov":
                        out.write(moov_bytes)
                    else:
                        atom.write_to(out)
            # All reads from the original file are finished here.
            shutil.move(tmp_path, dest)
        except Exception:
            try: os.unlink(tmp_path)
            except OSError: pass
            raise

        self.path = dest

        # ── Refresh internal state from the file we just wrote ───────────────
        # Re-reading moov (only) ensures _disk_moov_size and stco values in the
        # atom tree exactly match what is on disk, making subsequent save()
        # calls correct without any manual sync arithmetic.
        with open(dest, "rb") as f:
            self._atoms = read_top_level(f, dest)
        _m = self._moov()
        self._disk_moov_size = _m.size if _m is not None else 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _moov_before_mdat(self) -> bool:
        for a in self._atoms:
            if a.atom_type == b"moov": return True
            if a.atom_type == b"mdat": return False
        return False

    def _free_after_moov(self) -> Optional[Atom]:
        found_moov = False
        for a in self._atoms:
            if a.atom_type == b"moov":
                found_moov = True
                continue
            if found_moov:
                if a.atom_type in (b"free", b"skip"):
                    return a
                break
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_read(args):
    qt = QuickTimeFile(args.input)
    metadata = qt.all_metadata()
    if args.key:
        val = metadata.get(args.key)
        if val is None:
            print(f"Key not found: {args.key}", file=sys.stderr); sys.exit(1)
        print(val)
    else:
        if not metadata:
            print("No QuickTime metadata found.")
        else:
            w = max(len(k) for k in metadata)
            for k, v in sorted(metadata.items()):
                print(f"  {k:<{w}}  =  {v!r}")


def cmd_write(args):
    qt = QuickTimeFile(args.input)
    qt.set_metadata(args.key, args.value)
    out = args.output or args.input
    qt.save(out)
    print(f"Written: {args.key!r} = {args.value!r}  →  {out}")


def cmd_remove(args):
    qt = QuickTimeFile(args.input)
    removed = qt.remove_metadata(args.key)
    if not removed:
        print(f"Key not found: {args.key}", file=sys.stderr); sys.exit(1)
    out = args.output or args.input
    qt.save(out)
    print(f"Removed {args.key!r}  →  {out}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Read / write QuickTime metadata keys in .mov and .mp4 files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s read  clip.mp4
  %(prog)s read  clip.mp4 com.apple.quicktime.comment
  %(prog)s write clip.mp4 com.apple.quicktime.comment "My comment"
  %(prog)s write clip.mp4 com.apple.quicktime.comment "My comment" --output out.mp4
  %(prog)s remove clip.mp4 com.apple.quicktime.comment
""")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("read",   help="Print metadata")
    r.add_argument("input")
    r.add_argument("key", nargs="?", default=None)
    r.set_defaults(func=cmd_read)

    w = sub.add_parser("write",  help="Set or add a metadata key")
    w.add_argument("input")
    w.add_argument("key")
    w.add_argument("value")
    w.add_argument("--output", "-o", default=None)
    w.set_defaults(func=cmd_write)

    rm = sub.add_parser("remove", help="Remove a metadata key")
    rm.add_argument("input")
    rm.add_argument("key")
    rm.add_argument("--output", "-o", default=None)
    rm.set_defaults(func=cmd_remove)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
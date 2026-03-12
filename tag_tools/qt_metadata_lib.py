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
  - MP4:  moov → udta → meta  OR  moov → meta  (both locations are checked)
  - stco / co64 chunk-offset fixup so media data is never corrupted after a
    moov size change
  - 'free' padding atom reuse to minimise full-file rewrites

Usage (CLI):
    # Read all metadata
    python qt_metadata.py read input.mov
    python qt_metadata.py read input.mp4

    # Read a specific key
    python qt_metadata.py read input.mp4 com.apple.quicktime.comment

    # Set / add a key  (writes in-place by default, or use --output)
    python qt_metadata.py write input.mp4 com.apple.quicktime.comment "Hello"
    python qt_metadata.py write input.mp4 com.apple.quicktime.comment "Hello" --output out.mp4

    # Remove a key
    python qt_metadata.py remove input.mp4 com.apple.quicktime.comment

Usage (API):
    from qt_metadata import QuickTimeFile

    qt = QuickTimeFile("input.mp4")
    print(qt.get_metadata("com.apple.quicktime.comment"))

    qt.set_metadata("com.apple.quicktime.comment", "My comment")
    qt.save("output.mp4")          # new file
    qt.save()                      # overwrite in-place

Written by Claude
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

# Namespace for Apple's reverse-DNS metadata keys
APPLE_QT_NAMESPACE = b"mdta"

# Atoms that act as pure containers (payload = child atoms only).
# 'meta' is NOT in this set — it needs special handling for its version/flags prefix.
CONTAINER_ATOMS = {
    b"moov", b"trak", b"mdia", b"minf", b"dinf", b"stbl",
    b"udta", b"ilst", b"edts",
}


# ---------------------------------------------------------------------------
# Low-level binary helpers
# ---------------------------------------------------------------------------

def read_atom_header(stream) -> Optional[Tuple[int, bytes, int]]:
    """
    Read one atom header from *stream*.
    Returns (total_size, atom_type, header_size) or None at EOF.
    """
    raw = stream.read(8)
    if len(raw) < 8:
        return None
    size32, atom_type = struct.unpack(">I4s", raw)
    if size32 == 1:                        # 64-bit extended size
        ext = stream.read(8)
        if len(ext) < 8:
            return None
        size64 = struct.unpack(">Q", ext)[0]
        return size64, atom_type, 16
    elif size32 == 0:                      # atom extends to EOF
        cur = stream.tell() - 8
        stream.seek(0, 2)
        eof = stream.tell()
        stream.seek(cur + 8)
        return eof - cur, atom_type, 8
    else:
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
            break  # malformed
        yield offset, size, atom_type, header_size
        stream.seek(offset + size)


# ---------------------------------------------------------------------------
# Atom data structures
# ---------------------------------------------------------------------------

class Atom:
    """Generic passthrough atom — stores its raw payload verbatim."""
    __slots__ = ("offset", "size", "atom_type", "header_size", "payload")

    def __init__(self, offset, size, atom_type, header_size, payload):
        self.offset      = offset
        self.size        = size
        self.atom_type   = atom_type
        self.header_size = header_size
        self.payload     = payload

    def serialize(self) -> bytes:
        data  = self.payload
        total = 8 + len(data)
        return struct.pack(">I4s", total, self.atom_type) + data

    def __repr__(self):
        return f"<Atom {self.atom_type!r} size={self.size} @{self.offset}>"


class ContainerAtom(Atom):
    """An atom whose payload is entirely child atoms."""

    def __init__(self, offset, size, atom_type, header_size, children):
        super().__init__(offset, size, atom_type, header_size, b"")
        self.children: List[Atom] = children

    def find(self, atom_type: bytes) -> List[Atom]:
        return [c for c in self.children if c.atom_type == atom_type]

    def find_first(self, atom_type: bytes) -> Optional[Atom]:
        found = self.find(atom_type)
        return found[0] if found else None

    def serialize(self) -> bytes:
        child_bytes = b"".join(c.serialize() for c in self.children)
        total = 8 + len(child_bytes)
        return struct.pack(">I4s", total, self.atom_type) + child_bytes

    def __repr__(self):
        return f"<ContainerAtom {self.atom_type!r} children={len(self.children)}>"


class MetaAtom(ContainerAtom):
    """
    The 'meta' atom has a 4-byte version/flags field before its children.
    This applies to both MOV and MP4 files.
    """
    def __init__(self, offset, size, atom_type, header_size, version_flags, children):
        super().__init__(offset, size, atom_type, header_size, children)
        self.version_flags: bytes = version_flags  # 4 bytes

    def serialize(self) -> bytes:
        child_bytes = b"".join(c.serialize() for c in self.children)
        total = 8 + 4 + len(child_bytes)
        return struct.pack(">I4s", total, self.atom_type) + self.version_flags + child_bytes


# ---------------------------------------------------------------------------
# Atom reader
# ---------------------------------------------------------------------------

def read_atom(stream, offset: int, size: int, atom_type: bytes,
              header_size: int) -> Atom:
    payload_offset = offset + header_size
    payload_size   = size   - header_size

    if atom_type == b"meta":
        # meta always has a 4-byte version/flags prefix before its children
        stream.seek(payload_offset)
        raw_vf = stream.read(4)
        vf = raw_vf if len(raw_vf) == 4 else b"\x00\x00\x00\x00"
        children = _read_children(stream, payload_offset + 4, offset + size)
        return MetaAtom(offset, size, atom_type, header_size, vf, children)

    elif atom_type in CONTAINER_ATOMS:
        children = _read_children(stream, payload_offset, offset + size)
        return ContainerAtom(offset, size, atom_type, header_size, children)

    else:
        stream.seek(payload_offset)
        payload = stream.read(payload_size)
        return Atom(offset, size, atom_type, header_size, payload)


def _read_children(stream, start: int, end: int) -> List[Atom]:
    children = []
    stream.seek(start)
    for c_off, c_size, c_type, c_hdr in iter_atoms(stream, end):
        child = read_atom(stream, c_off, c_size, c_type, c_hdr)
        children.append(child)
        stream.seek(c_off + c_size)
    return children


def read_top_level(stream) -> List[Atom]:
    """Read all top-level atoms from an open file stream."""
    stream.seek(0, 2)
    file_size = stream.tell()
    stream.seek(0)
    atoms: List[Atom] = []
    for offset, size, atom_type, header_size in iter_atoms(stream, file_size):
        atom = read_atom(stream, offset, size, atom_type, header_size)
        atoms.append(atom)
        stream.seek(offset + size)
    return atoms


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def detect_format(atoms: List[Atom]) -> str:
    """
    Return 'mp4' or 'mov'.
    MOV files usually lack an ftyp atom; MP4 files always have one first.
    """
    for a in atoms:
        if a.atom_type == b"ftyp":
            brand = a.payload[:4] if len(a.payload) >= 4 else b""
            if brand == b"qt  ":
                return "mov"
            return "mp4"
    return "mov"


# ---------------------------------------------------------------------------
# Metadata key / value codec
# ---------------------------------------------------------------------------

def parse_keys_atom(payload: bytes) -> List[Tuple[bytes, bytes]]:
    """
    Parse 'keys' atom payload (including its 4-byte version/flags prefix).
    Returns list of (namespace, key_value); list index + 1 = ilst key index.
    """
    if len(payload) < 8:
        return []
    entry_count = struct.unpack_from(">I", payload, 4)[0]
    pos = 8
    keys = []
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
    """Serialise list of (namespace, key_value) → complete 'keys' atom bytes."""
    version_flags = b"\x00\x00\x00\x00"
    entry_count   = struct.pack(">I", len(keys))
    entries = b""
    for namespace, key_value in keys:
        key_size = 8 + len(key_value)
        entries += struct.pack(">I", key_size) + namespace + key_value
    inner = version_flags + entry_count + entries
    return struct.pack(">I4s", 8 + len(inner), b"keys") + inner


def _find_data_atoms_in_payload(payload: bytes) -> List[Atom]:
    """Find all 'data' child atoms within a raw payload buffer."""
    result = []
    pos = 0
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
    """Parse the raw payload of an ilst atom into ContainerAtom children."""
    children: List[Atom] = []
    pos = 0
    while pos + 8 <= len(payload):
        size  = struct.unpack_from(">I", payload, pos)[0]
        atype = payload[pos+4:pos+8]
        if size < 8:
            break
        child_payload = payload[pos+8:pos+size]
        data_children = _find_data_atoms_in_payload(child_payload)
        children.append(ContainerAtom(0, size, atype, 8, data_children))
        pos += size
    return children


def parse_ilst_values(children: List[Atom], key_count: int) -> Dict[int, bytes]:
    """
    Parse ilst children → {1-based key index: data-atom-payload bytes}.
    Each child's 4-byte atom type encodes the key index as a big-endian uint32.
    """
    values: Dict[int, bytes] = {}
    for child in children:
        key_index = struct.unpack(">I", child.atom_type)[0]
        if key_index < 1 or key_index > key_count:
            continue
        if isinstance(child, ContainerAtom):
            data_atoms = child.find(b"data")
        else:
            data_atoms = _find_data_atoms_in_payload(child.payload)
        for da in data_atoms:
            if isinstance(da, Atom) and len(da.payload) >= 8:
                values[key_index] = da.payload
                break
    return values


def decode_data_atom(raw_payload: bytes) -> Tuple[int, Any]:
    """Decode a 'data' atom payload → (type_indicator, python_value)."""
    if len(raw_payload) < 8:
        return TYPE_BINARY, raw_payload
    type_indicator = struct.unpack_from(">I", raw_payload, 0)[0]
    value_bytes    = raw_payload[8:]

    if type_indicator == TYPE_UTF8:
        return TYPE_UTF8,    value_bytes.decode("utf-8",    errors="replace")
    if type_indicator == TYPE_UTF16:
        return TYPE_UTF16,   value_bytes.decode("utf-16-be", errors="replace")
    if type_indicator == TYPE_INT8:
        return TYPE_INT8,    struct.unpack_from(">b", value_bytes)[0] if value_bytes else 0
    if type_indicator == TYPE_INT16:
        return TYPE_INT16,   struct.unpack_from(">h", value_bytes)[0] if len(value_bytes) >= 2 else 0
    if type_indicator == TYPE_INT32:
        return TYPE_INT32,   struct.unpack_from(">i", value_bytes)[0] if len(value_bytes) >= 4 else 0
    if type_indicator == TYPE_INT64:
        return TYPE_INT64,   struct.unpack_from(">q", value_bytes)[0] if len(value_bytes) >= 8 else 0
    if type_indicator == TYPE_UINT8:
        return TYPE_UINT8,   struct.unpack_from(">B", value_bytes)[0] if value_bytes else 0
    if type_indicator == TYPE_UINT16:
        return TYPE_UINT16,  struct.unpack_from(">H", value_bytes)[0] if len(value_bytes) >= 2 else 0
    if type_indicator == TYPE_UINT32:
        return TYPE_UINT32,  struct.unpack_from(">I", value_bytes)[0] if len(value_bytes) >= 4 else 0
    if type_indicator == TYPE_UINT64:
        return TYPE_UINT64,  struct.unpack_from(">Q", value_bytes)[0] if len(value_bytes) >= 8 else 0
    if type_indicator == TYPE_FLOAT32:
        return TYPE_FLOAT32, struct.unpack_from(">f", value_bytes)[0] if len(value_bytes) >= 4 else 0.0
    if type_indicator == TYPE_FLOAT64:
        return TYPE_FLOAT64, struct.unpack_from(">d", value_bytes)[0] if len(value_bytes) >= 8 else 0.0
    return type_indicator, value_bytes


def encode_data_atom(value: Any, type_indicator: int = TYPE_UTF8) -> bytes:
    """Build a complete 'data' atom (header + payload) for the given value."""
    locale = b"\x00\x00\x00\x00"
    if type_indicator == TYPE_UTF8:
        encoded = value.encode("utf-8") if isinstance(value, str) else bytes(value)
    elif type_indicator == TYPE_UTF16:
        encoded = value.encode("utf-16-be") if isinstance(value, str) else bytes(value)
    elif type_indicator == TYPE_INT8:
        encoded = struct.pack(">b", int(value))
    elif type_indicator == TYPE_INT16:
        encoded = struct.pack(">h", int(value))
    elif type_indicator == TYPE_INT32:
        encoded = struct.pack(">i", int(value))
    elif type_indicator == TYPE_INT64:
        encoded = struct.pack(">q", int(value))
    elif type_indicator == TYPE_UINT8:
        encoded = struct.pack(">B", int(value))
    elif type_indicator == TYPE_UINT16:
        encoded = struct.pack(">H", int(value))
    elif type_indicator == TYPE_UINT32:
        encoded = struct.pack(">I", int(value))
    elif type_indicator == TYPE_UINT64:
        encoded = struct.pack(">Q", int(value))
    elif type_indicator == TYPE_FLOAT32:
        encoded = struct.pack(">f", float(value))
    elif type_indicator == TYPE_FLOAT64:
        encoded = struct.pack(">d", float(value))
    else:
        encoded = value if isinstance(value, (bytes, bytearray)) else str(value).encode("utf-8")
    inner = struct.pack(">I", type_indicator) + locale + encoded
    return struct.pack(">I4s", 8 + len(inner), b"data") + inner


def build_ilst_bytes(keys: List[Tuple[bytes, bytes]],
                     values: Dict[int, bytes]) -> bytes:
    """Serialise {1-based index: data_atom_payload} → complete 'ilst' atom bytes."""
    entries = b""
    for idx, data_payload in sorted(values.items()):
        child_type = struct.pack(">I", idx)
        data_atom  = struct.pack(">I4s", 8 + len(data_payload), b"data") + data_payload
        child_total = 8 + len(data_atom)
        entries += struct.pack(">I4s", child_total, child_type) + data_atom
    return struct.pack(">I4s", 8 + len(entries), b"ilst") + entries


# ---------------------------------------------------------------------------
# stco / co64 chunk-offset fixup
# ---------------------------------------------------------------------------

def _fixup_offsets(atom: Atom, delta: int) -> None:
    """
    Recursively walk the atom tree and adjust every stco / co64 entry by *delta*.

    This is essential for MP4 files where moov precedes mdat: any change to
    moov's size shifts every byte of mdat (and thus every chunk offset) by delta.
    """
    if isinstance(atom, ContainerAtom):
        for child in atom.children:
            _fixup_offsets(child, delta)
        return

    if atom.atom_type == b"stco":
        # Layout: version(1) + flags(3) + count(4) + count × 4-byte offsets
        if len(atom.payload) < 8:
            return
        count = struct.unpack_from(">I", atom.payload, 4)[0]
        buf = bytearray(atom.payload)
        for i in range(count):
            off = 8 + i * 4
            if off + 4 > len(buf):
                break
            old = struct.unpack_from(">I", buf, off)[0]
            struct.pack_into(">I", buf, off, (old + delta) & 0xFFFFFFFF)
        atom.payload = bytes(buf)

    elif atom.atom_type == b"co64":
        # Same but 8-byte (64-bit) offsets
        if len(atom.payload) < 8:
            return
        count = struct.unpack_from(">I", atom.payload, 4)[0]
        buf = bytearray(atom.payload)
        for i in range(count):
            off = 8 + i * 8
            if off + 8 > len(buf):
                break
            old = struct.unpack_from(">Q", buf, off)[0]
            struct.pack_into(">Q", buf, off, old + delta)
        atom.payload = bytes(buf)


def _measure(atom: Atom) -> int:
    """Compute the serialised byte size of *atom* without materialising it."""
    if isinstance(atom, MetaAtom):
        return 8 + 4 + sum(_measure(c) for c in atom.children)
    if isinstance(atom, ContainerAtom):
        return 8 + sum(_measure(c) for c in atom.children)
    return 8 + len(atom.payload)


# ---------------------------------------------------------------------------
# High-level QuickTimeFile class
# ---------------------------------------------------------------------------

class QuickTimeFile:
    """
    Read and write QuickTime / MPEG-4 metadata keys.

    Supports .mov, .mp4, .m4v, .m4a.

    Example
    -------
    qt = QuickTimeFile("clip.mp4")
    print(qt.get_metadata("com.apple.quicktime.comment"))
    qt.set_metadata("com.apple.quicktime.comment", "Nice shot!")
    qt.save("clip_tagged.mp4")
    """

    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as f:
            self._atoms: List[Atom] = read_top_level(f)
        self.format: str = detect_format(self._atoms)  # 'mov' or 'mp4'

    # ------------------------------------------------------------------
    # Internal: locate structural atoms
    # ------------------------------------------------------------------

    def _moov(self) -> Optional[ContainerAtom]:
        for a in self._atoms:
            if a.atom_type == b"moov" and isinstance(a, ContainerAtom):
                return a
        return None

    def _find_meta(self, moov: ContainerAtom) -> Optional[MetaAtom]:
        """
        Locate the 'meta' atom.

        Search order (handles both MOV and MP4 layouts):
          1. moov → udta → meta   (standard QuickTime / iTunes MP4)
          2. moov → meta          (some MP4 encoders skip udta)
        """
        udta = moov.find_first(b"udta")
        if udta and isinstance(udta, ContainerAtom):
            for c in udta.children:
                if c.atom_type == b"meta" and isinstance(c, MetaAtom):
                    return c
        # Fallback: meta directly under moov
        for c in moov.children:
            if c.atom_type == b"meta" and isinstance(c, MetaAtom):
                return c
        return None

    def _ensure_meta(self, moov: ContainerAtom) -> MetaAtom:
        """Return existing MetaAtom, or create one under moov → udta."""
        meta = self._find_meta(moov)
        if meta is not None:
            return meta
        udta = moov.find_first(b"udta")
        if udta is None or not isinstance(udta, ContainerAtom):
            udta = ContainerAtom(0, 8, b"udta", 8, [])
            moov.children.append(udta)
        meta = MetaAtom(0, 8, b"meta", 8, b"\x00\x00\x00\x00", [])
        udta.children.append(meta)
        return meta

    # ------------------------------------------------------------------
    # Internal: parse / write keys + ilst
    # ------------------------------------------------------------------

    def _parse_meta(self, meta: MetaAtom
                    ) -> Tuple[List[Tuple[bytes, bytes]], Dict[int, bytes]]:
        """Return (keys_list, values_dict) extracted from *meta*."""
        keys_atom = meta.find_first(b"keys")
        keys: List[Tuple[bytes, bytes]] = []
        if keys_atom is not None:
            keys = parse_keys_atom(keys_atom.payload)

        values: Dict[int, bytes] = {}
        for c in meta.children:
            if c.atom_type == b"ilst":
                children = (c.children if isinstance(c, ContainerAtom)
                            else parse_ilst_children(c.payload))
                values = parse_ilst_values(children, len(keys))
                break
        return keys, values

    def _write_meta(self, meta: MetaAtom,
                    keys: List[Tuple[bytes, bytes]],
                    values: Dict[int, bytes]) -> None:
        """Replace the keys + ilst children inside *meta*."""
        new_keys_bytes = build_keys_atom(keys)
        new_keys_atom  = Atom(0, len(new_keys_bytes), b"keys", 8,
                              new_keys_bytes[8:])

        new_ilst_bytes    = build_ilst_bytes(keys, values)
        new_ilst_children = parse_ilst_children(new_ilst_bytes[8:])
        new_ilst_atom     = ContainerAtom(0, len(new_ilst_bytes), b"ilst", 8,
                                          new_ilst_children)

        meta.children = [c for c in meta.children
                         if c.atom_type not in (b"keys", b"ilst")]
        meta.children.append(new_keys_atom)
        meta.children.append(new_ilst_atom)

    # ------------------------------------------------------------------
    # Public read API
    # ------------------------------------------------------------------

    def all_metadata(self) -> Dict[str, Any]:
        """Return {key_string: python_value} for every metadata entry found."""
        result: Dict[str, Any] = {}
        moov = self._moov()
        if moov is None:
            return result
        meta = self._find_meta(moov)
        if meta is None:
            return result
        keys, values = self._parse_meta(meta)
        for i, (ns, kv) in enumerate(keys, start=1):
            if i in values:
                _, py_val = decode_data_atom(values[i])
                result[kv.decode("utf-8", errors="replace")] = py_val
        return result

    def get_metadata(self, key: str) -> Optional[Any]:
        """Return the value for *key*, or None if not present."""
        return self.all_metadata().get(key)

    # ------------------------------------------------------------------
    # Public write API
    # ------------------------------------------------------------------

    def set_metadata(self, key: str, value: Any,
                     type_indicator: int = TYPE_UTF8) -> None:
        """
        Set (or add) a metadata key.

        Parameters
        ----------
        key            : e.g. "com.apple.quicktime.comment"
        value          : the value to store
        type_indicator : TYPE_UTF8 (default), TYPE_INT32, TYPE_FLOAT64, etc.
        """
        moov = self._moov()
        if moov is None:
            raise ValueError("No 'moov' atom — not a valid QuickTime/MP4 file.")
        meta         = self._ensure_meta(moov)
        keys, values = self._parse_meta(meta)

        key_bytes = key.encode("utf-8")
        idx: Optional[int] = None
        for i, (ns, kv) in enumerate(keys, start=1):
            if kv == key_bytes:
                idx = i
                break
        if idx is None:
            keys.append((APPLE_QT_NAMESPACE, key_bytes))
            idx = len(keys)

        data_bytes  = encode_data_atom(value, type_indicator)
        values[idx] = data_bytes[8:]   # store only the payload part

        self._write_meta(meta, keys, values)

    def set_multiple_metadata(self, entries: Dict[str, Any],
                               type_indicators: Optional[Dict[str, int]] = None
                               ) -> None:
        """Set multiple metadata keys at once."""
        ti = type_indicators or {}
        for key, val in entries.items():
            self.set_metadata(key, val, ti.get(key, TYPE_UTF8))

    def remove_metadata(self, key: str) -> bool:
        """Remove a metadata key.  Returns True if it was found and removed."""
        moov = self._moov()
        if moov is None:
            return False
        meta = self._find_meta(moov)
        if meta is None:
            return False
        keys, values = self._parse_meta(meta)

        key_bytes = key.encode("utf-8")
        found_idx: Optional[int] = None
        for i, (ns, kv) in enumerate(keys, start=1):
            if kv == key_bytes:
                found_idx = i
                break
        if found_idx is None:
            return False

        # Compact keys list and re-index values
        new_keys: List[Tuple[bytes, bytes]] = []
        new_values: Dict[int, bytes] = {}
        new_i = 0
        for old_i, (ns, kv) in enumerate(keys, start=1):
            if old_i == found_idx:
                continue
            new_i += 1
            new_keys.append((ns, kv))
            if old_i in values:
                new_values[new_i] = values[old_i]

        self._write_meta(meta, new_keys, new_values)
        return True

    # ------------------------------------------------------------------
    # Save  —  with stco/co64 fixup for MP4
    # ------------------------------------------------------------------

    def save(self, output_path: Optional[str] = None) -> None:
        """
        Write the file, handling:
          - stco / co64 chunk-offset fixup (critical for MP4 fast-start layout)
          - 'free' / 'skip' padding atom shrink/reuse to avoid moving mdat
          - Atomic write via a temp file (safe for in-place overwrite)

        If *output_path* is None the source file is overwritten in-place.
        """
        dest  = output_path or self.path
        moov  = self._moov()

        if moov is None:
            self._write_raw(dest)
            return

        old_moov_size = moov.size           # size as originally read from disk
        new_moov_size = _measure(moov)
        delta         = new_moov_size - old_moov_size

        if delta != 0 and self._moov_before_mdat():
            # ── Try to absorb the delta with a 'free'/'skip' padding atom ─
            free_atom = self._free_after_moov()
            absorbed  = False

            if free_atom is not None:
                new_free_size = free_atom.size - delta
                if new_free_size == 0:
                    # Perfect fit: eliminate the free atom entirely
                    self._atoms = [a for a in self._atoms if a is not free_atom]
                    absorbed = True
                elif new_free_size >= 8:
                    # Shrink (or grow) the free atom to absorb the delta
                    free_atom.payload = b"\x00" * (new_free_size - 8)
                    free_atom.size    = new_free_size
                    absorbed = True
                # else new_free_size < 0 or 1-7: can't use it; fall through

            if not absorbed:
                # ── Full stco / co64 fixup ──────────────────────────────
                # If a free atom existed but couldn't absorb the full delta,
                # incorporate it into the size calculation then fix offsets.
                effective_delta = delta
                if free_atom is not None:
                    # Remove the free atom; its space is now gone too
                    effective_delta += free_atom.size
                    self._atoms = [a for a in self._atoms if a is not free_atom]
                _fixup_offsets(moov, effective_delta)

        self._write_raw(dest)
        # Refresh cached sizes so subsequent saves are correct
        moov.size = _measure(moov)

    # ------------------------------------------------------------------
    # Internal save helpers
    # ------------------------------------------------------------------

    def _free_after_moov(self) -> Optional[Atom]:
        """
        Return the first 'free' or 'skip' atom that immediately follows moov
        at the top level, if one exists.  These are standard padding atoms.
        """
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

    def _moov_before_mdat(self) -> bool:
        """Return True when moov appears before mdat in the atom list."""
        for a in self._atoms:
            if a.atom_type == b"moov":
                return True
            if a.atom_type == b"mdat":
                return False
        return False

    def _write_raw(self, dest: str) -> None:
        """Serialise all top-level atoms to *dest* atomically via a temp file."""
        dest_dir = os.path.dirname(os.path.abspath(dest)) or "."
        tmp_fd, tmp_path = tempfile.mkstemp(dir=dest_dir)
        try:
            with os.fdopen(tmp_fd, "wb") as out:
                for atom in self._atoms:
                    out.write(atom.serialize())
            shutil.move(tmp_path, dest)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        self.path = dest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_read(args):
    qt = QuickTimeFile(args.input)
    metadata = qt.all_metadata()
    if args.key:
        val = metadata.get(args.key)
        if val is None:
            print(f"Key not found: {args.key}", file=sys.stderr)
            sys.exit(1)
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
        print(f"Key not found: {args.key}", file=sys.stderr)
        sys.exit(1)
    out = args.output or args.input
    qt.save(out)
    print(f"Removed {args.key!r}  →  {out}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Read / write QuickTime metadata keys in .mov and .mp4 files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s read  clip.mov
  %(prog)s read  clip.mp4
  %(prog)s read  clip.mp4 com.apple.quicktime.comment
  %(prog)s write clip.mp4 com.apple.quicktime.comment "My comment"
  %(prog)s write clip.mp4 com.apple.quicktime.comment "My comment" --output out.mp4
  %(prog)s remove clip.mp4 com.apple.quicktime.comment
""")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("read",   help="Print metadata from a .mov or .mp4 file")
    r.add_argument("input")
    r.add_argument("key", nargs="?", default=None, help="Specific key (omit for all)")
    r.set_defaults(func=cmd_read)

    w = sub.add_parser("write",  help="Set or add a metadata key")
    w.add_argument("input")
    w.add_argument("key",   help="e.g. com.apple.quicktime.comment")
    w.add_argument("value", help="Value to set")
    w.add_argument("--output", "-o", default=None,
                   help="Output path (default: overwrite input)")
    w.set_defaults(func=cmd_write)

    rm = sub.add_parser("remove", help="Remove a metadata key")
    rm.add_argument("input")
    rm.add_argument("key")
    rm.add_argument("--output", "-o", default=None,
                    help="Output path (default: overwrite input)")
    rm.set_defaults(func=cmd_remove)

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

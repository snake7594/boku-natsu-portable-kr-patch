#!/usr/bin/env python3
import argparse
import gzip
import json
import os
import re
import struct
import zlib
from dataclasses import dataclass, asdict
from pathlib import Path


PADDING = 0x800
PAUSE_TOKEN_RE = re.compile(r"\{PAUSE(?::[0-9A-Fa-f]{4})?\}")


@dataclass
class Entry:
    path: str
    name: str
    is_folder: bool
    sub_entries: int
    offset: int
    size: int
    index_pos: int


def read_c_string(data: bytes, offset: int) -> str:
    end = data.index(0, offset)
    return data[offset:end].decode("ascii", errors="replace")


def parse_index(idx_path: Path) -> list[Entry]:
    data = idx_path.read_bytes()
    if data[:4] != b"DFI\x00":
        raise ValueError(f"{idx_path} is not a Boku cdimg.idx file")

    main_name_offset = struct.unpack_from("<I", data, 0x14)[0]
    num_entries = main_name_offset // 0x10
    raw_entries = []

    pos = 0x20
    for _ in range(num_entries - 1):
        entry_offset = pos
        is_folder_raw, sub_entries, name_rel, block_offset, size = struct.unpack_from("<HHIII", data, pos)
        name = read_c_string(data, entry_offset + name_rel)
        raw_entries.append(
            {
                "name": name,
                "is_folder": is_folder_raw == 1,
                "sub_entries": sub_entries,
                "offset": block_offset * PADDING,
                "size": size,
                "index_pos": pos,
            }
        )
        pos += 0x10

    queue = list(raw_entries)
    out: list[Entry] = []

    def consume(parent: str) -> None:
        item = queue.pop(0)
        path = f"{parent}/{item['name']}" if parent else item["name"]
        out.append(Entry(path=path, **item))
        if item["is_folder"]:
            for _ in range(item["sub_entries"] - 1):
                consume(path)

    while queue:
        consume("")
    return out


def extract_cd(entries: list[Entry], img_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with img_path.open("rb") as f:
        for entry in entries:
            target = out_dir / entry.path
            if entry.is_folder:
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            f.seek(entry.offset)
            target.write_bytes(f.read(entry.size))


def parse_pack(data: bytes, with_names: bool) -> list[tuple[str, bytes]]:
    count = struct.unpack_from("<I", data, 0)[0]
    entry_size = 0x0C if with_names else 0x08
    files = []
    for i in range(count):
        base = 4 + i * entry_size
        offset, size = struct.unpack_from("<II", data, base)
        if offset == 0 or size == 0:
            continue
        if with_names:
            name_offset = struct.unpack_from("<I", data, base + 8)[0]
            name = read_c_string(data, name_offset)
        else:
            name = f"{i}.dat"
        files.append((name, data[offset : offset + size]))
    return files


def parse_pack_entries(data: bytes, with_names: bool) -> list[dict]:
    count = struct.unpack_from("<I", data, 0)[0]
    entry_size = 0x0C if with_names else 0x08
    entries = []
    for i in range(count):
        base = 4 + i * entry_size
        offset, size = struct.unpack_from("<II", data, base)
        name = f"{i}.dat"
        if with_names:
            name_offset = struct.unpack_from("<I", data, base + 8)[0]
            name = read_c_string(data, name_offset)
        entries.append(
            {
                "index": i,
                "entry_offset": base,
                "name": name,
                "offset": offset,
                "size": size,
            }
        )
    return entries


def build_pack(files: list[tuple[str, bytes]], with_names: bool) -> bytes:
    entry_size = 0x0C if with_names else 0x08
    count = len(files)
    header_size = 4 + count * entry_size
    name_blob = bytearray()
    name_offsets: list[int] = []
    if with_names:
        for name, _payload in files:
            name_offsets.append(header_size + len(name_blob))
            name_blob.extend(name.encode("ascii"))
            name_blob.append(0)

    data_offset = header_size + len(name_blob)
    out = bytearray(data_offset)
    struct.pack_into("<I", out, 0, count)
    if with_names:
        out[header_size:data_offset] = name_blob

    payloads = bytearray()
    for i, (name, payload) in enumerate(files):
        offset = data_offset + len(payloads)
        base = 4 + i * entry_size
        struct.pack_into("<II", out, base, offset, len(payload))
        if with_names:
            struct.pack_into("<I", out, base + 8, name_offsets[i])
        payloads.extend(payload)

    out.extend(payloads)
    return bytes(out)


def make_gzip(payload: bytes, original: bytes) -> bytes:
    # Try multiple zlib memory levels. The original assets are packed more
    # tightly than Python's gzip defaults for some script members.
    best = None
    for mem_level in range(1, 10):
        compressor = zlib.compressobj(
            9,
            zlib.DEFLATED,
            31,
            mem_level,
            zlib.Z_DEFAULT_STRATEGY,
        )
        candidate = compressor.compress(payload) + compressor.flush()
        if best is None or len(candidate) < len(best):
            best = candidate
    compressed = best if best is not None else gzip.compress(payload, compresslevel=9, mtime=0)
    if original[4:6] == b"\x1F\x8B" or original[:4] == struct.pack("<I", len(payload)):
        return struct.pack("<I", len(payload)) + compressed
    return compressed


def gzip_payload(data: bytes) -> bytes:
    if data[:4] and len(data) >= 4:
        try:
            return gzip.decompress(data[4:])
        except gzip.BadGzipFile:
            pass
    return gzip.decompress(data)


def load_table(table_path: Path) -> dict[int, str]:
    table: dict[int, str] = {}
    text = table_path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if len(line) == 8 and not line.startswith("#"):
            try:
                table[int(line[:4])] = line[7]
            except ValueError:
                pass
    return table


def parse_dialog_text(raw: bytes, table: dict[int, str]) -> str:
    parts = []
    words = [value for (value,) in struct.iter_unpack("<H", raw[: len(raw) // 2 * 2])]
    i = 0
    while i < len(words):
        value = words[i]
        if value in (0x8000, 0xFFFF):
            break
        if value == 0x0000:
            parts.append("{SEG:0000}")
        elif value == 0x8001:
            parts.append("\n")
        elif value == 0x8002:
            if i + 1 < len(words):
                parts.append(f"{{PAUSE:{words[i + 1]:04X}}}")
                if i + 2 < len(words) and words[i + 2] == 0x0000:
                    i += 2
                else:
                    i += 1
            else:
                parts.append("{PAUSE}")
        elif value in table:
            parts.append(table[value])
        else:
            parts.append(f"{{{value:04X}}}")
        i += 1
    return "".join(parts)


def decode_dialog_words(raw: bytes, table: dict[int, str]) -> tuple[str, bytes]:
    words = []
    for i in range(0, len(raw) - 1, 2):
        value = struct.unpack_from("<H", raw, i)[0]
        words.append(value)
        if value in (0x8000, 0xFFFF):
            consumed = raw[: i + 2]
            return parse_dialog_text(consumed, table), consumed
    consumed = raw[: len(raw) // 2 * 2]
    return parse_dialog_text(consumed, table), consumed


def encode_dialog_text(text: str, table: dict[int, str], terminator_hex: str) -> bytes:
    inverse = {ch: code for code, ch in table.items() if ch}
    out = bytearray()
    i = 0
    while i < len(text):
        if text.startswith("{PAUSE:", i):
            end = text.find("}", i + 7)
            if end == -1:
                raise ValueError("unterminated PAUSE token")
            arg = text[i + 7:end]
            if len(arg) != 4 or any(c not in "0123456789abcdefABCDEF" for c in arg):
                raise ValueError(f"invalid PAUSE argument: {arg!r}")
            out.extend(struct.pack("<H", 0x8002))
            out.extend(struct.pack("<H", int(arg, 16)))
            if os.environ.get("BOKU_PAUSE_TRAILING_ZERO", "1") != "0":
                out.extend(struct.pack("<H", 0x0000))
            i = end + 1
            continue
        if text.startswith("{PAUSE}", i):
            out.extend(struct.pack("<H", 0x8002))
            i += len("{PAUSE}")
            continue
        if text.startswith("{SEG:0000}", i):
            out.extend(struct.pack("<H", 0x0000))
            i += len("{SEG:0000}")
            continue
        if text.startswith("{RAW:", i):
            end = text.find("}", i + 5)
            if end == -1:
                raise ValueError("unterminated RAW token")
            raw_hex = text[i + 5:end]
            out.extend(bytes.fromhex(raw_hex))
            i = end + 1
            continue
        if i + 5 < len(text) and text[i] == "{" and text[i + 5] == "}":
            token = text[i + 1 : i + 5].translate(
                str.maketrans("０１２３４５６７８９ＡＢＣＤＥＦａｂｃｄｅｆ", "0123456789ABCDEFabcdef")
            )
            if all(c in "0123456789abcdefABCDEF" for c in token):
                out.extend(struct.pack("<H", int(token, 16)))
                i += 6
                continue
        ch = text[i]
        if ch == "\n":
            out.extend(struct.pack("<H", 0x8001))
        elif ch in inverse:
            out.extend(struct.pack("<H", inverse[ch]))
        else:
            raise ValueError(f"character cannot be encoded yet: {ch!r}")
        i += 1
    out.extend(bytes.fromhex(terminator_hex))
    return bytes(out)


def iter_text_chars(text: str):
    i = 0
    while i < len(text):
        if text[i] == "{":
            end = text.find("}", i + 1)
            if end != -1:
                i = end + 1
                continue
        ch = text[i]
        if ch != "\n":
            yield ch
        i += 1


def prepare_hangul_assets(
    table_path: Path,
    translations_path: Path,
    output_table: Path,
    output_glyph_map: Path,
    start_code: int,
    end_code: int,
    font: str,
    font_size: int,
) -> None:
    table = load_table(table_path)
    translations = json.loads(translations_path.read_text(encoding="utf-8"))
    needed = []
    seen = set(table.values())
    for item in translations:
        text = item.get("ko") or ""
        for ch in iter_text_chars(text):
            if ch in seen:
                continue
            needed.append(ch)
            seen.add(ch)

    existing_codes = set(table)
    available = [code for code in range(start_code, end_code + 1) if code not in existing_codes]
    if len(needed) > len(available):
        raise ValueError(
            f"not enough glyph slots: need {len(needed)}, available {len(available)} "
            f"in {start_code}-{end_code}"
        )

    glyphs = [{"code": code, "char": ch} for code, ch in zip(available, needed)]
    glyph_map = {"font": font, "font_size": font_size, "glyphs": glyphs}
    output_glyph_map.parent.mkdir(parents=True, exist_ok=True)
    output_glyph_map.write_text(json.dumps(glyph_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = table_path.read_text(encoding="utf-8").splitlines()
    for glyph in glyphs:
        lines.append(f"{glyph['code']:04d} = {glyph['char']}")
    output_table.parent.mkdir(parents=True, exist_ok=True)
    output_table.write_text("\n".join(lines) + "\n", encoding="utf-8")


def layout_units(text: str) -> list[int]:
    units = []
    for line in text.splitlines():
        count = 0
        i = 0
        while i < len(line):
            if line[i] == "{":
                end = line.find("}", i + 1)
                if end != -1:
                    i = end + 1
                    continue
            count += 1
            i += 1
        units.append(count)
    return units or [0]


def validate_layout(change: dict) -> None:
    if os.environ.get("BOKU_LAYOUT_MODE") == "page3":
        max_width = int(os.environ.get("BOKU_MAX_LINE_UNITS", "24"))
        source_pages = PAUSE_TOKEN_RE.split(change.get("text", ""))
        ko_pages = PAUSE_TOKEN_RE.split(change.get("ko", ""))
        if len(ko_pages) > len(source_pages):
            raise ValueError(
                f"layout overflow in {change['script']} dialog {change['dialog_id']}: "
                f"page count {len(ko_pages)} > {len(source_pages)}"
            )
        for page_index, ko_page in enumerate(ko_pages):
            source_units = layout_units(source_pages[page_index]) if page_index < len(source_pages) else [0]
            ko_units = layout_units(ko_page)
            allowed_lines = max(3, len(source_units))
            if len(ko_units) > allowed_lines:
                raise ValueError(
                    f"layout overflow in {change['script']} dialog {change['dialog_id']} page {page_index + 1}: "
                    f"line count {len(ko_units)} > {allowed_lines}"
                )
            allowed_width = max(max_width, max(source_units or [0]))
            for idx, ko_count in enumerate(ko_units):
                if ko_count > allowed_width:
                    raise ValueError(
                        f"layout overflow in {change['script']} dialog {change['dialog_id']} "
                        f"page {page_index + 1} line {idx + 1}: {ko_count} glyphs > page3 budget {allowed_width}."
                    )
        return

    source_units = layout_units(change.get("text", ""))
    ko_units = layout_units(change.get("ko", ""))
    if len(ko_units) > len(source_units):
        raise ValueError(
            f"layout overflow in {change['script']} dialog {change['dialog_id']}: "
            f"line count {len(ko_units)} > {len(source_units)}"
        )
    for idx, ko_count in enumerate(ko_units):
        source_count = source_units[idx] if idx < len(source_units) else 0
        if ko_count > source_count:
            raise ValueError(
                f"layout overflow in {change['script']} dialog {change['dialog_id']} line {idx + 1}: "
                f"{ko_count} glyphs > source budget {source_count}. "
                "Shorten the line or add a verified layout override."
            )


def unswizzle_4bpp(raw: bytes, width: int, height: int) -> bytes:
    width_bytes = width // 2
    out = bytearray(len(raw))
    row_blocks = width_bytes // 16
    for y in range(height):
        for xb in range(width_bytes):
            block_x = xb // 16
            block_y = y // 8
            src = (block_y * row_blocks + block_x) * 0x80 + (y & 7) * 16 + (xb & 15)
            out[y * width_bytes + xb] = raw[src]
    return bytes(out)


def swizzle_4bpp(linear: bytes, width: int, height: int) -> bytes:
    width_bytes = width // 2
    out = bytearray(len(linear))
    row_blocks = width_bytes // 16
    for y in range(height):
        for xb in range(width_bytes):
            block_x = xb // 16
            block_y = y // 8
            dst = (block_y * row_blocks + block_x) * 0x80 + (y & 7) * 16 + (xb & 15)
            out[dst] = linear[y * width_bytes + xb]
    return bytes(out)


def pim2_4bpp_info(data: bytes) -> tuple[int, int, int, int]:
    if not data.startswith(b"PIM2"):
        raise ValueError("expected PIM2 image")
    header = 0x10 if data[5] == 0 else 0x80
    image_offset = header + struct.unpack_from("<H", data, header + 0x0C)[0]
    data_size = struct.unpack_from("<I", data, header + 0x08)[0]
    width = struct.unpack_from("<H", data, header + 0x14)[0]
    height = struct.unpack_from("<H", data, header + 0x16)[0]
    if data_size != width * height // 2:
        raise ValueError(f"expected 4bpp PIM2, got {width}x{height} data size {data_size}")
    return image_offset, data_size, width, height


def patch_font_glyphs(startup_gzx: Path, table_path: Path, glyph_map_path: Path, output_startup: Path, output_table: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    glyph_map = json.loads(glyph_map_path.read_text(encoding="utf-8"))
    startup_original = startup_gzx.read_bytes()
    startup_payload = bytearray(gzip.decompress(startup_original[4:]))
    startup_entries = parse_pack_entries(startup_payload, with_names=True)
    font_entry = next((entry for entry in startup_entries if entry["name"].lower() == "font.bin"), None)
    if font_entry is None:
        raise ValueError("font.bin not found in startup pack")

    font_pack = bytearray(startup_payload[font_entry["offset"] : font_entry["offset"] + font_entry["size"]])
    font_entries = parse_pack_entries(font_pack, with_names=False)
    font_file = glyph_map.get("font", "C:/Windows/Fonts/malgun.ttf")
    font_size = int(glyph_map.get("font_size", 15))
    glyph_max_width = int(glyph_map.get("glyph_max_width", 16))
    glyph_shift_x = int(glyph_map.get("glyph_shift_x", 0))
    glyph_shift_y = int(glyph_map.get("glyph_shift_y", 0))
    glyph_fill_hangul = bool(glyph_map.get("glyph_fill_hangul", False))
    glyph_fill_size = int(glyph_map.get("glyph_fill_size", 16))
    pil_font = ImageFont.truetype(font_file, font_size)

    glyphs_by_atlas: dict[int, list[dict]] = {}
    for item in glyph_map["glyphs"]:
        glyphs_by_atlas.setdefault(int(item["code"]) // 1024, []).append(item)

    for atlas_index, glyphs in sorted(glyphs_by_atlas.items()):
        if atlas_index >= len(font_entries):
            raise ValueError(f"font atlas {atlas_index} is not available")
        image_entry = font_entries[atlas_index]
        image_data = bytearray(font_pack[image_entry["offset"] : image_entry["offset"] + image_entry["size"]])
        image_offset, data_size, width, height = pim2_4bpp_info(image_data)
        linear = bytearray(unswizzle_4bpp(image_data[image_offset : image_offset + data_size], width, height))

        for item in glyphs:
            code = int(item["code"]) % 1024
            char = item["char"]
            tile_x = (code % 32) * 16
            tile_y = (code // 32) * 16
            source_size = max(32, font_size * 3)
            source = Image.new("L", (source_size, source_size), 0)
            draw = ImageDraw.Draw(source)
            bbox = draw.textbbox((0, 0), char, font=pil_font)
            draw.text((-bbox[0], -bbox[1]), char, font=pil_font, fill=255)
            ink_bbox = source.getbbox()
            canvas = Image.new("L", (16, 16), 0)
            if ink_bbox is not None:
                glyph = source.crop(ink_bbox)
                if glyph_fill_hangul and ("\uac00" <= char <= "\ud7a3" or "\u3130" <= char <= "\u318f"):
                    fill_size = max(1, min(16, glyph_fill_size))
                    glyph = glyph.resize((fill_size, fill_size), Image.Resampling.LANCZOS)
                    x = (16 - fill_size) // 2
                    y = (16 - fill_size) // 2
                    canvas.paste(glyph, (x, y))
                else:
                    if glyph.width > glyph_max_width:
                        new_height = max(1, round(glyph.height * glyph_max_width / glyph.width))
                        glyph = glyph.resize((glyph_max_width, new_height), Image.Resampling.LANCZOS)
                    if glyph.height > 16:
                        new_width = max(1, round(glyph.width * 16 / glyph.height))
                        glyph = glyph.resize((new_width, 16), Image.Resampling.LANCZOS)
                    x = max(0, min(16 - glyph.width, (16 - glyph.width) // 2 + glyph_shift_x))
                    y = max(0, min(16 - glyph.height, (16 - glyph.height) // 2 + glyph_shift_y))
                    canvas.paste(glyph, (x, y))
            for py in range(16):
                for px in range(16):
                    value = canvas.getpixel((px, py)) >> 4
                    byte_index = (tile_y + py) * (width // 2) + (tile_x + px) // 2
                    if px & 1:
                        linear[byte_index] = (linear[byte_index] & 0x0F) | (value << 4)
                    else:
                        linear[byte_index] = (linear[byte_index] & 0xF0) | value

        swizzled = swizzle_4bpp(bytes(linear), width, height)
        image_data[image_offset : image_offset + data_size] = swizzled
        font_pack[image_entry["offset"] : image_entry["offset"] + image_entry["size"]] = image_data

    startup_payload[font_entry["offset"] : font_entry["offset"] + font_entry["size"]] = font_pack
    rebuilt_startup = make_gzip(bytes(startup_payload), startup_original)

    output_startup.parent.mkdir(parents=True, exist_ok=True)
    output_startup.write_bytes(rebuilt_startup)

    lines = table_path.read_text(encoding="utf-8").splitlines()
    by_code = {int(item["code"]): item["char"] for item in glyph_map["glyphs"]}
    seen_codes = set()
    out_lines = []
    for line in lines:
        if len(line) >= 6 and line[:4].isdigit():
            code = int(line[:4])
            seen_codes.add(code)
            if code in by_code:
                out_lines.append(f"{code:04d} = {by_code[code]}")
                continue
        out_lines.append(line)
    for code, char in sorted(by_code.items()):
        if code not in seen_codes:
            out_lines.append(f"{code:04d} = {char}")
    output_table.parent.mkdir(parents=True, exist_ok=True)
    output_table.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def rebuild_dialog_block(block: bytes, changes: list[dict], table: dict[int, str]) -> bytes:
    elements = struct.unpack_from("<I", block, 0)[0]
    table_size = 4 + elements * 4
    offsets = [struct.unpack_from("<I", block, 4 + i * 4)[0] for i in range(elements)]
    change_by_element = {int(change["element_index"]): change for change in changes}

    boundaries = sorted({off for off in offsets if off != 0} | {len(block)})
    next_boundary = {}
    for pos, off in enumerate(boundaries[:-1]):
        next_boundary[off] = boundaries[pos + 1]

    rebuilt_segments: dict[int, bytes] = {}
    for off in boundaries:
        if off == len(block):
            continue
        segment = block[off:next_boundary[off]]
        rebuilt_segments[off] = segment

    for elem_idx, change in change_by_element.items():
        if elem_idx >= len(offsets):
            raise ValueError(f"element index out of range: {elem_idx}")
        off = offsets[elem_idx]
        if off == 0:
            continue
        segment = rebuilt_segments[off]
        old_raw = bytes.fromhex(change["raw_hex"])
        if not segment.startswith(old_raw):
            raise ValueError(f"raw mismatch in dialog {change['dialog_id']} element {elem_idx}")
        validate_layout(change)
        new_raw = encode_dialog_text(change["ko"], table, change["terminator_hex"])
        rebuilt_segments[off] = new_raw + segment[len(old_raw):]

    out = bytearray(block[:table_size])
    new_offsets_by_old: dict[int, int] = {}
    for off in sorted(rebuilt_segments):
        new_offsets_by_old[off] = len(out)
        out.extend(rebuilt_segments[off])

    for i, old_off in enumerate(offsets):
        new_off = 0 if old_off == 0 else new_offsets_by_old[old_off]
        struct.pack_into("<I", out, 4 + i * 4, new_off)

    return bytes(out)


def rebuild_dialogs_file(dialogs: bytes, changes: list[dict], table: dict[int, str]) -> bytes:
    block_count = struct.unpack_from("<I", dialogs, 0)[0]
    blocks = []
    changes_by_block: dict[int, list[dict]] = {}
    for change in changes:
        changes_by_block.setdefault(int(change["block_index"]), []).append(change)

    for i in range(block_count):
        fat = 4 + i * 8
        dialog_id, length, offset = struct.unpack_from("<HHI", dialogs, fat)
        block = dialogs[offset:offset + length]
        if i in changes_by_block:
            block = rebuild_dialog_block(block, changes_by_block[i], table)
        blocks.append({"id": dialog_id, "block": block})

    header_size = 4 + block_count * 8
    out = bytearray(header_size)
    struct.pack_into("<I", out, 0, block_count)
    for i, item in enumerate(blocks):
        offset = len(out)
        block = item["block"]
        out.extend(block)
        struct.pack_into("<HHI", out, 4 + i * 8, item["id"], len(block), offset)
    return bytes(out)


def rebuild_payload_preserving_pack(payload: bytes, changes: list[dict], table: dict[int, str]) -> bytes:
    entries = parse_pack_entries(payload, with_names=False)
    if len(entries) <= 1 or entries[1]["offset"] == 0:
        raise ValueError("script payload has no dialogs entry")

    dialog_entry = entries[1]
    dialogs = payload[dialog_entry["offset"]:dialog_entry["offset"] + dialog_entry["size"]]
    new_dialogs = rebuild_dialogs_file(dialogs, changes, table)
    if len(new_dialogs) > dialog_entry["size"]:
        raise ValueError(
            "dialog payload grew beyond its fixed slot. "
            f"{dialog_entry['size']} -> {len(new_dialogs)} bytes. "
            "This member has no safe gap; shorten another string in the same dialog file "
            "or use a relocation strategy."
        )

    out = bytearray(payload)
    start = dialog_entry["offset"]
    end = start + dialog_entry["size"]
    out[start:end] = new_dialogs + b"\x00" * (dialog_entry["size"] - len(new_dialogs))
    return bytes(out)


def rebuild_payload_repacking_dialogs(payload: bytes, changes: list[dict], table: dict[int, str]) -> bytes:
    entries = parse_pack_entries(payload, with_names=False)
    if len(entries) <= 1 or entries[1]["offset"] == 0:
        raise ValueError("script payload has no dialogs entry")

    dialog_entry = entries[1]
    dialogs = payload[dialog_entry["offset"]:dialog_entry["offset"] + dialog_entry["size"]]
    new_dialogs = rebuild_dialogs_file(dialogs, changes, table)

    entry_size = 0x08
    header_size = 4 + len(entries) * entry_size
    out = bytearray(header_size)
    struct.pack_into("<I", out, 0, len(entries))
    payloads = bytearray()

    for entry in entries:
        base = 4 + entry["index"] * entry_size
        if entry["offset"] == 0 or entry["size"] == 0:
            struct.pack_into("<II", out, base, 0, 0)
            continue
        item = new_dialogs if entry["index"] == 1 else payload[entry["offset"]:entry["offset"] + entry["size"]]
        offset = header_size + len(payloads)
        struct.pack_into("<II", out, base, offset, len(item))
        payloads.extend(item)

    out.extend(payloads)
    return bytes(out)


def rebuild_scripts_raw(extracted_root: Path, table_path: Path, translations_path: Path, out_root: Path) -> None:
    table = load_table(table_path)
    translations = json.loads(translations_path.read_text(encoding="utf-8"))
    by_script: dict[str, list[dict]] = {}
    for item in translations:
        if item.get("ko"):
            by_script.setdefault(item["script"], []).append(item)

    src_dir = extracted_root / "map" / "gz"
    dst_dir = out_root / "map" / "gz"
    dst_dir.mkdir(parents=True, exist_ok=True)
    for script_path in sorted(src_dir.glob("*.bin")):
        changes = by_script.get(script_path.name, [])
        if not changes:
            (dst_dir / script_path.name).write_bytes(script_path.read_bytes())
            continue

        script = bytearray(script_path.read_bytes())
        members = parse_pack_entries(script, with_names=True)
        changes_by_pack: dict[int, list[dict]] = {}
        for change in changes:
            changes_by_pack.setdefault(int(change["pack_index"]), []).append(change)

        for pack_index in sorted(changes_by_pack):
            member = members[pack_index]
            old_slot = bytes(script[member["offset"]:member["offset"] + member["size"]])
            payload = gzip_payload(old_slot)
            try:
                try:
                    new_payload = rebuild_payload_preserving_pack(payload, changes_by_pack[pack_index], table)
                except ValueError as exc:
                    if "fixed slot" not in str(exc) or os.environ.get("BOKU_ALLOW_DIALOG_RELOCATION", "0") != "1":
                        raise
                    new_payload = rebuild_payload_repacking_dialogs(payload, changes_by_pack[pack_index], table)
            except Exception as exc:
                raise ValueError(f"{script_path.name}/{member['name']}: {exc}") from exc
            new_member = make_gzip(new_payload, old_slot)
            if len(new_member) > member["size"]:
                raise ValueError(
                    f"{script_path.name}/{member['name']} compressed member grew beyond its slot: "
                    f"{member['size']} -> {len(new_member)}"
                )
            padded_member = new_member + b"\x00" * (member["size"] - len(new_member))
            script[member["offset"]:member["offset"] + member["size"]] = padded_member

        (dst_dir / script_path.name).write_bytes(script)


def extract_scripts(extracted_root: Path, table_path: Path, out_json: Path, limit: int | None = None) -> None:
    table = load_table(table_path)
    script_files = sorted((extracted_root / "map" / "gz").glob("*.bin"))
    results = []

    for script_path in script_files[:limit]:
        data = script_path.read_bytes()
        for pack_index, (gz_name, gz_data) in enumerate(parse_pack(data, with_names=True)):
            payload = gzip.decompress(gz_data[4:] if gz_name.endswith(".gzx") else gz_data)
            parts = parse_pack(payload, with_names=False)
            if len(parts) < 2:
                continue
            dialogs = parts[1][1]
            if len(dialogs) < 4:
                continue
            block_count = struct.unpack_from("<I", dialogs, 0)[0]
            for block_idx in range(block_count):
                fat = 4 + block_idx * 8
                if fat + 8 > len(dialogs):
                    continue
                dialog_id, _length, block_offset = struct.unpack_from("<HHI", dialogs, fat)
                if block_offset + 4 > len(dialogs):
                    continue
                elements = struct.unpack_from("<I", dialogs, block_offset)[0]
                for elem in range(3, elements, 2):
                    p_name = block_offset + 4 + elem * 4
                    p_text = block_offset + 4 + (elem + 1) * 4
                    if p_text + 4 > len(dialogs):
                        continue
                    name_off = block_offset + struct.unpack_from("<I", dialogs, p_name)[0]
                    text_off = block_offset + struct.unpack_from("<I", dialogs, p_text)[0]
                    if name_off >= len(dialogs) or text_off >= len(dialogs):
                        continue
                    try:
                        key = read_c_string(dialogs, name_off)
                    except ValueError:
                        key = ""
                    text, raw = decode_dialog_words(dialogs[text_off:], table)
                    if text:
                        results.append(
                            {
                                "script": script_path.name,
                                "pack_index": pack_index,
                                "pack_member": gz_name,
                                "dialog_id": dialog_id,
                                "block_index": block_idx,
                                "element_index": elem + 1,
                                "text_offset": text_off,
                                "raw_hex": raw.hex().upper(),
                                "terminator_hex": raw[-2:].hex().upper(),
                                "key": key,
                                "text": text,
                                "ko": "",
                                "status": "todo",
                            }
                        )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


def rebuild_scripts(extracted_root: Path, table_path: Path, translations_path: Path, out_root: Path) -> None:
    table = load_table(table_path)
    translations = json.loads(translations_path.read_text(encoding="utf-8"))
    by_script: dict[str, list[dict]] = {}
    for item in translations:
        if item.get("ko"):
            by_script.setdefault(item["script"], []).append(item)

    src_dir = extracted_root / "map" / "gz"
    dst_dir = out_root / "map" / "gz"
    dst_dir.mkdir(parents=True, exist_ok=True)
    for script_path in sorted(src_dir.glob("*.bin")):
        changes = by_script.get(script_path.name, [])
        if not changes:
            (dst_dir / script_path.name).write_bytes(script_path.read_bytes())
            continue

        top_members = parse_pack(script_path.read_bytes(), with_names=True)
        changes_by_pack: dict[int, list[dict]] = {}
        for change in changes:
            changes_by_pack.setdefault(change["pack_index"], []).append(change)

        rebuilt_top = []
        for pack_index, (gz_name, gz_data) in enumerate(top_members):
            member_changes = changes_by_pack.get(pack_index, [])
            if not member_changes:
                rebuilt_top.append((gz_name, gz_data))
                continue

            payload = gzip.decompress(gz_data[4:] if gz_name.endswith(".gzx") else gz_data)
            parts = parse_pack(payload, with_names=False)
            dialogs = bytearray(parts[1][1])
            # Apply from back to front because replacements can change offsets.
            for change in sorted(member_changes, key=lambda c: c["text_offset"], reverse=True):
                original = bytes.fromhex(change["raw_hex"])
                new_raw = encode_dialog_text(change["ko"], table, change["terminator_hex"])
                off = change["text_offset"]
                if dialogs[off : off + len(original)] != original:
                    raise ValueError(f"raw mismatch in {script_path.name} {gz_name} at 0x{off:X}")
                if len(new_raw) != len(original):
                    raise ValueError(
                        f"length-changing script rebuild is not enabled yet for "
                        f"{script_path.name}/{gz_name} dialog {change['dialog_id']}: "
                        f"{len(original)} -> {len(new_raw)} bytes"
                    )
                dialogs[off : off + len(original)] = new_raw

            parts[1] = (parts[1][0], bytes(dialogs))
            new_payload = build_pack(parts, with_names=False)
            rebuilt_top.append((gz_name, make_gzip(new_payload, gz_data)))

        (dst_dir / script_path.name).write_bytes(build_pack(rebuilt_top, with_names=True))


def rebuild_cdimg(idx_path: Path, img_path: Path, extracted_root: Path, replacement_root: Path, out_idx: Path, out_img: Path) -> None:
    entries = parse_index(idx_path)
    idx_data = bytearray(idx_path.read_bytes())
    out_img.parent.mkdir(parents=True, exist_ok=True)
    out_idx.parent.mkdir(parents=True, exist_ok=True)

    replacements: list[tuple[Entry, bytes]] = []
    for entry in entries:
        if entry.is_folder:
            continue
        replacement = replacement_root / entry.path
        if replacement.exists():
            payload = replacement.read_bytes()
            extracted = extracted_root / entry.path
            if not extracted.exists() or payload != extracted.read_bytes():
                replacements.append((entry, payload))

    if all(len(payload) == entry.size for entry, payload in replacements):
        out_img.write_bytes(img_path.read_bytes())
        for entry, payload in replacements:
            with out_img.open("r+b") as dst:
                dst.seek(entry.offset)
                dst.write(payload)
        out_idx.write_bytes(idx_data)
        return

    with img_path.open("rb") as src, out_img.open("wb") as dst:
        for entry in entries:
            if entry.is_folder:
                continue
            replacement = replacement_root / entry.path
            extracted = extracted_root / entry.path
            if replacement.exists():
                payload = replacement.read_bytes()
            elif extracted.exists():
                payload = extracted.read_bytes()
            else:
                src.seek(entry.offset)
                payload = src.read(entry.size)

            pad = (-dst.tell()) % PADDING
            if pad:
                dst.write(b"\x00" * pad)
            new_offset = dst.tell()
            dst.write(payload)

            block = new_offset // PADDING
            struct.pack_into("<II", idx_data, entry.index_pos + 8, block, len(payload))

    out_idx.write_bytes(idx_data)


def cmd_index(args: argparse.Namespace) -> None:
    entries = parse_index(Path(args.idx))
    payload = [asdict(e) for e in entries]
    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {len(entries)} entries to {args.output}")


def cmd_extract(args: argparse.Namespace) -> None:
    entries = parse_index(Path(args.idx))
    extract_cd(entries, Path(args.img), Path(args.output))
    print(f"extracted {sum(not e.is_folder for e in entries)} files to {args.output}")


def cmd_scripts(args: argparse.Namespace) -> None:
    extract_scripts(Path(args.root), Path(args.table), Path(args.output), args.limit)
    print(f"wrote script JSON to {args.output}")


def cmd_rebuild_scripts(args: argparse.Namespace) -> None:
    rebuild_scripts(Path(args.root), Path(args.table), Path(args.translations), Path(args.output))
    print(f"rebuilt changed scripts under {args.output}")


def cmd_rebuild_scripts_raw(args: argparse.Namespace) -> None:
    rebuild_scripts_raw(Path(args.root), Path(args.table), Path(args.translations), Path(args.output))
    print(f"raw-rebuilt changed scripts under {args.output}")


def cmd_rebuild_cdimg(args: argparse.Namespace) -> None:
    rebuild_cdimg(
        Path(args.idx),
        Path(args.img),
        Path(args.extracted),
        Path(args.replacements),
        Path(args.output_idx),
        Path(args.output_img),
    )
    print(f"wrote {args.output_idx} and {args.output_img}")


def cmd_patch_font(args: argparse.Namespace) -> None:
    patch_font_glyphs(
        Path(args.startup),
        Path(args.table),
        Path(args.glyph_map),
        Path(args.output_startup),
        Path(args.output_table),
    )
    print(f"wrote {args.output_startup} and {args.output_table}")


def cmd_prepare_hangul(args: argparse.Namespace) -> None:
    prepare_hangul_assets(
        Path(args.table),
        Path(args.translations),
        Path(args.output_table),
        Path(args.output_glyph_map),
        args.start_code,
        args.end_code,
        args.font,
        args.font_size,
    )
    print(f"wrote {args.output_table} and {args.output_glyph_map}")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("index")
    p.add_argument("--idx", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("extract")
    p.add_argument("--idx", required=True)
    p.add_argument("--img", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("scripts")
    p.add_argument("--root", required=True)
    p.add_argument("--table", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--limit", type=int)
    p.set_defaults(func=cmd_scripts)

    p = sub.add_parser("rebuild-scripts")
    p.add_argument("--root", required=True)
    p.add_argument("--table", required=True)
    p.add_argument("--translations", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_rebuild_scripts)

    p = sub.add_parser("rebuild-scripts-raw")
    p.add_argument("--root", required=True)
    p.add_argument("--table", required=True)
    p.add_argument("--translations", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_rebuild_scripts_raw)

    p = sub.add_parser("rebuild-cdimg")
    p.add_argument("--idx", required=True)
    p.add_argument("--img", required=True)
    p.add_argument("--extracted", required=True)
    p.add_argument("--replacements", required=True)
    p.add_argument("--output-idx", required=True)
    p.add_argument("--output-img", required=True)
    p.set_defaults(func=cmd_rebuild_cdimg)

    p = sub.add_parser("patch-font")
    p.add_argument("--startup", required=True)
    p.add_argument("--table", required=True)
    p.add_argument("--glyph-map", required=True)
    p.add_argument("--output-startup", required=True)
    p.add_argument("--output-table", required=True)
    p.set_defaults(func=cmd_patch_font)

    p = sub.add_parser("prepare-hangul")
    p.add_argument("--table", required=True)
    p.add_argument("--translations", required=True)
    p.add_argument("--output-table", required=True)
    p.add_argument("--output-glyph-map", required=True)
    p.add_argument("--start-code", type=int, default=1573)
    p.add_argument("--end-code", type=int, default=2047)
    p.add_argument("--font", default="C:/Windows/Fonts/malgun.ttf")
    p.add_argument("--font-size", type=int, default=15)
    p.set_defaults(func=cmd_prepare_hangul)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

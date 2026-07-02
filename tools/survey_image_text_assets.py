#!/usr/bin/env python3
import gzip
import json
import math
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boku_tools


ROOT = Path("work/cdimg0_extracted")
OUT = Path("work/image_text_survey")
PNG_SIG = b"\x89PNG\r\n\x1a\n"
IEND = b"IEND"


def iter_png_blobs(data: bytes):
    pos = 0
    while True:
        start = data.find(PNG_SIG, pos)
        if start < 0:
            break
        iend = data.find(IEND, start)
        if iend < 0:
            break
        end = iend + 8
        yield start, data[start:end]
        pos = end


def iter_pim2_offsets(data: bytes):
    pos = 0
    while True:
        start = data.find(b"PIM2", pos)
        if start < 0:
            break
        yield start
        pos = start + 4


def pim2_to_gray(data: bytes) -> Image.Image | None:
    try:
        image_offset, data_size, width, height = boku_tools.pim2_4bpp_info(data)
    except Exception:
        return None
    raw = data[image_offset : image_offset + data_size]
    if len(raw) != data_size:
        return None
    linear = boku_tools.unswizzle_4bpp(raw, width, height)
    img = Image.new("L", (width, height), 0)
    pix = img.load()
    for y in range(height):
        row = y * (width // 2)
        for x in range(0, width, 2):
            b = linear[row + x // 2]
            pix[x, y] = (b & 0x0F) * 17
            pix[x + 1, y] = (b >> 4) * 17
    return img.convert("RGBA")


def safe_name(path: Path, suffix: str) -> str:
    rel = path.relative_to(ROOT).as_posix().replace("/", "__")
    return f"{rel}{suffix}"


def collect_assets() -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    images_dir = OUT / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        layers = [("file", data)]
        if data[:2] == b"\x1f\x8b" or data[4:6] == b"\x1f\x8b":
            try:
                layers.append(("gzip", gzip.decompress(data[4:] if data[4:6] == b"\x1f\x8b" else data)))
            except Exception:
                pass
        for layer, blob in layers:
            for idx, (offset, png) in enumerate(iter_png_blobs(blob)):
                out = images_dir / safe_name(path, f"__{layer}__png_{idx:02d}.png")
                out.write_bytes(png)
                rows.append({"source": str(path), "layer": layer, "kind": "png", "offset_hex": f"0x{offset:X}", "image": str(out)})
            for idx, offset in enumerate(iter_pim2_offsets(blob)):
                img = pim2_to_gray(blob[offset:])
                if img is None:
                    continue
                out = images_dir / safe_name(path, f"__{layer}__pim2_{idx:02d}.png")
                img.save(out)
                rows.append({"source": str(path), "layer": layer, "kind": "pim2-gray", "offset_hex": f"0x{offset:X}", "image": str(out), "width": img.width, "height": img.height})
    return rows


def make_contact_sheet(rows: list[dict], name: str, predicate, max_items: int = 120) -> Path | None:
    selected = [row for row in rows if predicate(row)][:max_items]
    if not selected:
        return None
    thumb_w, thumb_h = 180, 140
    cols = 4
    rows_count = math.ceil(len(selected) / cols)
    sheet = Image.new("RGB", (cols * thumb_w, rows_count * thumb_h), "white")
    draw = ImageDraw.Draw(sheet)
    for i, row in enumerate(selected):
        x = (i % cols) * thumb_w
        y = (i // cols) * thumb_h
        try:
            img = Image.open(row["image"]).convert("RGB")
        except Exception:
            continue
        img.thumbnail((thumb_w - 8, thumb_h - 36), Image.Resampling.LANCZOS)
        sheet.paste(img, (x + 4, y + 4))
        label = Path(row["source"]).name + " " + row["kind"] + " " + row["offset_hex"]
        draw.text((x + 4, y + thumb_h - 28), label[:28], fill=(0, 0, 0))
        draw.text((x + 4, y + thumb_h - 14), str(Path(row["source"]).parent.name)[:28], fill=(80, 80, 80))
    out = OUT / name
    sheet.save(out)
    return out


def main() -> None:
    rows = collect_assets()
    json_path = OUT / "image_asset_candidates.json"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sheets = {}
    sheets["diary"] = make_contact_sheet(rows, "contact_diary.png", lambda r: "\\diary\\" in r["source"] or "/diary/" in r["source"], 160)
    sheets["title_system"] = make_contact_sheet(rows, "contact_title_system.png", lambda r: any(key in r["source"].lower() for key in ["title", "system", "startup", "memory"]), 120)
    sheets["embedded_png"] = make_contact_sheet(rows, "contact_embedded_png.png", lambda r: r["kind"] == "png", 80)
    md = ["# Image Text Asset Survey", "", f"- Extracted image candidates: {len(rows)}", ""]
    for key, path in sheets.items():
        if path:
            md.append(f"- {key}: `{path}`")
    md.append("")
    md.append("## Notes")
    md.append("")
    md.append("- `pim2-gray` images are grayscale decodes of 4bpp PIM2 payloads. They are useful for spotting baked text, but not final-color previews.")
    md.append("- OCR was not available in this environment, so candidates should be visually reviewed from contact sheets.")
    (OUT / "image_text_survey.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json_path)
    for path in sheets.values():
        if path:
            print(path)


if __name__ == "__main__":
    main()

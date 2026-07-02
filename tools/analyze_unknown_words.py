#!/usr/bin/env python3
import csv
import gzip
import json
import os
import struct
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import boku_tools


BLOCKS = Path(os.environ.get("BOKU_STRUCTURE_BLOCKS", "outputs/dialog_structure_v1/dialog_blocks_structured.json"))
OUT_DIR = Path(os.environ.get("BOKU_UNKNOWN_OUT", "outputs/dialog_structure_v2"))
STARTUP = Path(os.environ.get("BOKU_STARTUP_GZX", "work/cdimg0_extracted/01startup/startup.bin.gzx"))


def text_around(tokens: list[dict], index: int, radius: int = 7) -> tuple[str, str]:
    def visible(chunk: list[dict]) -> str:
        parts = []
        for token in chunk:
            if token.get("kind") in {"char", "glyph_token", "newline", "page"}:
                parts.append(token.get("text", ""))
        return "".join(parts).replace("\n", "\\n")

    return visible(tokens[max(0, index - radius):index]), visible(tokens[index + 1:index + 1 + radius])


def collect_unknowns() -> tuple[Counter[int], dict[int, list[dict]]]:
    blocks = json.loads(BLOCKS.read_text(encoding="utf-8"))
    counts: Counter[int] = Counter()
    examples: dict[int, list[dict]] = defaultdict(list)
    for block in blocks:
        for element in block["elements"]:
            if element.get("role_hint") != "text":
                continue
            for run in element.get("runs", []):
                tokens = run.get("tokens", [])
                for index, token in enumerate(tokens):
                    if token.get("kind") == "control" and token.get("name") == "unknown_word":
                        value = int(token["word"], 16)
                        counts[value] += 1
                        if len(examples[value]) < 12:
                            before, after = text_around(tokens, index)
                            examples[value].append(
                                {
                                    "script": block["script"],
                                    "member": block["pack_member"],
                                    "dialog_id": block["dialog_id"],
                                    "block_index": block["block_index"],
                                    "element_index": element["element_index"],
                                    "run_index": run["run_index"],
                                    "before": before,
                                    "after": after,
                                    "run_text": run.get("text", "").replace("\n", "\\n"),
                                }
                            )
    return counts, examples


def extract_font_atlas(atlas_index: int) -> Image.Image:
    startup = STARTUP.read_bytes()
    payload = gzip.decompress(startup[4:])
    entries = boku_tools.parse_pack_entries(payload, with_names=True)
    font_entry = next(entry for entry in entries if entry["name"].lower() == "font.bin")
    font_pack = payload[font_entry["offset"]:font_entry["offset"] + font_entry["size"]]
    font_entries = boku_tools.parse_pack_entries(font_pack, with_names=False)
    entry = font_entries[atlas_index]
    image_data = font_pack[entry["offset"]:entry["offset"] + entry["size"]]
    image_offset, data_size, width, height = boku_tools.pim2_4bpp_info(image_data)
    swizzled = image_data[image_offset:image_offset + data_size]
    linear = boku_tools.unswizzle_4bpp(swizzled, width, height)
    pixels = Image.new("L", (width, height), 0)
    data = bytearray()
    for byte in linear:
        data.append((byte & 0x0F) * 17)
        data.append(((byte >> 4) & 0x0F) * 17)
    pixels.putdata(data)
    return pixels


def render_marked_atlas(atlas: Image.Image, counts: Counter[int], atlas_index: int) -> Image.Image:
    scale = 2
    tile = 16 * scale
    image = atlas.resize((atlas.width * scale, atlas.height * scale), Image.Resampling.NEAREST).convert("RGB")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 9)
    except OSError:
        font = ImageFont.load_default()
    base = atlas_index * 1024
    top = {value for value, _count in counts.most_common(80) if value // 1024 == atlas_index}
    for value, count in counts.items():
        if value // 1024 != atlas_index:
            continue
        cell = value - base
        x = (cell % 32) * tile
        y = (cell // 32) * tile
        color = (255, 48, 48) if value in top else (255, 190, 0)
        draw.rectangle((x, y, x + tile - 1, y + tile - 1), outline=color, width=2)
        if value in top:
            draw.text((x + 1, y + 1), f"{value:04X}", fill=(0, 255, 255), font=font)
    return image


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counts, examples = collect_unknowns()

    rows = []
    for value, count in counts.most_common():
        atlas = value // 1024
        cell = value % 1024
        rows.append(
            {
                "word_hex": f"{value:04X}",
                "word_dec": value,
                "count": count,
                "atlas": atlas,
                "cell": cell,
                "tile_x": cell % 32,
                "tile_y": cell // 32,
                "contexts": " / ".join(f"{ex['before']}□{ex['after']}" for ex in examples[value][:5]),
                "first_location": f"{examples[value][0]['script']}/{examples[value][0]['member']}:{examples[value][0]['dialog_id']}:{examples[value][0]['block_index']}:{examples[value][0]['element_index']}",
                "candidate_char": "",
                "note": "likely glyph in extra font atlas" if atlas >= 1 else "review",
            }
        )

    with (OUT_DIR / "unknown_word_inventory.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "word_hex",
            "word_dec",
            "count",
            "atlas",
            "cell",
            "tile_x",
            "tile_y",
            "contexts",
            "first_location",
            "candidate_char",
            "note",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    (OUT_DIR / "unknown_word_inventory.json").write_text(
        json.dumps(
            [
                {
                    **{k: v for k, v in row.items() if k != "contexts"},
                    "examples": examples[int(row["word_hex"], 16)],
                }
                for row in rows
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    for atlas_index in sorted({value // 1024 for value in counts}):
        if atlas_index > 1:
            continue
        atlas = extract_font_atlas(atlas_index)
        atlas.save(OUT_DIR / f"unknown_original_atlas{atlas_index}.png")
        render_marked_atlas(atlas, counts, atlas_index).save(OUT_DIR / f"unknown_original_atlas{atlas_index}_marked_2x.png")

    range_counts = Counter(f"{value // 0x100:02X}xx" for value in counts for _ in range(counts[value]))
    md = [
        "# Unknown Word Analysis",
        "",
        f"- Unknown total occurrences: {sum(counts.values())}",
        f"- Unknown unique words: {len(counts)}",
        "- Main finding: most unknown words are not control codes. They are codes above 1023, pointing into the second font atlas.",
        "",
        "## Range Distribution",
        "",
    ]
    md.extend(f"- `{key}`: {range_counts[key]}" for key in sorted(range_counts))
    md.extend(
        [
            "",
            "## Top Unknowns",
            "",
            "| word | count | atlas/cell | context |",
            "|---|---:|---|---|",
        ]
    )
    for row in rows[:40]:
        context = row["contexts"].replace("|", "/")
        md.append(f"| `{row['word_hex']}` | {row['count']} | {row['atlas']}/{row['cell']} | {context} |")
    md.extend(
        [
            "",
            "## Files",
            "",
            "- `unknown_word_inventory.csv`: editable inventory with context and candidate columns.",
            "- `unknown_word_inventory.json`: same data with full example records.",
            "- `unknown_original_atlas1.png`: original second font atlas.",
            "- `unknown_original_atlas1_marked_2x.png`: second font atlas with unknown-used cells marked.",
        ]
    )
    (OUT_DIR / "unknown_word_analysis.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    summary = {
        "unknown_total": sum(counts.values()),
        "unknown_unique": len(counts),
        "range_counts": dict(sorted(range_counts.items())),
        "top": [{"word_hex": f"{value:04X}", "count": count} for value, count in counts.most_common(20)],
    }
    (OUT_DIR / "unknown_word_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

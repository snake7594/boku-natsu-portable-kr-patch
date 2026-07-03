#!/usr/bin/env python3
import gzip
import hashlib
import io
import json
import shutil
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boku_tools


ROOT = Path(__file__).resolve().parents[1]
EXTRACT = ROOT / "work" / "cdimg0_extracted"
BASE_BUILD = ROOT / "work" / "build_pause_guard_fixedpack"
BASE_REPLACEMENTS = ROOT / "work" / "replacements_pause_guard_fixedpack"
OUT = ROOT / "work" / "image_patch_title_system"
REPLACEMENTS = ROOT / "work" / "replacements_pause_guard_image_kr"
BUILD = ROOT / "work" / "build_pause_guard_image_kr"

FONT_BOLD = Path("C:/Windows/Fonts/Binggrae-Bold.ttf")
FONT_REG = Path("C:/Windows/Fonts/Binggrae.ttf")


TEXT = {
    "title": "\ub098\uc758 \uc5ec\ub984\ubc29\ud559",
    "portable": "\ud3ec\ud130\ube14",
    "secret": "\ubb34\uc2dc\ubb34\uc2dc \ubc15\uc0ac\uc640 \ud14c\ud39c\uc0b0\uc758 \ube44\ubc00!!",
    "start": "START \ubc84\ud2bc\uc744 \ub20c\ub7ec \uc8fc\uc138\uc694",
    "new": "\ucc98\uc74c\ubd80\ud130",
    "continue": "\uc774\uc5b4\ud558\uae30",
    "memory": "\ucd94\uc5b5 \ubcf4\uae30",
    "bonus": "\ud2b9\uc804",
    "settings": "\uc124\uc815",
    "favorite": "\uc990\uaca8\ucc3e\uae30",
    "sumo": "\uace4\ucda9 \uc528\ub984",
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REG), size)


def fit_font(text: str, max_w: int, start: int, min_size: int = 8, bold: bool = False) -> ImageFont.FreeTypeFont:
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for size in range(start, min_size - 1, -1):
        f = font(size, bold)
        stroke = max(1, size // 18)
        box = probe.textbbox((0, 0), text, font=f, stroke_width=stroke)
        if box[2] - box[0] <= max_w:
            return f
    return font(min_size, bold)


def draw_center(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, f, fill, stroke, sw: int) -> None:
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=f, stroke_width=sw)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = x1 + (x2 - x1 - w) // 2 - bbox[0]
    y = y1 + (y2 - y1 - h) // 2 - bbox[1]
    draw.text((x, y), text, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke)


def patch_title_preview() -> Image.Image:
    src = ROOT / "work" / "image_text_survey" / "images" / "map__models__title__title.bin__file__pim2_01.png"
    image = Image.open(src).convert("L").convert("RGBA")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((0, 118, 392, 178), radius=4, fill=(0, 0, 0, 255))
    draw.rectangle((384, 120, 511, 222), fill=(0, 0, 0, 255))
    draw.rectangle((456, 0, 511, 28), fill=(0, 0, 0, 255))
    draw.rectangle((0, 178, 380, 215), fill=(0, 0, 0, 255))
    draw.rectangle((0, 218, 330, 252), fill=(0, 0, 0, 255))
    draw.rectangle((340, 178, 511, 285), fill=(0, 0, 0, 255))

    draw_center(draw, (4, 122, 388, 172), TEXT["title"], fit_font(TEXT["title"], 370, 56, 30, True), "white", "black", 2)
    draw_center(draw, (292, 166, 388, 204), TEXT["portable"], font(26, True), "white", "black", 2)
    draw_center(draw, (4, 184, 370, 214), TEXT["secret"], fit_font(TEXT["secret"], 340, 24, 14, True), "white", "black", 1)
    draw_center(draw, (0, 222, 330, 250), TEXT["start"], fit_font(TEXT["start"], 320, 22, 12, True), "white", "black", 1)
    for y, key in [(124, "new"), (144, "continue"), (164, "memory"), (187, "bonus")]:
        draw_center(draw, (392, y, 510, y + 18), TEXT[key], font(16, True), "white", "black", 1)
    draw_center(draw, (458, 2, 510, 26), TEXT["settings"], font(18, True), "white", "black", 1)

    return image.convert("L").point(lambda v: round(v / 17) * 17)


def encode_png_under_size(image: Image.Image, max_size: int) -> bytes:
    candidates = []
    for colors in (256, 128, 64, 32, 16):
        quant = image.convert("P", palette=Image.Palette.ADAPTIVE, colors=colors)
        bio = io.BytesIO()
        quant.save(bio, format="PNG", optimize=True, compress_level=9)
        candidates.append(bio.getvalue())
    rgb = image.convert("RGB")
    bio = io.BytesIO()
    rgb.save(bio, format="PNG", optimize=True, compress_level=9)
    candidates.append(bio.getvalue())
    candidates = sorted(candidates, key=len)
    for data in candidates:
        if len(data) <= max_size:
            return data
    raise ValueError(f"PNG replacement too large: best={len(candidates[0])}, max={max_size}")


def make_logo(size: tuple[int, int], source: Path, favorite: bool) -> Image.Image:
    if favorite:
        base = Image.open(source).convert("RGB").resize(size)
        image = base.convert("RGBA")
        overlay = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        w, h = size
        draw.rounded_rectangle((8, 8, w - 8, h - 8), radius=8, fill=(15, 25, 20, 255), outline=(255, 225, 40, 255), width=3)
        image = Image.alpha_composite(image, overlay)
        draw = ImageDraw.Draw(image)
        draw_center(draw, (14, 14, w - 14, h - 30), TEXT["favorite"], fit_font(TEXT["favorite"], w - 36, 24 if h < 100 else 52, 12, True), (255, 235, 45, 255), (35, 45, 10, 255), 2 if h < 100 else 3)
        draw_center(draw, (18, h - 32, w - 18, h - 8), TEXT["sumo"], fit_font(TEXT["sumo"], w - 40, 14 if h < 100 else 28, 8, True), (255, 255, 255, 255), (0, 0, 0, 255), 1 if h < 100 else 2)
        return image.convert("RGB")

    base = Image.open(source).convert("RGB").resize(size)
    image = base.convert("RGBA")
    draw = ImageDraw.Draw(image)
    w, h = size
    top = 18 if h <= 90 else 30
    bottom = 62 if h <= 90 else 118
    draw.rounded_rectangle((10, top, w - 10, bottom), radius=8, fill=(18, 54, 96, 150))
    draw_center(draw, (14, top + 1, w - 14, top + (26 if h <= 90 else 54)), TEXT["title"], fit_font(TEXT["title"], w - 34, 24 if h <= 90 else 58, 14, True), (255, 255, 255, 255), (20, 65, 125, 255), 2 if h <= 90 else 3)
    draw_center(draw, (20, top + (25 if h <= 90 else 52), w - 20, bottom - 2), TEXT["portable"], fit_font(TEXT["portable"], w - 60, 13 if h <= 90 else 28, 8, True), (255, 226, 60, 255), (50, 70, 40, 255), 1 if h <= 90 else 2)
    return image.convert("RGB")


def replace_png_blobs_in_gzx(src: Path, dst: Path, replacements: dict[str, Path]) -> None:
    original = src.read_bytes()
    payload = bytearray(gzip.decompress(original[4:]))
    entries = boku_tools.parse_pack_entries(payload, with_names=True)
    for entry in entries:
        if entry["name"] not in replacements:
            continue
        old = bytes(payload[entry["offset"] : entry["offset"] + entry["size"]])
        repl = replacements[entry["name"]].read_bytes()
        if len(repl) > len(old):
            raise ValueError(f"{src.name}/{entry['name']} replacement grew: {len(old)} -> {len(repl)}")
        payload[entry["offset"] : entry["offset"] + entry["size"]] = repl + b"\0" * (len(old) - len(repl))
    dst.parent.mkdir(parents=True, exist_ok=True)
    rebuilt = boku_tools.make_gzip(bytes(payload), original)
    if len(rebuilt) > len(original):
        raise ValueError(f"{src.name} compressed replacement grew: {len(original)} -> {len(rebuilt)}")
    dst.write_bytes(rebuilt + b"\0" * (len(original) - len(rebuilt)))


def extract_base_entry(rel: str, out: Path) -> Path:
    entries = boku_tools.parse_index(BASE_BUILD / "cdimg.idx")
    entry = next(item for item in entries if item.path == rel)
    with (BASE_BUILD / "cdimg0.img").open("rb") as handle:
        handle.seek(entry.offset)
        data = handle.read(entry.size)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return out


def patch_title_bin(src: Path, dst: Path, patched_image: Image.Image) -> None:
    data = bytearray(src.read_bytes())
    offset = 0x40480
    image_data = bytearray(data[offset:])
    image_offset, data_size, width, height = boku_tools.pim2_4bpp_info(image_data)
    if (width, height) != patched_image.size:
        raise ValueError(f"title image size mismatch: {(width, height)} vs {patched_image.size}")
    linear = bytearray(width * height // 2)
    pixels = patched_image.convert("L")
    for y in range(height):
        for x in range(0, width, 2):
            lo = pixels.getpixel((x, y)) >> 4
            hi = pixels.getpixel((x + 1, y)) >> 4
            linear[y * (width // 2) + x // 2] = (hi << 4) | lo
    swizzled = boku_tools.swizzle_4bpp(bytes(linear), width, height)
    image_data[image_offset : image_offset + data_size] = swizzled
    data[offset : offset + len(image_data)] = image_data
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)


def decode_pim2_from_blob(blob: bytes, offset: int) -> Image.Image:
    image_data = blob[offset:]
    image_offset, data_size, width, height = boku_tools.pim2_4bpp_info(image_data)
    raw = image_data[image_offset : image_offset + data_size]
    linear = boku_tools.unswizzle_4bpp(raw, width, height)
    image = Image.new("L", (width, height), 0)
    pix = image.load()
    for y in range(height):
        row = y * (width // 2)
        for x in range(0, width, 2):
            b = linear[row + x // 2]
            pix[x, y] = (b & 0x0F) * 17
            pix[x + 1, y] = (b >> 4) * 17
    return image


def encode_pim2_into_blob(blob: bytearray, offset: int, image: Image.Image) -> None:
    image_data = bytearray(blob[offset:])
    image_offset, data_size, width, height = boku_tools.pim2_4bpp_info(image_data)
    if image.size != (width, height):
        raise ValueError(f"PIM2 size mismatch: {image.size} vs {(width, height)}")
    pixels = image.convert("L").point(lambda v: round(v / 17) * 17)
    linear = bytearray(width * height // 2)
    for y in range(height):
        for x in range(0, width, 2):
            lo = pixels.getpixel((x, y)) >> 4
            hi = pixels.getpixel((x + 1, y)) >> 4
            linear[y * (width // 2) + x // 2] = (hi << 4) | lo
    image_data[image_offset : image_offset + data_size] = boku_tools.swizzle_4bpp(bytes(linear), width, height)
    blob[offset : offset + len(image_data)] = image_data


def draw_menu_label(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, size: int = 13) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1, y1, x2, y2), radius=4, fill=255)
    draw_center(draw, box, text, fit_font(text, x2 - x1 - 4, size, 7, True), 70, 255, 0)


def patch_0sub(image: Image.Image) -> Image.Image:
    img = image.convert("L")
    draw = ImageDraw.Draw(img)
    for box, text, size in [
        ((127, 20, 180, 55), "연날리기", 12),
        ((190, 20, 244, 55), "낚시도구", 11),
        ((126, 78, 181, 116), "채집세트", 11),
        ((190, 82, 244, 116), "빈손", 14),
        ((5, 126, 55, 160), "잠자리채", 10),
        ((67, 130, 119, 162), "돌아가기", 10),
        ((130, 139, 181, 171), "설정", 14),
        ((191, 139, 247, 171), "소지품", 12),
    ]:
        draw_menu_label(draw, box, text, size)
    return img


def patch_item(image: Image.Image) -> Image.Image:
    img = image.convert("L")
    draw = ImageDraw.Draw(img)
    draw_menu_label(draw, (3, 10, 55, 42), "소지품", 12)
    return img


def patch_kite_book(image: Image.Image) -> Image.Image:
    img = image.convert("L")
    draw = ImageDraw.Draw(img)
    draw_menu_label(draw, (3, 4, 57, 39), "확인", 14)
    return img


def patch_kite_select(image: Image.Image) -> Image.Image:
    img = image.convert("L")
    draw = ImageDraw.Draw(img)
    draw_menu_label(draw, (5, 5, 57, 40), "연날리기", 10)
    return img


def patch_diary_icon(image: Image.Image) -> Image.Image:
    img = image.convert("L")
    draw = ImageDraw.Draw(img)
    draw_menu_label(draw, (3, 6, 58, 42), "휴식", 15)
    return img


def patch_specimen(image: Image.Image) -> Image.Image:
    img = image.convert("L")
    draw = ImageDraw.Draw(img)
    labels = [
        ((6, 17, 56, 53), "곤충\n채집"),
        ((72, 17, 123, 53), "곤충\n씨름"),
        ((139, 17, 190, 53), "주의"),
        ((207, 17, 258, 53), "표본\n삭제"),
        ((275, 17, 326, 53), "이전"),
        ((344, 17, 405, 53), "점보"),
        ((6, 86, 56, 123), "놓아\n주기"),
        ((72, 86, 123, 123), "약"),
        ((139, 86, 190, 123), "채집함"),
        ((207, 86, 258, 123), "종류\n목록"),
        ((275, 86, 326, 123), "다음"),
        ((344, 86, 405, 123), "편집"),
    ]
    for box, text in labels:
        draw_menu_label(draw, box, text, 12)
    return img


def patch_sumo_menu(image: Image.Image) -> Image.Image:
    img = image.convert("L")
    draw = ImageDraw.Draw(img)
    for box, text, size in [
        ((9, 61, 62, 101), "곤충\n교환", 11),
        ((77, 61, 129, 101), "곤충\n상자", 11),
        ((9, 126, 62, 166), "랭크", 13),
        ((77, 126, 129, 166), "배치", 13),
        ((146, 126, 198, 166), "대회", 13),
        ((292, 41, 345, 82), "놓아\n주기", 11),
        ((291, 105, 344, 144), "내 정보", 10),
    ]:
        draw_menu_label(draw, box, text, size)
    draw.rectangle((205, 165, 248, 186), fill=70)
    draw_center(draw, (205, 165, 248, 186), "스태미나", fit_font("스태미나", 41, 12, 7, True), 255, 70, 0)
    draw.rectangle((256, 165, 306, 186), fill=70)
    draw_center(draw, (256, 165, 306, 186), "교환", font(12, True), 255, 70, 0)
    return img


def patch_sumo_moves(image: Image.Image) -> Image.Image:
    img = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(img)
    moves_top = ["들이받기", "물기", "집게", "밀어내기", "밀치기", "버티기", "박치기", "넘기기", "파고들기", "되치기", "누르기", "찍기"]
    moves_bottom = ["필살", "보기", "뒤집기", "잡기", "올려치기", "다리걸기", "조르기", "밀어붙이기", "회피", "버티기", "속공", "돌진"]
    x_positions = [4, 38, 72, 106, 140, 174, 208, 242, 276, 310, 344, 378]
    f = font(17, True)
    def draw_vertical_text(x: int, y: int, text: str) -> None:
        yy = y
        for ch in text:
            bbox = draw.textbbox((0, 0), ch, font=f, stroke_width=1)
            w = bbox[2] - bbox[0]
            draw.text((x + (24 - w) // 2, yy), ch, font=f, fill=255, stroke_width=1, stroke_fill=0)
            yy += 18
    for x, text in zip(x_positions, moves_top):
        draw_vertical_text(x, 4, text)
    for x, text in zip(x_positions, moves_bottom):
        draw_vertical_text(x, 245, text)
    return img


def patch_pim2_file_from_base(rel: str, offset: int, patcher, preview_name: str) -> None:
    base = extract_base_entry(rel, OUT / ("base_" + rel.replace("/", "__")))
    data = bytearray(base.read_bytes())
    image = decode_pim2_from_blob(bytes(data), offset)
    patched = patcher(image)
    patched.save(OUT / preview_name)
    encode_pim2_into_blob(data, offset, patched)
    target = REPLACEMENTS / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def patch_pim2_file_multi_from_base(rel: str, patches: list[tuple[int, object, str]]) -> None:
    base = extract_base_entry(rel, OUT / ("base_" + rel.replace("/", "__")))
    data = bytearray(base.read_bytes())
    for offset, patcher, preview_name in patches:
        image = decode_pim2_from_blob(bytes(data), offset)
        patched = patcher(image)
        patched.save(OUT / preview_name)
        encode_pim2_into_blob(data, offset, patched)
    target = REPLACEMENTS / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def patch_pim2_gzx_from_base(rel: str, offset: int, patcher, preview_name: str) -> None:
    base = extract_base_entry(rel, OUT / ("base_" + rel.replace("/", "__")))
    original = base.read_bytes()
    payload = bytearray(gzip.decompress(original[4:]))
    image = decode_pim2_from_blob(bytes(payload), offset)
    patched = patcher(image)
    patched.save(OUT / preview_name)
    encode_pim2_into_blob(payload, offset, patched)
    rebuilt = boku_tools.make_gzip(bytes(payload), original)
    if len(rebuilt) > len(original):
        raise ValueError(f"{rel} compressed PIM2 replacement grew: {len(original)} -> {len(rebuilt)}")
    target = REPLACEMENTS / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(rebuilt + b"\0" * (len(original) - len(rebuilt)))


def main() -> None:
    patched_files = [
        "map/models/title/title.bin",
        "map/models/system/saveload_normal.bin.gzx",
        "map/models/system/saveload_favorite.bin.gzx",
        "map/models/sub/0sub.bin.gzx",
        "map/models/sub/item.bin.gzx",
        "map/models/sub/specimen2.bin",
        "map/models/sub/sumo.dat",
        "map/models/sub/kite_book.bin",
        "map/models/sub/kite_select.bin.gzx",
        "diary/icon.bin",
    ]
    preview_files = []
    OUT.mkdir(parents=True, exist_ok=True)
    if REPLACEMENTS.exists():
        shutil.rmtree(REPLACEMENTS)
    shutil.copytree(BASE_REPLACEMENTS, REPLACEMENTS)
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)

    title = patch_title_preview()
    title_preview = OUT / "title_pim2_01_patched_preview.png"
    title.save(title_preview)
    preview_files.append(title_preview)
    patch_title_bin(EXTRACT / "map/models/title/title.bin", REPLACEMENTS / "map/models/title/title.bin", title)

    source_images = {
        "normal_icon": ROOT / "work/image_text_survey/images/map__models__system__saveload_normal.bin.gzx__gzip__png_00.png",
        "normal_pic": ROOT / "work/image_text_survey/images/map__models__system__saveload_normal.bin.gzx__gzip__png_01.png",
        "fav_icon": ROOT / "work/image_text_survey/images/map__models__system__saveload_favorite.bin.gzx__gzip__png_00.png",
        "fav_pic": ROOT / "work/image_text_survey/images/map__models__system__saveload_favorite.bin.gzx__gzip__png_01.png",
    }
    generated = {}
    for key, src in source_images.items():
        old = Image.open(src)
        img = make_logo(old.size, src, favorite=key.startswith("fav"))
        max_size = src.stat().st_size
        png = encode_png_under_size(img, max_size)
        out = OUT / f"{key}_patched.png"
        out.write_bytes(png)
        generated[key] = out
        preview_files.append(out)

    base_normal = extract_base_entry("map/models/system/saveload_normal.bin.gzx", OUT / "base_saveload_normal.bin.gzx")
    base_favorite = extract_base_entry("map/models/system/saveload_favorite.bin.gzx", OUT / "base_saveload_favorite.bin.gzx")

    replace_png_blobs_in_gzx(
        base_normal,
        REPLACEMENTS / "map/models/system/saveload_normal.bin.gzx",
        {"ICON0.PNG": generated["normal_icon"], "PIC1.PNG": generated["normal_pic"]},
    )
    replace_png_blobs_in_gzx(
        base_favorite,
        REPLACEMENTS / "map/models/system/saveload_favorite.bin.gzx",
        {"ICON0.png": generated["fav_icon"], "PIC1.PNG": generated["fav_pic"]},
    )

    patch_pim2_gzx_from_base("map/models/sub/0sub.bin.gzx", 0x40, patch_0sub, "sub_0sub_patched.png")
    preview_files.append(OUT / "sub_0sub_patched.png")
    patch_pim2_gzx_from_base("map/models/sub/item.bin.gzx", 0xB6CC0, patch_item, "sub_item_patched.png")
    preview_files.append(OUT / "sub_item_patched.png")
    patch_pim2_file_from_base("map/models/sub/specimen2.bin", 0x60, patch_specimen, "sub_specimen2_patched.png")
    preview_files.append(OUT / "sub_specimen2_patched.png")
    patch_pim2_file_multi_from_base(
        "map/models/sub/sumo.dat",
        [
            (0x6AB40, patch_sumo_menu, "sub_sumo_menu_patched.png"),
            (0x73340, patch_sumo_moves, "sub_sumo_moves_patched.png"),
        ],
    )
    preview_files.extend([OUT / "sub_sumo_menu_patched.png", OUT / "sub_sumo_moves_patched.png"])
    patch_pim2_file_from_base("map/models/sub/kite_book.bin", 0x80, patch_kite_book, "sub_kite_book_patched.png")
    preview_files.append(OUT / "sub_kite_book_patched.png")
    patch_pim2_gzx_from_base("map/models/sub/kite_select.bin.gzx", 0x5F5C0, patch_kite_select, "sub_kite_select_patched.png")
    preview_files.append(OUT / "sub_kite_select_patched.png")
    patch_pim2_file_from_base("diary/icon.bin", 0x20C0, patch_diary_icon, "diary_icon_patched.png")
    preview_files.append(OUT / "diary_icon_patched.png")

    boku_tools.rebuild_cdimg(
        BASE_BUILD / "cdimg.idx",
        BASE_BUILD / "cdimg0.img",
        EXTRACT,
        REPLACEMENTS,
        BUILD / "cdimg.idx",
        BUILD / "cdimg0.img",
    )

    report = {
        "patched_files": patched_files,
        "previews": [str(path) for path in preview_files],
        "build": {
            "cdimg.idx": hashlib.md5((BUILD / "cdimg.idx").read_bytes()).hexdigest().upper(),
            "cdimg0.img": hashlib.md5((BUILD / "cdimg0.img").read_bytes()).hexdigest().upper(),
        },
    }
    (ROOT / "outputs/title_system_image_patch_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

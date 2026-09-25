import ctypes
from dataclasses import dataclass
import re
from typing import Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageGrab, ImageOps
import winocr


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor_pos() -> Tuple[int, int]:
    """Возвращает текущие экранные координаты курсора мыши через Win32 API."""
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


# Эталонные битовые маски (9x15) шрифта перекрестия HUD для резервного геометрического распознавания
_GLYPH_TEMPLATES: dict[str, list[list[int]]] = {
    ch: [[1 if c == "#" else 0 for c in row] for row in rows]
    for ch, rows in {
        "0": [
            "..#####..", ".#######.", ".##...##.", "##....###", "##.....##",
            "##.....##", "##.....##", "##.....##", "##.....##", "##.....##",
            "##.....##", "##....##.", ".##...##.", ".#######.", "..####...",
        ],
        "1": [
            "...######", "#########", "####.####", ".....####", ".....####",
            ".....####", ".....####", ".....####", ".....####", ".....####",
            ".....####", ".....####", ".....####", ".....####", ".....####",
        ],
        "2": [
            "..#####..", ".#######.", "###...###", "##.....##", ".......##",
            "......###", ".....###.", "....###..", "...###...", "..###....",
            ".###.....", "###......", "##.......", "#########", "#########",
        ],
        "3": [
            "..#####..", ".#######.", "###...###", ".......##", ".......##",
            "......##.", "..#####..", "..######.", ".......##", ".......##",
            ".......##", "##.....##", "###...###", ".#######.", "..#####..",
        ],
        "4": [
            ".....###.", "....####.", "...#####.", "...##.##.", "..##..##.",
            ".##...##.", ".##...##.", "##....##.", "##....##.", "#########",
            "#########", "......##.", "......##.", "......##.", "......##.",
        ],
        "5": [
            "#########", "#########", "##.......", "##.......", "##.......",
            "#######..", "########.", "##....###", ".......##", ".......##",
            ".......##", "##.....##", "###...###", ".#######.", "..#####..",
        ],
        "6": [
            "..#####..", ".#######.", "###...##.", "##.....#.", "##.......",
            "##.####..", "########.", "###...###", "##.....##", "##.....##",
            "##.....##", "##.....##", ".##...###", ".#######.", "..#####..",
        ],
        "7": [
            "#########", "#########", "#.....##.", "......##.", ".....###.",
            ".....##..", ".....##..", "....###..", "....##...", "....##...",
            "...##....", "...##....", "...##....", "..##.....", "..##.....",
        ],
        "8": [
            "..#####..", ".#######.", "###...##.", "##.....##", "##.....##",
            ".##...##.", ".######..", ".#######.", "###...##.", "##.....##",
            "##.....##", "##.....##", "###...###", ".#######.", "..#####..",
        ],
        "9": [
            "..#####..", ".#######.", "###...##.", "##.....##", "##.....##",
            "##.....##", "###...###", ".########", "..####.##", ".......##",
            ".#.....##", "##.....##", ".##...###", ".#######.", "..#####..",
        ],
        "x": [
            "##....###", "##....##.", ".##...##.", ".##..##..", "..##.##..",
            "..####...", "...###...", "...##....", "...###...", "..####...",
            "..##.##..", ".##..##..", ".##...##.", "##....##.", "##.....##",
        ],
        "y": [
            "##.....##", "##.....##", "##.....##", ".##...##.", ".##...##.",
            ".##...##.", "..##.##..", "..#####..", "...###...", "...###...",
            "...###...", "...##....", "...##....", "####.....", "###......",
        ],
    }.items()
}


@dataclass
class LiteScanResult:
    success: bool
    x: Optional[float]
    y: Optional[float]
    preview_image: Image.Image
    raw_texts: list[str]
    error_msg: str = ""


class LiteCoordinateScanner:
    """
    Сканер координат, использует встроенный системный движок Windows 10/11 (Windows.Media.Ocr) и Pillow
    с ахроматической фильтрацией цветовых перекрытий (красный, зелёный, синий, жёлтый)
    и резервным геометрическим сопоставлением глифов.
    """

    @staticmethod
    def _normalize_number_str(num_str: str) -> Optional[float]:
        num_str = num_str.strip().replace(",", ".")
        try:
            val = float(num_str)
            if "." not in num_str and val >= 1000:
                val = val / 100.0
            return round(val, 2)
        except ValueError:
            return None

    @staticmethod
    def _build_achromatic_channel(img_rgb: Image.Image, chroma_penalty: float = 0.75) -> Image.Image:
        """
        Выделяет нейтрально-белый текст координат и подавляет цветные элементы карты
        (красные/зелёные/синие/жёлтые зоны, маркеры, радиусы).
        """
        r, g, b = img_rgb.split()
        min_rgb = ImageChops.darker(ImageChops.darker(r, g), b)
        if chroma_penalty > 0:
            max_rgb = ImageChops.lighter(ImageChops.lighter(r, g), b)
            spread = ImageChops.subtract(max_rgb, min_rgb).point(lambda p: int(p * chroma_penalty))
            return ImageChops.subtract(min_rgb, spread)
        return min_rgb

    @classmethod
    def _bitmask_fallback_scan(
        cls, gray_channel: Image.Image, thresh: int = 125
    ) -> list[Tuple[str, float, Tuple[int, int, int, int]]]:
        w, h = gray_channel.size
        px = gray_channel.load()
        visited = [[False] * w for _ in range(h)]
        blobs = []

        for y in range(h):
            for x in range(w):
                if px[x, y] >= thresh and not visited[y][x]:
                    q = [(x, y)]
                    visited[y][x] = True
                    minx = maxx = x
                    miny = maxy = y
                    cnt = 0
                    while q:
                        cx, cy = q.pop()
                        cnt += 1
                        if cx < minx:
                            minx = cx
                        if cx > maxx:
                            maxx = cx
                        if cy < miny:
                            miny = cy
                        if cy > maxy:
                            maxy = cy
                        for nx, ny in (
                            (cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1),
                            (cx - 1, cy - 1), (cx + 1, cy - 1), (cx - 1, cy + 1), (cx + 1, cy + 1),
                        ):
                            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx] and px[nx, ny] >= thresh:
                                visited[ny][nx] = True
                                q.append((nx, ny))
                    bw, bh = maxx - minx + 1, maxy - miny + 1
                    if (4 <= bw <= 14 and 9 <= bh <= 24) or (1 <= bw <= 4 and 1 <= bh <= 4 and cnt >= 2):
                        blobs.append((minx, miny, maxx, maxy, bw, bh))

        tall = [b for b in blobs if 10 <= b[5] <= 22 and 4 <= b[4] <= 13]
        dots = [b for b in blobs if 1 <= b[4] <= 4 and 1 <= b[5] <= 4]
        tall.sort(key=lambda b: (b[1] // 12, b[0]))

        lines: list[list[tuple]] = []
        for b in tall:
            placed = False
            for line in lines:
                last = line[-1]
                if abs(b[1] - last[1]) <= 6 and 0 <= (b[0] - last[2]) <= 16:
                    line.append(b)
                    placed = True
                    break
            if not placed:
                lines.append([b])

        results: list[Tuple[str, float, Tuple[int, int, int, int]]] = []
        for line in lines:
            if len(line) < 4:
                continue
            l_minx, l_maxx = line[0][0], line[-1][2]
            baseline = max(b[3] for b in line[1:])
            line_dots = [d for d in dots if l_minx < d[0] < l_maxx and abs(d[3] - baseline) <= 4]
            if not line_dots:
                continue
            dot = line_dots[0]
            first = line[0]

            if first[3] >= baseline + 2:
                axis = "y"
            elif first[1] >= line[1][1] + 2:
                axis = "x"
            else:
                axis = "x" if first[5] < line[1][5] else "y"

            int_d, frac_d = [], []
            for b in line[1:]:
                if b[4] / max(1, b[5]) <= 0.44:
                    ch = "1"
                else:
                    crop = gray_channel.crop((b[0], b[1], b[2] + 1, b[3] + 1)).resize(
                        (9, 15), Image.Resampling.BILINEAR
                    )
                    vals = list(crop.tobytes())
                    t_loc = max(100, int((min(vals) + max(vals)) * 0.52))
                    mat = [[1 if vals[r * 9 + c] >= t_loc else 0 for c in range(9)] for r in range(15)]
                    best_ch, best_sc = "0", -1
                    for cand in "0123456789":
                        tmpl = _GLYPH_TEMPLATES[cand]
                        sc = sum(1 for r in range(15) for c in range(9) if mat[r][c] == tmpl[r][c])
                        if sc > best_sc:
                            best_sc, best_ch = sc, cand
                    ch = best_ch
                if b[2] < dot[0]:
                    int_d.append(ch)
                elif b[0] > dot[2]:
                    frac_d.append(ch)

            if int_d and len(frac_d) >= 2:
                try:
                    val = round(float(f"{''.join(int_d)}.{''.join(frac_d[:2])}"), 2)
                    rect = (
                        min(b[0] for b in line),
                        min(b[1] for b in line),
                        max(b[2] for b in line),
                        max(b[3] for b in line),
                    )
                    results.append((axis, val, rect))
                except ValueError:
                    pass
        return results

    def extract_coordinates_from_pil(self, img: Image.Image) -> LiteScanResult:
        rgb_img = img.convert("RGB")
        annotated = rgb_img.copy()
        draw = ImageDraw.Draw(annotated)

        w, h = rgb_img.size

        found_x: Optional[float] = None
        found_y: Optional[float] = None
        raw_texts: list[str] = []
        unassigned_decimals: list[Tuple[float, float, Tuple[float, float, float, float]]] = []

        def parse_winocr_dict(ocr_dict: dict, cur_scale: int) -> None:
            nonlocal found_x, found_y
            lines = ocr_dict.get("lines", []) if isinstance(ocr_dict, dict) else []
            for line in lines:
                line_text = line.get("text", "")
                if line_text and line_text not in raw_texts:
                    raw_texts.append(line_text)
                cleaned = (
                    line_text.strip()
                    .replace(",", ".")
                    .replace("х", "x")
                    .replace("Х", "X")
                    .replace("у", "y")
                    .replace("У", "Y")
                    .replace("×", "x")
                )
                cleaned = re.sub(r"(?<=[xXyYvV\d\.])\s+(?=[\d\.])", "", cleaned)

                words = line.get("words", [])
                if words:
                    x0 = min(wd["bounding_rect"]["x"] for wd in words) / cur_scale
                    y0 = min(wd["bounding_rect"]["y"] for wd in words) / cur_scale
                    x1 = max(wd["bounding_rect"]["x"] + wd["bounding_rect"]["width"] for wd in words) / cur_scale
                    y1 = max(wd["bounding_rect"]["y"] + wd["bounding_rect"]["height"] for wd in words) / cur_scale
                else:
                    x0, y0, x1, y1 = 0.0, 0.0, 10.0, 10.0

                center_y = (y0 + y1) * 0.5
                rect = (x0, y0, x1, y1)

                mx = re.search(r"[xX](\d{1,3}\.\d{2}|\d{4,5})\b", cleaned)
                if mx and found_x is None:
                    val = self._normalize_number_str(mx.group(1))
                    if val is not None:
                        found_x = val
                        draw.rectangle(rect, outline="#00ffb4", width=2)
                        continue

                my = re.search(r"[yYvV](\d{1,3}\.\d{2}|\d{4,5})\b", cleaned)
                if my and found_y is None:
                    val = self._normalize_number_str(my.group(1))
                    if val is not None:
                        found_y = val
                        draw.rectangle(rect, outline="#38bdf8", width=2)
                        continue

                m_dec = re.search(r"\b(\d{1,3}\.\d{2})\b", cleaned)
                if m_dec:
                    val = self._normalize_number_str(m_dec.group(1))
                    if val is not None:
                        unassigned_decimals.append((center_y, val, rect))

        scale_ach = 3

        # Проход 1: Канал min(R,G,B) с мягким подавлением насыщенности (chroma_penalty=0.15).
        # Сохраняет сглаженные края белых цифр поверх цветных колец/зон (не съедая дуги '8' и '0'),
        # при этом полностью гасит красные, зелёные, синие и жёлтые перекрытия.
        ach_clean = self._build_achromatic_channel(rgb_img, chroma_penalty=0.15)
        for thr in (125, 145):
            if found_x is not None and found_y is not None:
                break
            ach_bw = (
                ach_clean.resize((w * scale_ach, h * scale_ach), Image.Resampling.BICUBIC)
                .point(lambda p, t=thr: 0 if p >= t else 255)
                .convert("RGB")
            )
            parse_winocr_dict(winocr.recognize_pil_sync(ach_bw, lang="en"), scale_ach)

        # Проход 2: Плавный ахроматический фильтр без бинаризации
        if found_x is None or found_y is None:
            ach_smooth = (
                ImageOps.invert(ImageOps.autocontrast(ach_clean, cutoff=1))
                .resize((w * scale_ach, h * scale_ach), Image.Resampling.BICUBIC)
                .convert("RGB")
            )
            parse_winocr_dict(winocr.recognize_pil_sync(ach_smooth, lang="en"), scale_ach)

        # Проход 3: Мягкое 2x масштабирование оригинала
        if found_x is None or found_y is None:
            scale_rgb = 2
            upscaled = rgb_img.resize((w * scale_rgb, h * scale_rgb), Image.Resampling.LANCZOS)
            parse_winocr_dict(winocr.recognize_pil_sync(upscaled, lang="en"), scale_rgb)

        # Проход 4: Геометрический Bitmask-фоллбэк по контурам глифов
        if found_x is None or found_y is None:
            for ch_img, thr in ((ach_clean, 145), (ach_clean, 120)):
                for axis, val, rect in self._bitmask_fallback_scan(ch_img, thresh=thr):
                    if axis == "x" and found_x is None:
                        found_x = val
                        raw_texts.append(f"x{val:.2f}")
                        draw.rectangle(rect, outline="#00ffb4", width=2)
                    elif axis == "y" and found_y is None:
                        found_y = val
                        raw_texts.append(f"y{val:.2f}")
                        draw.rectangle(rect, outline="#38bdf8", width=2)
                if found_x is not None and found_y is not None:
                    break

        # Позиционный фоллбэк - Y всегда выше X на перекрестии
        if (found_x is None or found_y is None) and unassigned_decimals:
            unassigned_decimals.sort(key=lambda item: item[0])
            if found_y is None and found_x is None and len(unassigned_decimals) >= 2:
                found_y = unassigned_decimals[0][1]
                found_x = unassigned_decimals[1][1]
                draw.rectangle(unassigned_decimals[0][2], outline="#38bdf8", width=2)
                draw.rectangle(unassigned_decimals[1][2], outline="#00ffb4", width=2)
            elif found_y is None and len(unassigned_decimals) >= 1:
                found_y = unassigned_decimals[0][1]
                draw.rectangle(unassigned_decimals[0][2], outline="#38bdf8", width=2)
            elif found_x is None and len(unassigned_decimals) >= 1:
                found_x = unassigned_decimals[-1][1]
                draw.rectangle(unassigned_decimals[-1][2], outline="#00ffb4", width=2)

        success = (found_x is not None) and (found_y is not None)
        err = "" if success else "Не удалось считать обе координаты (X/Y) около курсора"

        return LiteScanResult(
            success=success,
            x=found_x,
            y=found_y,
            preview_image=annotated,
            raw_texts=raw_texts,
            error_msg=err,
        )

    def scan_around_cursor(self, capture_size: int = 320) -> LiteScanResult:
        cx, cy = get_cursor_pos()
        half = capture_size // 2
        left = max(0, cx - int(half * 0.85))
        top = max(0, cy - int(half * 1.15))
        bbox = (left, top, left + capture_size, top + capture_size)

        img = ImageGrab.grab(bbox=bbox, all_screens=True)
        return self.extract_coordinates_from_pil(img)

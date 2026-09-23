import ctypes
from dataclasses import dataclass
import re
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageGrab, ImageOps
import winocr


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor_pos() -> Tuple[int, int]:
    """Возвращает текущие экранные координаты курсора мыши через Win32 API."""
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


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
    Сканер координат, использует встроенный системный движок Windows 10/11 (Windows.Media.Ocr) и Pillow.
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

    def extract_coordinates_from_pil(self, img: Image.Image) -> LiteScanResult:
        rgb_img = img.convert("RGB")
        annotated = rgb_img.copy()
        draw = ImageDraw.Draw(annotated)

        w, h = rgb_img.size
        scale = 2
        upscaled = rgb_img.resize((w * scale, h * scale), Image.Resampling.LANCZOS)

        found_x: Optional[float] = None
        found_y: Optional[float] = None
        raw_texts: list[str] = []
        unassigned_decimals: list[Tuple[float, float, Tuple[float, float, float, float]]] = []

        def parse_winocr_dict(ocr_dict: dict) -> None:
            nonlocal found_x, found_y
            lines = ocr_dict.get("lines", []) if isinstance(ocr_dict, dict) else []
            for line in lines:
                line_text = line.get("text", "")
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

                # Вычисляем прямоугольник строки из слов
                words = line.get("words", [])
                if words:
                    x0 = min(wd["bounding_rect"]["x"] for wd in words) / scale
                    y0 = min(wd["bounding_rect"]["y"] for wd in words) / scale
                    x1 = max(wd["bounding_rect"]["x"] + wd["bounding_rect"]["width"] for wd in words) / scale
                    y1 = max(wd["bounding_rect"]["y"] + wd["bounding_rect"]["height"] for wd in words) / scale
                else:
                    x0, y0, x1, y1 = 0.0, 0.0, 10.0, 10.0

                center_y = (y0 + y1) * 0.5
                rect = (x0, y0, x1, y1)

                # Ищем явный X (например x98.90 или X98.90)
                mx = re.search(r"[xX]\s*(\d{1,4}(?:\.\d{1,2})?)", cleaned)
                if mx and found_x is None:
                    val = self._normalize_number_str(mx.group(1))
                    if val is not None:
                        found_x = val
                        draw.rectangle(rect, outline="#00ffb4", width=2)
                        continue

                # Ищем явный Y (например y109.79 или v109.79)
                my = re.search(r"[yYvV]\s*(\d{1,4}(?:\.\d{1,2})?)", cleaned)
                if my and found_y is None:
                    val = self._normalize_number_str(my.group(1))
                    if val is not None:
                        found_y = val
                        draw.rectangle(rect, outline="#38bdf8", width=2)
                        continue

                m_dec = re.search(r"\b(\d{1,3}\.\d{1,2})\b", cleaned)
                if m_dec:
                    val = self._normalize_number_str(m_dec.group(1))
                    if val is not None:
                        unassigned_decimals.append((center_y, val, rect))

        # Проход 1: 2x LANCZOS через системный Windows OCR
        res1 = winocr.recognize_pil_sync(upscaled, lang="en")
        parse_winocr_dict(res1)

        # Проход 2: инвертированный контрастный вариант, если одна из осей не считалась
        if found_x is None or found_y is None:
            inv = ImageOps.invert(rgb_img.convert("L")).resize(
                (w * scale, h * scale), Image.Resampling.LANCZOS
            )
            res2 = winocr.recognize_pil_sync(inv, lang="en")
            parse_winocr_dict(res2)

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

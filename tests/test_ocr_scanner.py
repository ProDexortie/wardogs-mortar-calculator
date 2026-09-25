import unittest
from PIL import Image, ImageDraw, ImageFont
from ocr_scanner_lite import LiteCoordinateScanner


class TestLiteCoordinateScanner(unittest.TestCase):
    def setUp(self) -> None:
        self.scanner = LiteCoordinateScanner()

    def test_normalize_number_str(self) -> None:
        """Проверка нормализации чисел: точки, запятые и пропущенный разделитель сотых."""
        self.assertEqual(self.scanner._normalize_number_str("98.90"), 98.90)
        self.assertEqual(self.scanner._normalize_number_str("109,79"), 109.79)
        self.assertEqual(self.scanner._normalize_number_str("10979"), 109.79)
        self.assertEqual(self.scanner._normalize_number_str("9890"), 98.90)
        self.assertIsNone(self.scanner._normalize_number_str("abc"))

    def test_synthetic_crosshair_ocr(self) -> None:
        """Проверка распознавания координат x и y на сгенерированном изображении перекрестия."""
        img = Image.new("RGB", (320, 320), (22, 27, 34))
        draw = ImageDraw.Draw(img)

        draw.line([(130, 0), (130, 320)], fill=(150, 160, 170), width=1)
        draw.line([(0, 160), (320, 160)], fill=(150, 160, 170), width=1)

        try:
            font = ImageFont.truetype("arial.ttf", 19)
        except Exception:
            font = ImageFont.load_default()

        draw.text((142, 65), "y109.79", fill=(248, 250, 252), font=font)
        draw.text((165, 132), "x98.90", fill=(248, 250, 252), font=font)

        res = self.scanner.extract_coordinates_from_pil(img)
        self.assertTrue(res.success, f"OCR failed with raw_texts={res.raw_texts}")
        self.assertAlmostEqual(res.x or 0.0, 98.90, places=2)
        self.assertAlmostEqual(res.y or 0.0, 109.79, places=2)

    def test_colored_overlays_resilience(self) -> None:
        """Проверка устойчивости распознавания при перекрытии красным, зелёным, синим и жёлтым цветом."""
        for color_rgba in [
            (255, 35, 35, 95),    # Красное перекрытие
            (35, 255, 50, 95),    # Зелёное перекрытие
            (35, 100, 255, 95),   # Синее перекрытие
            (230, 215, 60, 125),  # Жёлтая дуга/зона
        ]:
            with self.subTest(color=color_rgba):
                base = Image.new("RGBA", (320, 320), (28, 32, 38, 255))
                draw = ImageDraw.Draw(base)
                try:
                    font = ImageFont.truetype("arial.ttf", 19)
                except Exception:
                    font = ImageFont.load_default()

                # Рисуем цветную зону/кольцо на карте и поверх неё полупрозрачное перекрытие на тексте
                draw.ellipse((50, 35, 215, 215), fill=color_rgba[:3] + (80,), outline=color_rgba[:3] + (190,), width=3)
                draw.text((145, 75), "y71.61", fill=(245, 248, 250, 255), font=font)
                draw.text((175, 145), "x80.26", fill=(245, 248, 250, 255), font=font)

                tint = Image.new("RGBA", (320, 320), (0, 0, 0, 0))
                tdraw = ImageDraw.Draw(tint)
                tdraw.rectangle((135, 65, 260, 180), fill=color_rgba)

                merged = Image.alpha_composite(base, tint).convert("RGB")
                res = self.scanner.extract_coordinates_from_pil(merged)
                self.assertTrue(res.success, f"Failed for {color_rgba}: raw={res.raw_texts}")
                self.assertAlmostEqual(res.x or 0.0, 80.26, places=2)
                self.assertAlmostEqual(res.y or 0.0, 71.61, places=2)


if __name__ == "__main__":
    unittest.main()

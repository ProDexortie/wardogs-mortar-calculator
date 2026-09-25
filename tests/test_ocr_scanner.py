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

        # Рисуем перекрестие и подписи координат
        draw.line([(130, 0), (130, 320)], fill=(150, 160, 170), width=1)
        draw.line([(0, 160), (320, 160)], fill=(150, 160, 170), width=1)

        try:
            font = ImageFont.truetype("consola.ttf", 20)
        except Exception:
            font = ImageFont.load_default()

        draw.text((142, 65), "y109.79", fill=(248, 250, 252), font=font)
        draw.text((165, 132), "x98.90", fill=(248, 250, 252), font=font)

        res = self.scanner.extract_coordinates_from_pil(img)
        self.assertTrue(res.success, f"OCR failed with raw_texts={res.raw_texts}")
        self.assertAlmostEqual(res.x or 0.0, 98.90, places=2)
        self.assertAlmostEqual(res.y or 0.0, 109.79, places=2)


if __name__ == "__main__":
    unittest.main()

import unittest
from ballistics import (
    MORTAR_TABLE,
    MIN_RANGE_M,
    MAX_RANGE_M,
    calculate_ballistics,
    interpolate_mil,
)


class TestBallistics(unittest.TestCase):
    def test_exact_mortar_table_nodes(self) -> None:
        """Все 17 узловых точек таблицы миномёта должны возвращать точные значения mil."""
        for dist_m, expected_mil in MORTAR_TABLE:
            with self.subTest(dist_m=dist_m):
                mil, status = interpolate_mil(dist_m)
                self.assertEqual(status, "OK")
                self.assertEqual(mil, round(expected_mil))

    def test_interpolation_between_nodes(self) -> None:
        """Кусочно-линейная интерполяция между соседними узлами таблицы."""
        # Между (80м -> 950 mil) и (110м -> 900 mil), середина 95м -> 925 mil
        mil_95, status_95 = interpolate_mil(95.0)
        self.assertEqual(status_95, "OK")
        self.assertEqual(mil_95, 925)

        # Между (430м -> 550 mil) и (470м -> 500 mil), середина 450м -> 525 mil
        mil_450, status_450 = interpolate_mil(450.0)
        self.assertEqual(status_450, "OK")
        self.assertEqual(mil_450, 525)

    def test_out_of_range_bounds(self) -> None:
        """Проверка выхода за минимальную (<80м) и максимальную (>684м) дистанцию."""
        mil_low, status_low = interpolate_mil(MIN_RANGE_M - 0.1)
        self.assertIsNone(mil_low)
        self.assertEqual(status_low, "TOO_CLOSE")

        mil_high, status_high = interpolate_mil(MAX_RANGE_M + 0.1)
        self.assertIsNone(mil_high)
        self.assertEqual(status_high, "TOO_FAR")

    def test_cardinal_azimuths(self) -> None:
        """Проверка расчёта азимута по 4 сторонам света (Север=0°, Восток=90°, Юг=180°, Запад=270°)."""
        # Север (+Y)
        res_n = calculate_ballistics(100.0, 100.0, 100.0, 103.4)
        self.assertEqual(res_n.azimuth_deg, 0.0)
        self.assertEqual(res_n.distance_m, 340)
        self.assertEqual(res_n.elevation_mil, 650)

        # Восток (+X)
        res_e = calculate_ballistics(100.0, 100.0, 104.7, 100.0)
        self.assertEqual(res_e.azimuth_deg, 90.0)
        self.assertEqual(res_e.distance_m, 470)
        self.assertEqual(res_e.elevation_mil, 500)

        # Юг (-Y)
        res_s = calculate_ballistics(100.0, 100.0, 100.0, 97.6)
        self.assertEqual(res_s.azimuth_deg, 180.0)
        self.assertEqual(res_s.distance_m, 240)
        self.assertEqual(res_s.elevation_mil, 750)

        # Запад (-X)
        res_w = calculate_ballistics(100.0, 100.0, 98.9, 100.0)
        self.assertEqual(res_w.azimuth_deg, 270.0)
        self.assertEqual(res_w.distance_m, 110)
        self.assertEqual(res_w.elevation_mil, 900)

    def test_diagonal_and_zero_distance(self) -> None:
        """Проверка диагонального азимута (45°) и нулевой дистанции."""
        res_ne = calculate_ballistics(50.0, 50.0, 52.0, 52.0)
        self.assertEqual(res_ne.azimuth_deg, 45.0)
        self.assertEqual(res_ne.distance_m, 283)

        res_zero = calculate_ballistics(98.90, 109.79, 98.90, 109.79)
        self.assertEqual(res_zero.distance_m, 0)
        self.assertEqual(res_zero.azimuth_deg, 0.0)
        self.assertEqual(res_zero.range_status, "TOO_CLOSE")


if __name__ == "__main__":
    unittest.main()

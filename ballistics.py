from dataclasses import dataclass
import math
from typing import Optional, Tuple

# Таблица расстояний миномёта 
MORTAR_TABLE: list[Tuple[float, float]] = [
    (80.0, 950.0),
    (110.0, 900.0),
    (132.0, 850.0),
    (187.0, 800.0),
    (240.0, 750.0),
    (290.0, 700.0),
    (340.0, 650.0),
    (385.0, 600.0),
    (430.0, 550.0),
    (470.0, 500.0),
    (510.0, 450.0),
    (545.0, 400.0),
    (578.0, 350.0),
    (609.0, 300.0),
    (637.0, 250.0),
    (661.0, 200.0),
    (684.0, 150.0),
]

MIN_RANGE_M = MORTAR_TABLE[0][0]   # 80 м
MAX_RANGE_M = MORTAR_TABLE[-1][0]  # 684 м
METERS_PER_UNIT = 100.0            # 1 единица координат = 100 метров


@dataclass
class BallisticResult:
    distance_m: float
    azimuth_deg: float
    elevation_mil: Optional[float]
    range_status: str  # "OK", "TOO_CLOSE", "TOO_FAR"
    dx_m: float
    dy_m: float


def interpolate_mil(distance_m: float) -> Tuple[Optional[float], str]:
    if distance_m < MIN_RANGE_M:
        return None, "TOO_CLOSE"
    if distance_m > MAX_RANGE_M:
        return None, "TOO_FAR"

    for i in range(len(MORTAR_TABLE) - 1):
        d0, m0 = MORTAR_TABLE[i]
        d1, m1 = MORTAR_TABLE[i + 1]
        if d0 <= distance_m <= d1:
            if d1 == d0:
                return m0, "OK"
            t = (distance_m - d0) / (d1 - d0)
            mil = m0 + t * (m1 - m0)
            return round(mil), "OK"

    return round(MORTAR_TABLE[-1][1]), "OK"


def calculate_ballistics(
    gun_x: float, gun_y: float, target_x: float, target_y: float
) -> BallisticResult:
    dx_m = (target_x - gun_x) * METERS_PER_UNIT
    dy_m = (target_y - gun_y) * METERS_PER_UNIT
    distance_m = math.hypot(dx_m, dy_m)

    if distance_m < 1e-6:
        azimuth_deg = 0.0
    else:
        azimuth_deg = (math.degrees(math.atan2(dx_m, dy_m)) + 360.0) % 360.0

    elevation_mil, status = interpolate_mil(distance_m)

    return BallisticResult(
        distance_m=round(distance_m),
        azimuth_deg=round(azimuth_deg, 1),
        elevation_mil=elevation_mil,
        range_status=status,
        dx_m=dx_m,
        dy_m=dy_m,
    )

__version__ = "1.0.0"


"""
Ates izni kurallari (Sartname 4.2 ve 6.3).

Bu modul sadece "ates serbest mi?" sorusuna cevap verir; motor/tetik
komutunu gondermek main.py'nin isi.
"""

from typing import Optional, Tuple

import config
from vision_detector import Target


def can_engage(target: Optional[Target], stage: int, estop: bool, frame_width: int) -> Tuple[bool, str]:
    if estop:
        return False, "ACIL DURDUR AKTIF"

    if target is None:
        return False, "HEDEF YOK"

    x_frac = target.center[0] / frame_width
    low, high = config.NO_FIRE_ZONE_X_FRACTION
    if not (low <= x_frac <= high):
        return False, "ATISA YASAK BOLGE"

    if stage == 1:
        # Manuel mod: sira/menzil karari operatorde, yazilim sadece engellemiyor.
        return True, "OK"

    if stage == 2:
        # Siniflandirma istenmiyor (Sartname 6.2); her tespit dusman kabul edilir.
        return True, "OK"

    if stage == 3:
        if target.faction == "DOST":
            return False, "DOST HEDEF - ATES YASAK"
        if target.faction == "BILINMIYOR":
            return False, "FACTION BELIRSIZ - ONAY GEREKLI"
        if target.target_type is None or target.range_m is None:
            return False, "SINIFLANDIRMA/MESAFE YOK - ONAY GEREKLI"

        valid_range = config.ENGAGEMENT_RANGES_M.get(target.target_type)
        if valid_range and not (valid_range[0] <= target.range_m <= valid_range[1]):
            return False, f"MENZIL DISI ({target.range_m:.1f}m)"

        return True, "OK"

    return False, "BILINMEYEN ASAMA"

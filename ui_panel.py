"""
Gercek kullanici arayuzu paneli.

Video goruntusunun yanina eklenen, tiklanabilir butonlari ve anlik durumu
gosteren bir panel. Ayri bir pencere/framework acmadan, ayni OpenCV
penceresi icinde calisir (main.py bu paneli video ile yan yana birlestirir).

Sartname Yetenek-1: "kullanicidan komutlarin verildigi arayuz tum
fonksiyonlariyla anlatilacak" -> klavye kisayollarinin yaninda, hakemin
goreceği gercek buton/panel burada.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

PANEL_WIDTH = 260

BG_COLOR = (32, 32, 32)
TEXT_COLOR = (230, 230, 230)
MUTED_TEXT = (150, 150, 150)
BUTTON_COLOR = (70, 70, 70)
ACTIVE_COLOR = (0, 170, 0)
DANGER_COLOR = (0, 0, 220)
WHITE = (255, 255, 255)


@dataclass
class Button:
    label: str
    rect: Tuple[int, int, int, int]  # x1, y1, x2, y2 (panel-local koordinat)
    action: str


class UIPanel:
    """Video karesinin saginda gosterilen buton + durum paneli."""

    def __init__(self, height: int, width: int = PANEL_WIDTH):
        self.width = width
        self.height = height
        self.buttons: List[Button] = []
        self._build_buttons()

    def _build_buttons(self):
        specs = [
            ("ASAMA 1", "stage:1"),
            ("ASAMA 2", "stage:2"),
            ("ASAMA 3", "stage:3"),
            ("MOD DEGISTIR (M)", "toggle_mode"),
            ("KILIDI BIRAK", "release_lock"),
            ("ATES (SPACE)", "fire"),
        ]
        y = 20
        for label, action in specs:
            rect = (15, y, self.width - 15, y + 40)
            self.buttons.append(Button(label, rect, action))
            y += 52

    def handle_click(self, x: int, y: int) -> Optional[str]:
        """Panel-local (x,y) tikla eslesen butonun action adini dondurur."""
        for b in self.buttons:
            x1, y1, x2, y2 = b.rect
            if x1 <= x <= x2 and y1 <= y <= y2:
                return b.action
        return None

    def render(self, state: dict) -> np.ndarray:
        panel = np.full((self.height, self.width, 3), BG_COLOR, dtype=np.uint8)

        for b in self.buttons:
            x1, y1, x2, y2 = b.rect
            is_active = b.action == f"stage:{state['stage']}"
            color = ACTIVE_COLOR if is_active else BUTTON_COLOR
            cv2.rectangle(panel, (x1, y1), (x2, y2), color, -1)
            cv2.rectangle(panel, (x1, y1), (x2, y2), WHITE, 1)
            text_color = (0, 0, 0) if is_active else TEXT_COLOR
            cv2.putText(panel, b.label, (x1 + 8, y1 + 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, text_color, 1)

        y = self.buttons[-1].rect[3] + 35
        cv2.line(panel, (15, y - 15), (self.width - 15, y - 15), (90, 90, 90), 1)

        lines = [
            f"MOD: {state['mode']}",
            f"ASAMA: {state['stage']}",
            f"HEDEF SAYISI: {state['target_count']}",
            f"KILIT: {state['lock_id'] if state['lock_id'] is not None else '-'}",
            f"TAKIM (FACTION): {state['faction']}",
            f"TIP: {state['target_type']}",
            f"MESAFE: {state['range_txt']}",
        ]
        for line in lines:
            cv2.putText(panel, line, (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, TEXT_COLOR, 1)
            y += 24

        if state.get("lost"):
            y += 6
            cv2.putText(panel, "HEDEF KAYIP! KURTARMA BEKLENIYOR",
                        (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)
            y += 24

        y += 10
        cv2.putText(panel, "ATES DURUMU:", (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, MUTED_TEXT, 1)
        y += 24
        fire_color = ACTIVE_COLOR if state["can_fire"] else DANGER_COLOR
        cv2.putText(panel, state["fire_reason"], (15, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, fire_color, 1)

        if state.get("estop"):
            cv2.rectangle(panel, (0, self.height - 44), (self.width, self.height), DANGER_COLOR, -1)
            cv2.putText(panel, "ACIL DURDUR AKTIF", (18, self.height - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, WHITE, 2)

        return panel

"""
Hedef kilitleme / takip hafizasi.

Orijinal targetTracker.py'deki tiklayarak-kilitle + ID-degisince-kurtar
mantigi; artik test edilebilir bir sinif ve otomatik secimde titremeyi
(flicker) azaltan bir histerezis eklenmis hali.
"""

import cv2
import numpy as np

import config
from vision_detector import Target


class TargetLock:
    def __init__(self, max_lost_frames=config.MAX_LOST_FRAMES,
                 max_recovery_distance=config.MAX_RECOVERY_DISTANCE,
                 auto_switch_hysteresis=config.AUTO_SWITCH_HYSTERESIS_PX):
        self.manual_locked_id = None
        self.auto_target_id = None
        self.last_known_center = None
        self.lost_counter = 0
        self.max_lost_frames = max_lost_frames
        self.max_recovery_distance = max_recovery_distance
        self.auto_switch_hysteresis = auto_switch_hysteresis
        self.clicked_point = None

    # cv2.setMouseCallback(WINDOW_NAME, lock.mouse_callback)
    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.clicked_point = (x, y)
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.release()

    def release(self):
        self.manual_locked_id = None
        self.auto_target_id = None
        self.last_known_center = None
        self.lost_counter = 0
        self.clicked_point = None
        print("[BILGI] Kilit serbest birakildi.")

    def update(self, targets: list[Target]) -> Target | None:
        primary = None

        if self.clicked_point is not None:
            cx, cy = self.clicked_point
            for t in targets:
                x1, y1, x2, y2 = t.box
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    self.manual_locked_id = t.id
                    self.last_known_center = t.center
                    self.lost_counter = 0
                    print(f"[KILIT] ID: {t.id} hedefine kilitlendi.")
                    break
            self.clicked_point = None

        if self.manual_locked_id is not None:
            primary = self._resolve_manual_lock(targets)
        else:
            primary = self._auto_select(targets)

        return primary

    def _resolve_manual_lock(self, targets: list[Target]):
        primary = None

        for t in targets:
            if t.id == self.manual_locked_id:
                primary = t
                self.last_known_center = t.center
                self.lost_counter = 0
                break

        # ID anlik degistiyse (ByteTrack ID atlamasi) yakinlik kurtarmasi yap
        if primary is None and self.last_known_center is not None:
            closest, min_drift = None, float("inf")
            for t in targets:
                drift = np.hypot(t.center[0] - self.last_known_center[0],
                                  t.center[1] - self.last_known_center[1])
                if drift < min_drift and drift < self.max_recovery_distance:
                    min_drift, closest = drift, t

            if closest is not None:
                self.manual_locked_id = closest.id
                primary = closest
                self.last_known_center = closest.center
                self.lost_counter = 0

        if primary is None:
            self.lost_counter += 1
            if self.lost_counter > self.max_lost_frames:
                self.release()

        return primary

    def _auto_select(self, targets: list[Target]):
        """Manuel secim yokken merkeze en yakin hedefi secer; kucuk mesafe
        farklarinda ayni hedefte kalarak kutular arasi ziplamayi azaltir."""
        if not targets:
            self.auto_target_id = None
            return None

        candidate = min(targets, key=lambda t: t.dist)
        current = next((t for t in targets if t.id == self.auto_target_id), None)

        if current is None or candidate.dist < current.dist - self.auto_switch_hysteresis:
            self.auto_target_id = candidate.id
            return candidate

        return current

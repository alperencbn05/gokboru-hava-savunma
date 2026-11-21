"""
Tespit + siniflandirma katmani.

YOLO/ByteTrack ile kutu ve ID uretir, ustune iki ozelligi ekler:
  - faction  : "DUSMAN" | "DOST" | "BILINMIYOR"  (hedef maketi rengine gore)
  - range_m  : tahmini mesafe (metre) veya None (kalibre edilmemisse)
"""

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

import config


@dataclass
class Target:
    id: int
    box: Tuple[int, int, int, int]
    center: Tuple[int, int]
    dist: float            # kare merkezine piksel uzakligi (oto-secim icin)
    dx: int
    dy: int
    cls_name: str           # YOLO'nun dondurdugu ham sinif adi
    faction: str
    target_type: Optional[str]
    range_m: Optional[float]


class Detector:
    def __init__(self, model_path: str = config.MODEL_PATH):
        self.model = YOLO(model_path)

    def detect(self, frame, frame_cx: int, frame_cy: int) -> list[Target]:
        results = self.model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
        targets: list[Target] = []

        if not results or results[0].boxes is None or results[0].boxes.id is None:
            return targets

        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.int().cpu().numpy()
        cls_ids = results[0].boxes.cls.int().cpu().numpy()
        names = results[0].names

        for box, track_id, cls_id in zip(boxes, track_ids, cls_ids):
            x1, y1, x2, y2 = box
            bbox = (int(x1), int(y1), int(x2), int(y2))

            # Yukari cikamama sorununu cozen hedefleme noktasi (ustten %30)
            target_cx = int((x1 + x2) / 2)
            target_cy = int(y1 + (y2 - y1) * 0.3)

            target_type = config.CLASS_NAME_MAP.get(int(cls_id))
            faction = classify_faction(frame, bbox)
            range_m = estimate_distance_m(y2 - y1, target_type)

            targets.append(Target(
                id=int(track_id),
                box=bbox,
                center=(target_cx, target_cy),
                dist=float(np.hypot(target_cx - frame_cx, target_cy - frame_cy)),
                dx=target_cx - frame_cx,
                dy=target_cy - frame_cy,
                cls_name=names.get(int(cls_id), str(cls_id)),
                faction=faction,
                target_type=target_type,
                range_m=range_m,
            ))

        return targets


def classify_faction(frame, bbox: Tuple[int, int, int, int]) -> str:
    """Hedef maketinin govde rengine gore DOST/DUSMAN ayrimi.

    Balon (her maketin altinda, her zaman kirmizi) kutunun alt kismindadir ve
    siniflandirmayi bozmamasi icin orneklemeye dahil edilmez.
    """
    x1, y1, x2, y2 = bbox
    h = y2 - y1
    body_bottom = y1 + int(h * config.FACTION_BODY_TOP_RATIO)

    fy1, fy2 = max(y1, 0), max(body_bottom, y1 + 1)
    fx1, fx2 = max(x1, 0), max(x2, x1 + 1)
    crop = frame[fy1:fy2, fx1:fx2]
    if crop.size == 0:
        return "BILINMIYOR"

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    red_mask = (
        cv2.inRange(hsv, np.array(config.RED_HSV_RANGE_1[0]), np.array(config.RED_HSV_RANGE_1[1]))
        | cv2.inRange(hsv, np.array(config.RED_HSV_RANGE_2[0]), np.array(config.RED_HSV_RANGE_2[1]))
    )
    blue_mask = cv2.inRange(hsv, np.array(config.BLUE_HSV_RANGE[0]), np.array(config.BLUE_HSV_RANGE[1]))

    total_px = crop.shape[0] * crop.shape[1]
    red_ratio = cv2.countNonZero(red_mask) / total_px
    blue_ratio = cv2.countNonZero(blue_mask) / total_px

    if max(red_ratio, blue_ratio) < config.FACTION_MIN_COVERAGE:
        return "BILINMIYOR"
    return "DUSMAN" if red_ratio >= blue_ratio else "DOST"


def estimate_distance_m(bbox_height_px: float, target_type: Optional[str]) -> Optional[float]:
    if config.FOCAL_PX is None or bbox_height_px <= 0:
        return None
    real_h = config.REAL_HEIGHT_M.get(target_type or "DEFAULT", config.REAL_HEIGHT_M["DEFAULT"])
    return (real_h * config.FOCAL_PX) / bbox_height_px

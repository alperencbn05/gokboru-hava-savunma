"""
Gokboru Hava Savunma Sistemi - Hedef Takip Ana Dongu

Pencere, video goruntusunun saginda bir kontrol paneli ile acilir
(bkz. ui_panel.py). Panel butonlari ve klavye kisayollari ayni islevleri
yapar; biri hakem gosterimi icin "gercek arayuz", digeri hizli test icin.

Video alani uzerinde:
  Sol tik      : hedefe kilitlen
  Sag tik      : kilidi birak

Panel / klavye:
  ASAMA 1/2/3  veya  1 / 2 / 3   : Asama sec (sartname kurallarini degistirir)
  MOD DEGISTIR veya  M           : MANUEL <-> OTONOM mod
  ATES         veya  SPACE       : tek atimlik ates istegi
  KILIDI BIRAK                   : kilidi birak (sag tik ile ayni)
  Q                               : cikis
"""

import cv2
import numpy as np

import config
from vision_detector import Detector
from target_lock import TargetLock
from serial_link import SerialLink
from engagement import can_engage
from ui_panel import UIPanel
from kamera import kaynak_olustur


def draw_crosshair(frame, cx, cy):
    cv2.line(frame, (cx - 20, cy), (cx + 20, cy), (0, 255, 0), 1)
    cv2.line(frame, (cx, cy - 20), (cx, cy + 20), (0, 255, 0), 1)
    cv2.circle(frame, (cx, cy), config.DEADZONE, (0, 255, 0), 1)


def draw_target(frame, target, is_primary):
    x1, y1, x2, y2 = target.box
    tcx, tcy = target.center
    color = (0, 0, 255) if is_primary else (0, 255, 255)
    thickness = 2 if is_primary else 1

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)
    cv2.circle(frame, (tcx, tcy), 5 if is_primary else 3, color, -1)

    range_txt = f"{target.range_m:.1f}m" if target.range_m is not None else "?"
    type_txt = target.target_type or target.cls_name
    label = f"ID:{target.id} {target.faction} {type_txt} {range_txt}"
    cv2.putText(frame, label, (x1, max(y1 - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)


def _camera_settings():
    """kamera.kaynak_olustur() icin config.py'den ayar sozlugu kurar."""
    return {
        "source": config.CAMERA_SOURCE,       # "orbbec" | "webcam" | "video" | "demo"
        "depth": config.CAMERA_DEPTH,
        "demo_fps": config.CAMERA_DEMO_FPS,
        "video_path": config.CAMERA_VIDEO_PATH,
        "webcam_index": config.CAMERA_INDEX,
    }


def main():
    detector = Detector(config.MODEL_PATH)
    lock = TargetLock()
    link = SerialLink()
    ui = UIPanel(height=config.FRAME_HEIGHT)

    source = kaynak_olustur(_camera_settings())
    source.start()

    cv2.namedWindow(config.WINDOW_NAME)

    state = {"stage": 1, "mode": "MANUEL", "fire_once": False}

    def on_mouse(event, x, y, flags, param):
        if x < config.FRAME_WIDTH:
            lock.mouse_callback(event, x, y, flags, param)
            return

        if event != cv2.EVENT_LBUTTONDOWN:
            return

        action = ui.handle_click(x - config.FRAME_WIDTH, y)
        if action is None:
            return
        if action == "toggle_mode":
            state["mode"] = "OTONOM" if state["mode"] == "MANUEL" else "MANUEL"
        elif action == "release_lock":
            lock.release()
        elif action == "fire":
            state["fire_once"] = True
        elif action.startswith("stage:"):
            state["stage"] = int(action.split(":")[1])

    cv2.setMouseCallback(config.WINDOW_NAME, on_mouse)

    try:
        while True:
            kare = source.read()
            if kare is None:
                print("[HATA] Kameradan goruntu alinamiyor (kaynak: "
                      f"{config.CAMERA_SOURCE}). Baglantiyi/CAMERA_INDEX'i kontrol edin.")
                break

            frame = kare.color_bgr
            depth_mm = kare.depth_mm

            if config.FLIP_HORIZONTAL:
                frame = cv2.flip(frame, 1)  # ayna etkisini duzelt
                if depth_mm is not None:
                    depth_mm = cv2.flip(depth_mm, 1)  # Color ile hizali kalsin

            if frame.shape[1] != config.FRAME_WIDTH or frame.shape[0] != config.FRAME_HEIGHT:
                frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))
                if depth_mm is not None:
                    depth_mm = cv2.resize(depth_mm, (config.FRAME_WIDTH, config.FRAME_HEIGHT),
                                           interpolation=cv2.INTER_NEAREST)

            height, width = frame.shape[:2]
            frame_cx, frame_cy = width // 2, height // 2
            draw_crosshair(frame, frame_cx, frame_cy)

            targets = detector.detect(frame, frame_cx, frame_cy, depth_mm)
            primary = lock.update(targets)
            estop = link.poll_estop()

            can_fire, reason = can_engage(primary, state["stage"], estop, width)

            if state["fire_once"]:
                if can_fire:
                    link.request_fire()
                state["fire_once"] = False  # tek atimlik istek tuketildi

            dx = dy = 0
            if primary is not None:
                dx = 0 if abs(primary.dx) < config.DEADZONE else primary.dx
                dy = 0 if abs(primary.dy) < config.DEADZONE else primary.dy

            if estop:
                link.cancel_pending_fire()
                link.send(0, 0)
            else:
                link.send(dx, dy)

            for t in targets:
                draw_target(frame, t, primary is not None and t.id == primary.id)

            lost = lock.manual_locked_id is not None and primary is None and lock.last_known_center is not None
            if lost:
                cv2.circle(frame, lock.last_known_center, 20, (0, 165, 255), 1)

            panel_state = {
                "stage": state["stage"],
                "mode": state["mode"],
                "target_count": len(targets),
                "lock_id": lock.manual_locked_id,
                "faction": primary.faction if primary else "-",
                "target_type": (primary.target_type or primary.cls_name) if primary else "-",
                "range_txt": f"{primary.range_m:.1f}m" if (primary and primary.range_m is not None) else "KALIBRE EDILMEDI",
                "lost": lost,
                "can_fire": can_fire,
                "fire_reason": reason,
                "estop": estop,
            }
            panel = ui.render(panel_state)
            display = np.hstack([frame, panel])
            cv2.imshow(config.WINDOW_NAME, display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or cv2.getWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
            elif key in (ord('1'), ord('2'), ord('3')):
                state["stage"] = int(chr(key))
            elif key == ord('m'):
                state["mode"] = "OTONOM" if state["mode"] == "MANUEL" else "MANUEL"
            elif key == 32:  # SPACE
                state["fire_once"] = True
    finally:
        link.close()
        source.close()
        cv2.destroyAllWindows()
        cv2.waitKey(1)


if __name__ == "__main__":
    main()

"""
Gokboru Hava Savunma Sistemi - Hedef Takip Ana Dongu

Kontroller:
  Sol tik      : hedefe kilitlen
  Sag tik      : kilidi birak
  1 / 2 / 3    : Asama sec (sartname kurallarini degistirir)
  M            : MANUEL <-> OTONOM mod
  SPACE        : tek atimlik ates istegi (gercek tetik UI/joystick ile degisecek)
  Q            : cikis
"""

import cv2

import config
from vision_detector import Detector
from target_lock import TargetLock
from serial_link import SerialLink
from engagement import can_engage


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

    range_txt = f"{target.range_m:.1f}m" if target.range_m is not None else "KALIBRE EDILMEDI"
    type_txt = target.target_type or target.cls_name
    label = f"ID:{target.id} {target.faction} {type_txt} {range_txt}"
    cv2.putText(frame, label, (x1, max(y1 - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)


def main():
    detector = Detector(config.MODEL_PATH)
    lock = TargetLock()
    link = SerialLink()

    cap = cv2.VideoCapture(config.CAMERA_INDEX, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    cv2.namedWindow(config.WINDOW_NAME)
    cv2.setMouseCallback(config.WINDOW_NAME, lock.mouse_callback)

    stage = 1
    mode = "MANUEL"
    fire_once = False

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("[HATA] Kameradan goruntu alinamiyor. CAMERA_INDEX degerini 1 veya 2 yapmayi deneyin.")
                break

            frame = cv2.flip(frame, 1)  # ayna etkisini duzelt
            height, width = frame.shape[:2]
            frame_cx, frame_cy = width // 2, height // 2
            draw_crosshair(frame, frame_cx, frame_cy)

            targets = detector.detect(frame, frame_cx, frame_cy)
            primary = lock.update(targets)
            estop = link.poll_estop()

            can_fire, reason = can_engage(primary, stage, estop, width)
            fire_cmd = 1 if (fire_once and can_fire) else 0
            fire_once = False  # tek atimlik istek tuketildi

            dx = dy = 0
            if primary is not None:
                dx = 0 if abs(primary.dx) < config.DEADZONE else primary.dx
                dy = 0 if abs(primary.dy) < config.DEADZONE else primary.dy

            if not estop:
                link.send(dx, dy, fire_cmd)
            else:
                link.send(0, 0, 0)

            for t in targets:
                draw_target(frame, t, primary is not None and t.id == primary.id)

            if lock.manual_locked_id is not None and primary is None and lock.last_known_center is not None:
                cv2.putText(frame, f"HEDEF KAYIP! BEKLENIYOR ({lock.lost_counter}/{lock.max_lost_frames})",
                            (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
                cv2.circle(frame, lock.last_known_center, 20, (0, 165, 255), 1)

            lock_txt = f"KILIT: ID {lock.manual_locked_id}" if lock.manual_locked_id else "OTO SECIM MODU"
            cv2.putText(frame, f"Toplam: {len(targets)} | {lock_txt}", (20, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
            cv2.putText(frame, f"ASAMA-{stage} | {mode} | ATES: {reason}", (20, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0) if can_fire else (0, 0, 255), 2)

            if estop:
                cv2.putText(frame, "ACIL DURDUR AKTIF", (20, height - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 3)

            cv2.imshow(config.WINDOW_NAME, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or cv2.getWindowProperty(config.WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
            elif key in (ord('1'), ord('2'), ord('3')):
                stage = int(chr(key))
            elif key == ord('m'):
                mode = "OTONOM" if mode == "MANUEL" else "MANUEL"
            elif key == 32:  # SPACE
                fire_once = True
    finally:
        link.close()
        cap.release()
        cv2.destroyAllWindows()
        cv2.waitKey(1)


if __name__ == "__main__":
    main()

"""
Tek basina kamera testi (model/Arduino YOK).

Jetson'a veya baska bir makineye gectiginizde once sadece kameranin
acilip goruntu verdigini dogrulamak icin kullanin. main.py'nin tamamini
calistirmadan once bu testin gecmesi gerekir.

kamera.py uzerinden main.py ile AYNI kaynagi (config.CAMERA_SOURCE) acar,
boylece burada calisan main.py'de de calisir.

Kullanim:
    python tools/test_camera.py
    (q ile cikis)
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

import config
from kamera import kaynak_olustur


def main():
    settings = {
        "source": config.CAMERA_SOURCE,
        "depth": config.CAMERA_DEPTH,
        "demo_fps": config.CAMERA_DEMO_FPS,
        "video_path": config.CAMERA_VIDEO_PATH,
        "webcam_index": config.CAMERA_INDEX,
    }
    print(f"[BILGI] CAMERA_SOURCE={config.CAMERA_SOURCE}  DEPTH={config.CAMERA_DEPTH}")

    source = kaynak_olustur(settings)
    source.start()

    frame_count = 0
    window_start = time.time()

    try:
        while True:
            kare = source.read()
            if kare is None:
                print("[HATA] Kareden goruntu alinamadi.")
                break

            frame_count += 1
            elapsed = time.time() - window_start
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                h, w = kare.color_bgr.shape[:2]
                depth_txt = "var" if kare.depth_mm is not None else "yok"
                print(f"FPS: {fps:5.1f}  |  Kare boyutu: {w}x{h}  |  Depth: {depth_txt}")
                frame_count = 0
                window_start = time.time()

            cv2.imshow("Kamera Testi (q = cikis)", kare.color_bgr)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        source.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

"""
Tek basina kamera testi (model/Arduino YOK).

Jetson'a veya baska bir makineye gectiginizde once sadece kameranin
acilip goruntu verdigini dogrulamak icin kullanin. main.py'nin tamamini
calistirmadan once bu testin gecmesi gerekir.

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


def main():
    print(f"[BILGI] CAMERA_INDEX={config.CAMERA_INDEX}  BACKEND={config.CAMERA_BACKEND}")
    cap = cv2.VideoCapture(config.CAMERA_INDEX, config.CAMERA_BACKEND)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

    if not cap.isOpened():
        print("[HATA] Kamera acilamadi. config.CAMERA_INDEX degerini "
              "(0, 1, 2 ...) degistirmeyi deneyin. Linux'ta 'v4l2-ctl "
              "--list-devices' ile hangi index'in Orbbec oldugunu gorebilirsiniz.")
        return

    frame_count = 0
    window_start = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[HATA] Kareden goruntu okunamadi.")
                break

            frame_count += 1
            elapsed = time.time() - window_start
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                print(f"FPS: {fps:5.1f}  |  Kare boyutu: {frame.shape[1]}x{frame.shape[0]}")
                frame_count = 0
                window_start = time.time()

            cv2.imshow("Kamera Testi (q = cikis)", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

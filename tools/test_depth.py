"""
Orbbec derinlik kamerasi tek basina testi (main.py'ye BAGLI DEGIL).

kamera.py'nin OrbbecKaynak sinifini kullanir (bu, takim arkadasinin
goruntu isleme lab projesinden alinan, birim testleri gecen, demo modunda
calistigi dogrulanmis kod - bkz. lab_goruntu_isleme/). Gercek Orbbec
donanimiyla bu script HENUZ test edilmedi; once bir cismi bilinen bir
mesafeye (orn. tam 1m, 2m, 3m) koyup ekranda yazdirilan degerle
karsilastirin.

Kullanim:
    python tools/test_depth.py
    (q ile cikis)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np

from kamera import OrbbecKaynak


def point_distance_m(depth_mm, x, y, window=3):
    h, w = depth_mm.shape[:2]
    x0, x1 = max(0, x - window), min(w, x + window + 1)
    y0, y1 = max(0, y - window), min(h, y + window + 1)
    patch = depth_mm[y0:y1, x0:x1]
    valid = patch[patch > 0]
    if valid.size == 0:
        return None
    return float(np.median(valid)) / 1000.0


def main():
    source = OrbbecKaynak(depth=True)

    try:
        source.start()
    except RuntimeError as e:
        print(f"[HATA] {e}")
        return

    print("[BILGI] Orbbec pipeline baslatildi. Goruntu merkezindeki mesafe "
          "yazdirilacak. Bir cismi bilinen bir mesafeye koyup degeri "
          "dogrulayin. 'q' ile cikis.")
    print("[UYARI] Kamera fiziksel olarak takili/acik degilse SDK temiz bir "
          "Python hatasi vermeden sureci sert bicimde sonlandirabilir.")

    try:
        while True:
            kare = source.read()
            if kare is None:
                print("[UYARI] Kare alinamadi.")
                continue

            color = kare.color_bgr
            h, w = color.shape[:2]
            cx, cy = w // 2, h // 2

            dist = point_distance_m(kare.depth_mm, cx, cy) if kare.depth_mm is not None else None
            dist_txt = f"{dist:.2f} m" if dist is not None else "?"

            cv2.circle(color, (cx, cy), 6, (0, 0, 255), -1)
            cv2.putText(color, f"Merkez mesafe: {dist_txt}", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.imshow("Orbbec Derinlik Testi (q = cikis)", color)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        source.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

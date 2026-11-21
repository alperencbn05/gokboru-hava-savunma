"""
Orbbec derinlik kamerasi tek basina testi (main.py'ye BAGLI DEGIL).

depth_source.py'nin gercek donanimda calisip calismadigini ve okunan
mesafelerin gercekci olup olmadigini gormek icindir. Bir cismi kameradan
bilinen bir mesafeye (orn. tam 1m, 2m, 3m) koyup ekranda yazdirilan
degerle karsilastirin. Degerler tutmuyorsa depth_source.py'deki renk
formati varsayimini ve pyorbbecsdk kurulumunu kontrol edin.

Kullanim:
    python tools/test_depth.py
    (q ile cikis)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2

from depth_source import OrbbecDepthSource


def main():
    try:
        source = OrbbecDepthSource()
    except RuntimeError as e:
        print(f"[HATA] {e}")
        return

    print("[BILGI] Orbbec pipeline baslatildi. Goruntu merkezindeki mesafe "
          "yazdirilacak. Bir cismi bilinen bir mesafeye koyup degeri "
          "dogrulayin. 'q' ile cikis.")

    try:
        while True:
            color, depth_mm = source.read()
            if color is None:
                print("[UYARI] Kare alinamadi.")
                continue

            h, w = color.shape[:2]
            cx, cy = w // 2, h // 2
            dist = source.point_distance_m(depth_mm, cx, cy)
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

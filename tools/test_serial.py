"""
Tek basina Arduino/seri port testi (kamera/model YOK).

Jetson'a (ya da baska bir makineye) gectiginizde Arduino baglantisini,
ESTOP okumasini ve bir hareket komutunu kamera/modelden bagimsiz dogrulamak
icin kullanin. Arduino'da gokboru_turret.ino yuklu olmali.

Beklenen: pan servosu ~5 saniye yavasca sola-saga salinir, sonra bir
atimlik "ates" komutu gonderilir (PIN_FIRE pini kisa sure HIGH olur).

Kullanim:
    python tools/test_serial.py
"""

import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from serial_link import SerialLink


def main():
    print(f"[BILGI] SERIAL_PORT={config.SERIAL_PORT}  BAUD_RATE={config.BAUD_RATE}")
    link = SerialLink()

    if not link.connected:
        print("[HATA] Seri baglanti kurulamadi. config.SERIAL_PORT degerini "
              "kontrol edin. Linux/Jetson'da Arduino'yu takip 'ls /dev/tty*' "
              "ile hangi portun eklendigine bakin (genelde /dev/ttyACM0).")
        return

    print("[BILGI] Baglanti kuruldu. 5 saniye pan eksenini salinim yaptiriyorum...")
    start = time.time()
    try:
        while time.time() - start < 5.0:
            t = time.time() - start
            dx = int(40 * math.sin(t * 2))
            link.send(dx, 0)
            estop = link.poll_estop()
            print(f"dx={dx:4d}  ESTOP={estop}")
            time.sleep(0.05)

        print("[BILGI] Tek atimlik ates istegi gonderiliyor...")
        link.request_fire()
        link.send(0, 0)
        time.sleep(0.5)
        print("[BILGI] Test tamamlandi.")
    finally:
        link.close()


if __name__ == "__main__":
    main()

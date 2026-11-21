"""
Arduino ile seri haberlesme.

Protokol (bkz. README.md "Seri Protokol" bolumu):
  PC -> Arduino : "X{dx}Y{dy}F{fire}\n"   dx,dy: piksel hatasi, fire: 0/1
  Arduino -> PC : "ESTOP:0\n" / "ESTOP:1\n"  (acil durdur butonu durumu)

Kullanim: hareket icin her dongude send(dx, dy) cagrilir (throttle'li).
Ates icin once request_fire() ile istek kuyruga alinir, bir sonraki
send() cagrisinda F1 olarak kesin iletilir (throttle penceresine
denk gelse bile kaybolmaz).
"""

import time

import serial

import config


class SerialLink:
    def __init__(self, port: str = config.SERIAL_PORT, baud: int = config.BAUD_RATE,
                 interval: float = config.SERIAL_INTERVAL):
        self.interval = interval
        self._last_send = 0.0
        self._estop_state = False
        self._pending_fire = False
        self.port = port

        try:
            self.ser = serial.Serial(port, baud, timeout=0.01)
            time.sleep(2)
            print(f"[BAGLANTI] Arduino {port} baglantisi basarili.")
        except Exception as e:
            self.ser = None
            print(f"[UYARI] Arduino baglanamadi ({e}). SIMULASYON modu aktif.")

    @property
    def connected(self) -> bool:
        return self.ser is not None

    def request_fire(self) -> None:
        """Ates istegini kuyruga alir.

        Onemli: eskiden fire bayragi dogrudan send()'e parametre olarak
        geciyordu ve send() interval dolmadiysa komutu sessizce atlayip
        ates istegini kaybediyordu (SPACE/ATES tam throttle penceresine
        denk gelirse hic tetiklenmiyordu). Simdi istek burada saklanir ve
        bir sonraki send() cagrisinda -throttle'i gerekirse delerek- kesin
        iletilir.
        """
        self._pending_fire = True

    def cancel_pending_fire(self) -> None:
        self._pending_fire = False

    def send(self, dx: int, dy: int) -> None:
        if self.ser is None:
            return

        now = time.time()
        due = (now - self._last_send) >= self.interval
        if not due and not self._pending_fire:
            return  # henuz zamani gelmedi ve bekleyen ates istegi yok

        fire = 1 if self._pending_fire else 0
        command = f"X{dx}Y{dy}F{fire}\n"
        try:
            self.ser.write(command.encode("utf-8"))
        except Exception as e:
            print(f"[HATA] Seri yazma basarisiz: {e}")
        self._last_send = now
        self._pending_fire = False

    def poll_estop(self) -> bool:
        """Arduino'dan gelen ESTOP satirlarini okur ve son bilinen durumu dondurur.

        NOT: Gercek guvenlik kesintisi donanimda (buton gucü dogrudan kesmeli)
        olmak zorunda (Sartname 4.2). Bu fonksiyon yalnizca yazilimin da ayni
        duruma uyup hareket/ates komutlarini kesmesini saglayan ek bir katmandir.
        """
        if self.ser is None:
            return self._estop_state

        try:
            while self.ser.in_waiting:
                line = self.ser.readline().decode(errors="ignore").strip()
                if line == "ESTOP:1":
                    self._estop_state = True
                elif line == "ESTOP:0":
                    self._estop_state = False
        except Exception as e:
            print(f"[HATA] Seri okuma basarisiz: {e}")

        return self._estop_state

    def close(self) -> None:
        if self.ser is not None:
            self.ser.close()

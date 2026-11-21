"""Goruntu kaynaklari: Orbbec SDK v2, video/webcam ve guvenli demo.

Not: Bu modulle hedef bulma, takip veya fiziksel kontrol yapilmaz.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import sleep
from typing import Optional

import cv2
import numpy as np


@dataclass
class Kare:
    color_bgr: np.ndarray
    depth_mm: Optional[np.ndarray]
    zaman: str
    color_sdk_zaman_ham: Optional[int] = None
    depth_sdk_zaman_ham: Optional[int] = None
    depth_olcek: Optional[float] = None


def simdi():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class DemoKaynak:
    """Gercek kamera olmadan kalite/CSV/kayit sistemini sinamak icin."""

    def __init__(self, depth=False, fps=15):
        self.depth = depth
        self.fps = fps
        self.sayi = 0

    def start(self):
        print("[KAYNAK] Demo goruntuleri aktif (gercek kamera verisi degil).")

    def read(self):
        sleep(1.0 / self.fps)
        self.sayi += 1
        h, w = 360, 640
        x = np.tile(np.linspace(20, 230, w, dtype=np.uint8), (h, 1))
        y = np.tile(np.linspace(30, 200, h, dtype=np.uint8)[:, None], (1, w))
        color = np.stack((x, y, np.full((h, w), 100, dtype=np.uint8)), axis=2)
        cv2.rectangle(color, (90, 70), (290, 230), (235, 210, 80), -1)
        cv2.putText(color, "GORUNTU TESTI", (320, 180), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, (255, 255, 255), 2)
        depth_mm = None
        if self.depth:
            depth_mm = np.tile(np.linspace(600, 3000, w, dtype=np.uint16), (h, 1))
            depth_mm[:, :20] = 0  # ornek gecersiz veri
        return Kare(color, depth_mm, simdi())

    def close(self):
        pass


class VideoKaynak:
    """Bilgisayar kamerasini veya kayitli videoyu ac."""

    def __init__(self, video=None, webcam_index=0):
        self.video = video
        self.webcam_index = webcam_index
        self.cap = None

    def start(self):
        yol = str(Path(self.video).expanduser()) if self.video else self.webcam_index
        self.cap = cv2.VideoCapture(yol)
        if not self.cap.isOpened():
            raise RuntimeError(f"Video/kamera acilamadi: {yol}")
        print(f"[KAYNAK] VideoCapture acildi: {yol}")

    def read(self):
        ok, color = self.cap.read()
        if not ok:
            return None  # Dosya sonu veya kare alinamadi.
        return Kare(color, None, simdi())

    def close(self):
        if self.cap is not None:
            self.cap.release()


def orbbec_color_bgr(frame, OBFormat):
    """SDK Color verisini OpenCV BGR bicimine donustur."""
    w, h = frame.get_width(), frame.get_height()
    fmt = frame.get_format()
    data = np.frombuffer(frame.get_data(), dtype=np.uint8)
    if fmt == OBFormat.MJPG:
        color = cv2.imdecode(data, cv2.IMREAD_COLOR)
    elif fmt == OBFormat.RGB:
        color = cv2.cvtColor(data.reshape(h, w, 3), cv2.COLOR_RGB2BGR)
    elif fmt == OBFormat.BGR:
        color = data.reshape(h, w, 3).copy()
    elif fmt == OBFormat.YUYV:
        color = cv2.cvtColor(data.reshape(h, w, 2), cv2.COLOR_YUV2BGR_YUYV)
    elif fmt == OBFormat.UYVY:
        color = cv2.cvtColor(data.reshape(h, w, 2), cv2.COLOR_YUV2BGR_UYVY)
    elif fmt == OBFormat.NV12:
        color = cv2.cvtColor(data.reshape(h * 3 // 2, w), cv2.COLOR_YUV2BGR_NV12)
    elif fmt == OBFormat.NV21:
        color = cv2.cvtColor(data.reshape(h * 3 // 2, w), cv2.COLOR_YUV2BGR_NV21)
    elif fmt == OBFormat.I420:
        color = cv2.cvtColor(data.reshape(h * 3 // 2, w), cv2.COLOR_YUV2BGR_I420)
    else:
        raise ValueError(f"SDK Color formatini bu ornek desteklemiyor: {fmt}")
    if color is None or color.size == 0:
        raise ValueError("Color kare verisi bos veya donusturulemedi")
    return color


def orbbec_depth_mm(frame, OBFormat):
    """Ham 16-bit derinlik + SDK olcegi => 16-bit milimetre goruntusu."""
    kabul = [OBFormat.Y16]
    if hasattr(OBFormat, "Z16"):
        kabul.append(OBFormat.Z16)
    if frame.get_format() not in kabul:
        raise ValueError(f"Depth formatina uygun donusum tanimli degil: {frame.get_format()}")
    h, w = frame.get_height(), frame.get_width()
    ham = np.frombuffer(frame.get_data(), dtype=np.uint16).reshape(h, w)
    olcek = float(frame.get_depth_scale())
    if olcek <= 0:
        raise ValueError(f"Gecersiz Depth olcegi: {olcek}")
    mm_f32 = ham.astype(np.float32) * olcek
    # 16-bit PNG sayisal hassasiyeti 1 mm: daha hassas ham veri saklanmaz.
    mm = np.rint(np.clip(mm_f32, 0, 65535)).astype(np.uint16)
    return mm, olcek


def ham_sdk_zaman(frame):
    """SDK zaman damgasini birimi hakkinda varsayim yapmadan al."""
    try:
        return int(frame.get_timestamp())
    except (AttributeError, ValueError, TypeError):
        return None


class OrbbecKaynak:
    """Gercek Orbbec Gemini 335L icin SDK v2 veri kaynagi."""

    def __init__(self, depth=False):
        self.depth = depth
        self.pipeline = None
        self.basladi = False
        self.OBFormat = None
        self.eksik_depth_uyarisi = False

    def start(self):
        try:
            from pyorbbecsdk import Config, OBFormat, OBSensorType, Pipeline
        except ImportError as exc:
            raise RuntimeError(
                "'pyorbbecsdk' bulunamadi. Jetson'da kodu calistiran Python "
                "ortaminda 'python3 -c \"import pyorbbecsdk\"' kontrol edin."
            ) from exc
        self.OBFormat = OBFormat
        self.pipeline = Pipeline()
        config = Config()
        color_profiller = self.pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
        color_profil = color_profiller.get_default_video_stream_profile()
        config.enable_stream(color_profil)
        if self.depth:
            depth_profiller = self.pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
            depth_profil = depth_profiller.get_default_video_stream_profile()
            config.enable_stream(depth_profil)
        self.pipeline.start(config)
        self.basladi = True
        print("[KAYNAK] Orbbec SDK v2 acildi. Depth:", "acik" if self.depth else "kapali")
        print("[BILGI] Color ve Depth hizalanmiyor; iki goruntuye ayni piksel koordinati atfetmeyin.")

    def read(self):
        kareler = self.pipeline.wait_for_frames(1000)
        if kareler is None:
            return None
        cf = kareler.get_color_frame()
        if cf is None:
            return None
        color = orbbec_color_bgr(cf, self.OBFormat)
        depth_mm = None
        olcek = None
        depth_ts = None
        if self.depth:
            df = kareler.get_depth_frame()
            if df is not None:
                try:
                    depth_mm, olcek = orbbec_depth_mm(df, self.OBFormat)
                    depth_ts = ham_sdk_zaman(df)
                except (ValueError, AttributeError) as exc:
                    if not self.eksik_depth_uyarisi:
                        print("[UYARI] Depth donusumu yapilamadi:", exc)
                        self.eksik_depth_uyarisi = True
            elif not self.eksik_depth_uyarisi:
                print("[UYARI] Depth acik fakat bu karede Depth gelmedi.")
                self.eksik_depth_uyarisi = True
        return Kare(color, depth_mm, simdi(), ham_sdk_zaman(cf), depth_ts, olcek)

    def close(self):
        if self.basladi and self.pipeline is not None:
            self.pipeline.stop()
            self.basladi = False


def kaynak_olustur(ayarlar):
    secim = ayarlar["source"]
    if secim == "orbbec":
        return OrbbecKaynak(depth=ayarlar["depth"])
    if secim == "demo":
        return DemoKaynak(depth=ayarlar["depth"], fps=ayarlar["demo_fps"])
    if secim == "video":
        if not ayarlar["video_path"]:
            raise ValueError("source=video icin video_path gerekli")
        return VideoKaynak(video=ayarlar["video_path"])
    if secim == "webcam":
        return VideoKaynak(webcam_index=ayarlar["webcam_index"])
    raise ValueError(f"Bilinmeyen kaynak: {secim}")

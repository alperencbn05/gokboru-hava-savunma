"""
Orbbec Gemini 335L (pyorbbecsdk) derinlik kaynagi - OPSIYONEL modul.

ONEMLI DURUM NOTU: Bu modul resmi pyorbbecsdk dokumantasyonundaki
(orbbec.github.io/pyorbbecsdk) ornek kod parcaciklarindan yazildi.
Gercek kamera/SDK ile HENUZ TEST EDILMEDI - bu gelistirme ortaminda ne
Orbbec donanimi ne de pyorbbecsdk kurulu. main.py'ye baglamadan once
tools/test_depth.py ile bir cismi bilinen mesafelere (1m/2m/3m) koyup
okunan degerin dogru oldugunu MUTLAKA dogrulayin.

Ozellikle dogrulanmamis/riskli noktalar:
  - Renk karesinin RGB oldugu varsayildi; kameraniz MJPG/YUYV
    donduruyorsa _color_frame_to_bgr() yanlis cikar, duzeltilmesi gerekir.
  - Renk ve derinlik sensorleri kamerada farkli konumda oldugu icin
    piksel piksel TAM hizali degildir (kucuk bir kayma olabilir).
    pyorbbecsdk'nin AlignFilter'i ile duzeltilebilir ama bu API'yi
    dokumantasyondan dogrulayamadigim icin buraya eklemedim.

Varsayilan olarak devre disi: vision_detector.py hala config.FOCAL_PX
pinhole tahminini kullaniyor, bu modul onu DEGISTIRMEZ. Saha testinde
dogrulanirsa vision_detector.py'ye baglanabilir.

Kurulum: Orbbec'in resmi pyorbbecsdk GitHub sayfasindaki platform
talimatlarini izleyin (genel pip paketi her platformda calismayabilir,
ozellikle Jetson/aarch64'te kaynaktan derleme gerekebilir).

GERCEK BULGU (bu kod bu makinede denendi): pyorbbecsdk kurulu olsa bile,
kamera FIZIKSEL OLARAK TAKILI/ACIK degilken Pipeline() / stream profili
alma adimlari TEMIZ bir Python hatasi (ImportError/RuntimeError) VERMEDEN
sureci sert bicimde sonlandirabiliyor (try/except ile yakalanamiyor).
Yani bu modulu/test_depth.py'yi calistirirken "hicbir hata mesaji
gormeden program aninda kapaniyor" olursa, once kameranin fiziksel
olarak takili ve acik oldugunu kontrol edin - bu muhtemelen bir kod
hatasi degil, SDK'nin cihaz bulunamadiginda verdigi tepki.
"""

from typing import Optional, Tuple

import numpy as np

try:
    from pyorbbecsdk import Config, OBSensorType, OBFormat, Pipeline
    _ORBBEC_AVAILABLE = True
except ImportError:
    _ORBBEC_AVAILABLE = False


class OrbbecDepthSource:
    """Orbbec kamerasindan renk (BGR) + derinlik (mm) kare cifti okur."""

    def __init__(self, width: int = 640, height: int = 480, fps: int = 30):
        if not _ORBBEC_AVAILABLE:
            raise RuntimeError(
                "pyorbbecsdk kurulu degil. Orbbec'in resmi GitHub sayfasindaki "
                "(orbbec/pyorbbecsdk) platforma uygun kurulum talimatlarini izleyin."
            )

        self.pipeline = Pipeline()
        cfg = Config()

        color_profiles = self.pipeline.get_stream_profile_list(OBSensorType.COLOR_SENSOR)
        color_profile = color_profiles.get_video_stream_profile(width, height, OBFormat.RGB, fps)
        cfg.enable_stream(color_profile)

        depth_profiles = self.pipeline.get_stream_profile_list(OBSensorType.DEPTH_SENSOR)
        depth_profile = depth_profiles.get_default_video_stream_profile()
        cfg.enable_stream(depth_profile)

        self.pipeline.start(cfg)

    def read(self, timeout_ms: int = 1000) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """(renk_bgr, derinlik_mm) dondurur; alinamazsa (None, None)."""
        frames = self.pipeline.wait_for_frames(timeout_ms)
        if frames is None:
            return None, None

        color_frame = frames.get_color_frame()
        depth_frame = frames.get_depth_frame()
        if color_frame is None or depth_frame is None:
            return None, None

        return self._color_frame_to_bgr(color_frame), self._depth_frame_to_mm(depth_frame)

    @staticmethod
    def _color_frame_to_bgr(frame) -> np.ndarray:
        import cv2  # yerel import: bu modul cv2'siz de kullanilabilsin
        width, height = frame.get_width(), frame.get_height()
        data = np.frombuffer(frame.get_data(), dtype=np.uint8)
        rgb = data.reshape((height, width, 3))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    @staticmethod
    def _depth_frame_to_mm(frame) -> np.ndarray:
        width, height = frame.get_width(), frame.get_height()
        data = np.frombuffer(frame.get_data(), dtype=np.uint16)
        depth_raw = data.reshape((height, width))
        return depth_raw.astype(np.float32) * frame.get_depth_scale()

    @staticmethod
    def point_distance_m(depth_mm: np.ndarray, x: int, y: int, window: int = 3) -> Optional[float]:
        """(x,y) civarindaki kucuk pencerenin medyan derinligini metreye
        cevirir (tek piksel gurultuye/derinlik deliklerine karsi hassas
        olabilir, bu yuzden kucuk bir pencerenin medyani alinir)."""
        h, w = depth_mm.shape
        x0, x1 = max(0, x - window), min(w, x + window + 1)
        y0, y1 = max(0, y - window), min(h, y + window + 1)
        patch = depth_mm[y0:y1, x0:x1]
        valid = patch[patch > 0]
        if valid.size == 0:
            return None
        return float(np.median(valid)) / 1000.0

    def close(self) -> None:
        self.pipeline.stop()

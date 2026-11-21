"""Kamera gerektirmeyen birim testleri. python3 -m unittest discover -s testler -v"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from goruntu_isleme import derinlik_analizi, derinlik_onizleme, renk_analizi
from kamera import DemoKaynak, orbbec_color_bgr, orbbec_depth_mm
from kayit import KayitYoneticisi


class SahteSDKBicimi:
    MJPG = 1
    RGB = 2
    BGR = 3
    YUYV = 4
    UYVY = 5
    NV12 = 6
    NV21 = 7
    I420 = 8
    Y16 = 9
    Z16 = 10


class SahteKare:
    def __init__(self, data, fmt, w, h, scale=1):
        self.data, self.fmt, self.w, self.h, self.scale = data, fmt, w, h, scale

    def get_data(self):
        return self.data.tobytes()

    def get_format(self):
        return self.fmt

    def get_width(self):
        return self.w

    def get_height(self):
        return self.h

    def get_depth_scale(self):
        return self.scale


class GoruntuTestleri(unittest.TestCase):
    def test_renk_analizi(self):
        color = np.zeros((100, 120, 3), np.uint8)
        color[:] = (20, 60, 120)
        for filtre in ("none", "median", "gaussian", "clahe"):
            gri, kenarlar, kalite, hist = renk_analizi(color, filtre)
            self.assertEqual(gri.shape, (100, 120))
            self.assertEqual(kenarlar.shape, (100, 120))
            self.assertEqual(int(hist.sum()), 12000)
            self.assertGreater(kalite["parlaklik"], 0)
        self.assertTrue((color[:, :, 0] == 20).all())  # orijinal korunur

    def test_depth_bos_ve_gecerli(self):
        d = np.array([[0, 1000], [2000, 4000]], dtype=np.uint16)
        kalite = derinlik_analizi(d)
        self.assertAlmostEqual(kalite["depth_gecerli_yuzde"], 75)
        self.assertAlmostEqual(kalite["depth_ortalama_mm"], 7000 / 3)
        self.assertEqual(derinlik_onizleme(d).shape, (2, 2, 3))
        self.assertEqual(derinlik_analizi(np.zeros((2, 2), np.uint16))["depth_gecerli_yuzde"], 0)

    def test_sdk_color_rgb_to_bgr(self):
        rgb = np.zeros((2, 3, 3), dtype=np.uint8)
        rgb[0, 0] = (255, 40, 15)
        f = SahteKare(rgb, SahteSDKBicimi.RGB, 3, 2)
        out = orbbec_color_bgr(f, SahteSDKBicimi)
        self.assertEqual(tuple(out[0, 0]), (15, 40, 255))

    def test_sdk_depth_scale(self):
        raw = np.array([[0, 500], [1000, 60000]], dtype=np.uint16)
        frame = SahteKare(raw, SahteSDKBicimi.Y16, 2, 2, scale=0.5)
        mm, scale = orbbec_depth_mm(frame, SahteSDKBicimi)
        self.assertEqual(mm.dtype, np.uint16)
        self.assertEqual(mm[1, 0], 500)
        self.assertEqual(scale, 0.5)

    def test_demo_dosya_kaydi(self):
        demo = DemoKaynak(depth=True, fps=1000)
        demo.start()
        kare = demo.read()
        islenmis, kenarlar, kalite, hist = renk_analizi(kare.color_bgr)
        with tempfile.TemporaryDirectory() as tmp:
            kayit = KayitYoneticisi(tmp)
            kayit.fotograf_kaydet(kare, islenmis, kenarlar, hist, 1)
            yol = next(Path(kayit.fotograflar).glob("*_depth_mm.png"))
            okunan = cv2.imread(str(yol), cv2.IMREAD_UNCHANGED)
            self.assertIsNotNone(okunan)
            self.assertEqual(okunan.dtype, np.uint16)
            self.assertEqual(okunan[0, 40], kare.depth_mm[0, 40])
            kayit.close()
        demo.close()


if __name__ == "__main__":
    unittest.main()

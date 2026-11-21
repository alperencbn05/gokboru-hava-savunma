"""Guvenli goruntu kalite analizi ve temel OpenCV islemleri."""

import cv2
import numpy as np


def renk_analizi(color_bgr, filtre="gaussian"):
    """Orijinali degistirme; islenmis gri goruntu + kenar + kalite degerleri don."""
    if color_bgr is None or color_bgr.ndim != 3 or color_bgr.shape[2] != 3:
        raise ValueError("BGR renkli goruntu bekleniyor")
    if color_bgr.dtype != np.uint8:
        raise ValueError("Renkli goruntu uint8 olmali")

    gri = cv2.cvtColor(color_bgr, cv2.COLOR_BGR2GRAY)
    if filtre == "gaussian":
        islenmis = cv2.GaussianBlur(gri, (5, 5), 0)
    elif filtre == "median":
        islenmis = cv2.medianBlur(gri, 5)
    elif filtre == "clahe":
        # Yerel kontrast iyilestirme - her goruntude daha iyi sonuc vermez.
        islenmis = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gri)
    elif filtre == "none":
        islenmis = gri.copy()
    else:
        raise ValueError("Filtre none, gaussian, median veya clahe olmali")

    # Kenar goruntusu yalnizca kalite laboratuvari icin olusturulur.
    kenarlar = cv2.Canny(gri, 70, 140)
    hsv = cv2.cvtColor(color_bgr, cv2.COLOR_BGR2HSV)
    histogram = cv2.calcHist([gri], [0], None, [256], [0, 256]).flatten()

    kalite = {
        "parlaklik": float(gri.mean()),
        "kontrast_std": float(gri.std()),
        "netlik_laplacian": float(cv2.Laplacian(gri, cv2.CV_64F).var()),
        "karanlik_oran_yuzde": float((gri < 30).mean() * 100),
        "aydinlik_oran_yuzde": float((gri > 225).mean() * 100),
        "doygunluk_ortalama": float(hsv[:, :, 1].mean()),
    }
    return islenmis, kenarlar, kalite, histogram


def derinlik_analizi(depth_mm):
    """0: olcum bulunamadi; diger degerler icin temel istatistikler."""
    if depth_mm is None:
        return {"depth_gecerli_yuzde": None, "depth_ortalama_mm": None,
                "depth_min_mm": None, "depth_max_mm": None}
    if depth_mm.ndim != 2 or depth_mm.dtype != np.uint16:
        raise ValueError("Depth goruntusu tek kanalli uint16 olmali")
    gecerli = depth_mm > 0
    if not np.any(gecerli):
        return {"depth_gecerli_yuzde": 0.0, "depth_ortalama_mm": None,
                "depth_min_mm": None, "depth_max_mm": None}
    degerler = depth_mm[gecerli]
    return {
        "depth_gecerli_yuzde": float(gecerli.mean() * 100),
        "depth_ortalama_mm": float(degerler.mean()),
        "depth_min_mm": int(degerler.min()),
        "depth_max_mm": int(degerler.max()),
    }


def derinlik_onizleme(depth_mm, maks_mm=5000):
    """Sadece gorsellestirme: renklerin gercek mesafe bilgisi yerine gecmedigini unutma."""
    gosterilen = np.clip(depth_mm.astype(np.float32), 0, maks_mm)
    gri = (gosterilen / float(maks_mm) * 255).astype(np.uint8)
    renkli = cv2.applyColorMap(gri, cv2.COLORMAP_JET)
    renkli[depth_mm == 0] = 0
    return renkli


def ekrana_sigdir(goruntu, maks_genislik=960):
    if goruntu.shape[1] <= maks_genislik:
        return goruntu
    oran = maks_genislik / goruntu.shape[1]
    return cv2.resize(goruntu, None, fx=oran, fy=oran)

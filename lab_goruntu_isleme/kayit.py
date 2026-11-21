"""Dosyaya kayit, performans CSV'si ve oturum raporu."""

import csv
import json
from datetime import datetime
from pathlib import Path

import cv2

from goruntu_isleme import derinlik_onizleme


CSV_ALANLARI = [
    "zaman", "kare", "kaynak", "genislik", "yukseklik",
    "fps_dongu_ortalama", "okuma_ms", "isleme_ms",
    "parlaklik", "kontrast_std", "netlik_laplacian",
    "karanlik_oran_yuzde", "aydinlik_oran_yuzde", "doygunluk_ortalama",
    "depth_gecerli_yuzde", "depth_ortalama_mm", "depth_min_mm", "depth_max_mm",
    "color_sdk_zaman_ham", "depth_sdk_zaman_ham",
]


def png_yaz(yol, goruntu):
    if not cv2.imwrite(str(yol), goruntu):
        raise IOError(f"PNG kaydedilemedi: {yol}")


class KayitYoneticisi:
    def __init__(self, cikti_kok, video_kaydet=False, video_fps=15, preview_depth_mm=5000):
        kok = Path(cikti_kok).expanduser().resolve()
        kok.mkdir(parents=True, exist_ok=True)
        # Birden fazla calistirma ayni klasore yazmasin.
        damga = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.oturum = kok / f"oturum_{damga}"
        self.oturum.mkdir(exist_ok=False)
        self.fotograflar = self.oturum / "fotograflar"
        self.fotograflar.mkdir()
        self.csv_dosya = (self.oturum / "metrikler.csv").open("w", newline="", encoding="utf-8")
        self.csv_yazici = csv.DictWriter(self.csv_dosya, fieldnames=CSV_ALANLARI)
        self.csv_yazici.writeheader()
        self.log_dosya = (self.oturum / "calisma.log").open("w", encoding="utf-8")
        self.video_kaydet = video_kaydet
        self.video_fps = video_fps
        self.preview_depth_mm = preview_depth_mm
        self.video_writer = None
        self.video_boyut = None
        self.snap_sayi = 0
        self.metrik_sayi = 0
        self.toplam = {"parlaklik": 0.0, "fps_dongu_ortalama": 0.0,
                       "isleme_ms": 0.0, "depth_gecerli_yuzde": 0.0}
        self.depth_sayisi = 0

    def bilgi(self, mesaj):
        print(mesaj)
        self.log_dosya.write(f"{datetime.now().astimezone().isoformat()} {mesaj}\n")
        self.log_dosya.flush()

    def metrik_yaz(self, metrik):
        self.csv_yazici.writerow({alan: metrik.get(alan) for alan in CSV_ALANLARI})
        self.metrik_sayi += 1
        for ad in ("parlaklik", "fps_dongu_ortalama", "isleme_ms"):
            self.toplam[ad] += float(metrik[ad])
        if metrik.get("depth_gecerli_yuzde") is not None:
            self.toplam["depth_gecerli_yuzde"] += float(metrik["depth_gecerli_yuzde"])
            self.depth_sayisi += 1
        if self.metrik_sayi % 30 == 0:
            self.csv_dosya.flush()

    def kare_videoya(self, color_bgr):
        if not self.video_kaydet:
            return
        h, w = color_bgr.shape[:2]
        if self.video_writer is None:
            # Jetson'daki codec destegine gore mp4v kullanilamayabilir.
            video_yolu = self.oturum / "color_kayit.mp4"
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.video_writer = cv2.VideoWriter(str(video_yolu), fourcc,
                                                self.video_fps, (w, h))
            if not self.video_writer.isOpened():
                self.video_writer.release()
                self.video_writer = None
                raise RuntimeError("MP4 video yazici acilamadi. Codec destegini kontrol edin.")
            self.video_boyut = (w, h)
            self.bilgi(f"[VIDEO] Renkli kareler yaziliyor: {video_yolu}")
        if (w, h) != self.video_boyut:
            raise RuntimeError("Video akisi cozunurlugu degisti; video yazimi guvenli durduruldu.")
        self.video_writer.write(color_bgr)

    def fotograf_kaydet(self, kare, islenmis, kenarlar, histogram, numara, neden="ilk_kare"):
        self.snap_sayi += 1
        prefix = f"kare_{numara:06d}_{self.snap_sayi:03d}"
        # Orijinal Color korunur. Filtre uygulanmis goruntu AYRI dosyadadir.
        png_yaz(self.fotograflar / f"{prefix}_color.png", kare.color_bgr)
        png_yaz(self.fotograflar / f"{prefix}_filtreli.png", islenmis)
        png_yaz(self.fotograflar / f"{prefix}_kenarlar.png", kenarlar)
        if kare.depth_mm is not None:
            # Kayipsiz 16-bit PNG milimetre degerlerini saklar.
            png_yaz(self.fotograflar / f"{prefix}_depth_mm.png", kare.depth_mm)
            png_yaz(self.fotograflar / f"{prefix}_depth_onizleme.png",
                    derinlik_onizleme(kare.depth_mm, self.preview_depth_mm))
        with (self.fotograflar / f"{prefix}_histogram.csv").open(
            "w", encoding="utf-8", newline=""
        ) as f:
            yazar = csv.writer(f)
            yazar.writerow(["gri_deger", "piksel_sayisi"])
            for i, adet in enumerate(histogram):
                yazar.writerow([i, int(adet)])
        meta = {
            "dosya_on_eki": prefix,
            "kaydetme_nedeni": neden,
            "zaman": kare.zaman,
            "color_cozunurluk": [kare.color_bgr.shape[1], kare.color_bgr.shape[0]],
            "depth_cozunurluk": ([kare.depth_mm.shape[1], kare.depth_mm.shape[0]]
                                   if kare.depth_mm is not None else None),
            "color_sdk_timestamp_ham": kare.color_sdk_zaman_ham,
            "depth_sdk_timestamp_ham": kare.depth_sdk_zaman_ham,
            "depth_scale_sdk": kare.depth_olcek,
            "depth_hizalandi_mi": False,
            "depth_png_birimi": "mm (uint16)",
            "sdk_timestamp_birimi": "SDK surumune gore ayrica dogrulanmali",
        }
        (self.fotograflar / f"{prefix}_bilgi.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.bilgi(f"[FOTOGRAF] {prefix} kaydedildi (neden: {neden})")

    def rapor_yaz(self, ayarlar, okuma_hatasi, toplam_sure):
        n = self.metrik_sayi
        rapor = {
            "oturum": str(self.oturum),
            "kaynak": ayarlar["source"],
            "toplam_color_karesi": n,
            "bos_veya_eksik_kare_okumasi": okuma_hatasi,
            "calisma_suresi_s": round(toplam_sure, 2),
            "ortalama_dongu_fps": round(self.toplam["fps_dongu_ortalama"] / n, 2) if n else None,
            "ortalama_parlaklik": round(self.toplam["parlaklik"] / n, 2) if n else None,
            "ortalama_isleme_ms": round(self.toplam["isleme_ms"] / n, 2) if n else None,
            "depth_alinan_kare": self.depth_sayisi,
            "ortalama_depth_gecerli_yuzde": (
                round(self.toplam["depth_gecerli_yuzde"] / self.depth_sayisi, 2)
                if self.depth_sayisi else None
            ),
            "kaydedilen_fotograf_seti": self.snap_sayi,
            "notlar": [
                "FPS yazilim dongusu tahminidir; kameranin gercek FPS garantisi degildir.",
                "Bos okuma sayisi kesin kare kaybi sayisi degildir.",
                "Depth ve Color koordinatlari hizalanmamistir.",
                "Depth 16-bit PNG milimetreye yuvarlanmistir; ham SDK verisi degildir.",
                "MP4 sabit cikti FPS ile yazilir; orijinal sensor zamanlamasini korumaz.",
            ],
        }
        (self.oturum / "oturum_raporu.json").write_text(
            json.dumps(rapor, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self.bilgi("[RAPOR] oturum_raporu.json kaydedildi")
        return rapor

    def close(self):
        if self.video_writer is not None:
            self.video_writer.release()
        self.csv_dosya.close()
        self.log_dosya.close()

"""Gokboru genel goruntu isleme laboratuvar ve kalite yazilimi.

Kamera, renk/derinlik, kayit, test ve performans. Fiziksel kontrol yoktur.
"""

import argparse
from collections import deque
import json
import os
from pathlib import Path
from time import perf_counter

import cv2

from goruntu_isleme import (
    derinlik_analizi, derinlik_onizleme, ekrana_sigdir, renk_analizi
)
from kamera import kaynak_olustur
from kayit import KayitYoneticisi


AYAR_VARSAYILAN = {
    "source": "orbbec",  # orbbec, demo, webcam, video
    "depth": True,
    "gui": False,  # SSH uzerinden GUI kapali tutulur.
    "duration_seconds": 20,
    "output_dir": "ciktilar",
    "filter": "gaussian",  # none, gaussian, median, clahe
    "save_video": False,
    "video_output_fps": 15,
    "snapshot_interval_seconds": 0,
    "preview_depth_max_mm": 5000,
    "demo_fps": 15,
    "video_path": "",
    "webcam_index": 0,
}


def ayarlari_oku(args):
    ayarlar = AYAR_VARSAYILAN.copy()
    if args.config:
        dosya = Path(args.config)
        if not dosya.exists():
            raise FileNotFoundError(f"Ayar dosyasi bulunamadi: {dosya}")
        with dosya.open(encoding="utf-8") as f:
            ek = json.load(f)
        if not isinstance(ek, dict):
            raise ValueError("Ayar dosyasi bir JSON nesnesi olmali")
        bilinmeyen = set(ek) - set(ayarlar)
        if bilinmeyen:
            raise ValueError(f"Bilinmeyen ayar(lar): {sorted(bilinmeyen)}")
        ayarlar.update(ek)

    for anahtar, deger in (
        ("source", args.source), ("depth", args.depth),
        ("gui", args.gui), ("duration_seconds", args.seconds),
        ("save_video", args.save_video),
    ):
        if deger is not None:
            ayarlar[anahtar] = deger
    if ayarlar["source"] not in ("orbbec", "video", "webcam", "demo"):
        raise ValueError("source: orbbec, video, webcam veya demo olmali")
    if ayarlar["filter"] not in ("none", "gaussian", "median", "clahe"):
        raise ValueError("Gecersiz filter ayari")
    for anahtar in ("duration_seconds", "snapshot_interval_seconds"):
        if not isinstance(ayarlar[anahtar], (int, float)) or ayarlar[anahtar] < 0:
            raise ValueError(f"{anahtar} negatif olamaz")
    for anahtar in ("demo_fps", "video_output_fps", "preview_depth_max_mm"):
        if not isinstance(ayarlar[anahtar], (int, float)) or ayarlar[anahtar] <= 0:
            raise ValueError(f"{anahtar} sifirdan buyuk olmali")
    if ayarlar["source"] in ("webcam", "video") and ayarlar["depth"]:
        print("[UYARI] OpenCV video/webcam kaynaginda Depth yok; depth=false yapiliyor.")
        ayarlar["depth"] = False
    if ayarlar["gui"] and os.name != "nt" and not os.environ.get("DISPLAY"):
        raise RuntimeError("GUI istendi fakat DISPLAY yok. SSH baglantisinda gui=false kullanin.")
    return ayarlar


def baslik_yaz(ekran, metinler):
    for indeks, metin in enumerate(metinler):
        cv2.putText(ekran, metin, (12, 28 + 28 * indeks),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)


def calistir(ayarlar):
    kaynak = kaynak_olustur(ayarlar)
    kayit = None
    baslangic = perf_counter()
    onceki_zaman = None
    fps_degerleri = deque(maxlen=30)
    kare_sayisi = 0
    bos_okuma = 0
    ardisik_bos = 0
    onceki_fotograf_zamani = None
    hata_olustu = False

    try:
        kaynak.start()
        baslangic = perf_counter()  # Sure sayacini kamera acildiktan sonra baslat.
        kayit = KayitYoneticisi(
            ayarlar["output_dir"], ayarlar["save_video"],
            ayarlar["video_output_fps"], ayarlar["preview_depth_max_mm"]
        )
        kayit.bilgi(f"[BASLADI] kaynak={ayarlar['source']}, depth={ayarlar['depth']}, gui={ayarlar['gui']}")
        if ayarlar["gui"]:
            kayit.bilgi("[TUSLAR] S: fotograflari kaydet | Q/ESC: cik")
        while True:
            if ayarlar["duration_seconds"] and perf_counter() - baslangic >= ayarlar["duration_seconds"]:
                break

            basla_okuma = perf_counter()
            kare = kaynak.read()
            okuma_ms = (perf_counter() - basla_okuma) * 1000
            if kare is None:
                bos_okuma += 1
                ardisik_bos += 1
                if ayarlar["source"] == "video":
                    kayit.bilgi("[BILGI] Video dosyasinin sonuna ulasildi.")
                    break
                if ardisik_bos >= 10:
                    raise RuntimeError("Ardisik 10 kez Color karesi okunamadi. Kamera/USB/SDK kontrol edilmeli.")
                continue
            ardisik_bos = 0

            basla_isleme = perf_counter()
            islenmis, kenarlar, kalite, histogram = renk_analizi(
                kare.color_bgr, ayarlar["filter"]
            )
            kalite.update(derinlik_analizi(kare.depth_mm))
            isleme_ms = (perf_counter() - basla_isleme) * 1000

            simdi = perf_counter()
            if onceki_zaman is not None and simdi > onceki_zaman:
                fps_degerleri.append(1.0 / (simdi - onceki_zaman))
            fps = (sum(fps_degerleri) / len(fps_degerleri)) if fps_degerleri else 0.0
            onceki_zaman = simdi
            kare_sayisi += 1
            h, w = kare.color_bgr.shape[:2]
            metrik = {
                "zaman": kare.zaman, "kare": kare_sayisi,
                "kaynak": ayarlar["source"], "genislik": w, "yukseklik": h,
                "fps_dongu_ortalama": round(fps, 2),
                "okuma_ms": round(okuma_ms, 2), "isleme_ms": round(isleme_ms, 2),
                "color_sdk_zaman_ham": kare.color_sdk_zaman_ham,
                "depth_sdk_zaman_ham": kare.depth_sdk_zaman_ham,
            }
            metrik.update(kalite)
            kayit.metrik_yaz(metrik)
            kayit.kare_videoya(kare.color_bgr)

            kaydetme_nedeni = None
            if kare_sayisi == 1:
                kaydetme_nedeni = "ilk_kare"
            elif ayarlar["snapshot_interval_seconds"] > 0:
                if onceki_fotograf_zamani is not None and simdi - onceki_fotograf_zamani >= ayarlar["snapshot_interval_seconds"]:
                    kaydetme_nedeni = "otomatik_aralik"
            if kaydetme_nedeni:
                kayit.fotograf_kaydet(kare, islenmis, kenarlar, histogram,
                                      kare_sayisi, kaydetme_nedeni)
                onceki_fotograf_zamani = simdi

            if kare_sayisi % 30 == 0:
                kayit.bilgi(
                    f"[METRIK] kare={kare_sayisi} fps_dongu={fps:.1f} "
                    f"parlaklik={kalite['parlaklik']:.1f} "
                    f"netlik={kalite['netlik_laplacian']:.1f} "
                    f"isleme={isleme_ms:.1f}ms "
                    f"depth_gecerli={kalite['depth_gecerli_yuzde']}"
                )

            if ayarlar["gui"]:
                ekran = kare.color_bgr.copy()
                baslik_yaz(ekran, [
                    f"FPS (dongu): {fps:.1f}",
                    f"Parlaklik: {kalite['parlaklik']:.1f}",
                    f"Netlik gostergesi: {kalite['netlik_laplacian']:.1f}",
                ])
                cv2.imshow("Gokboru - Orijinal Color", ekrana_sigdir(ekran))
                cv2.imshow("Gokboru - Islenmis Gri", ekrana_sigdir(islenmis))
                cv2.imshow("Gokboru - Kenar Testi", ekrana_sigdir(kenarlar))
                if kare.depth_mm is not None:
                    onizleme = derinlik_onizleme(
                        kare.depth_mm, ayarlar["preview_depth_max_mm"]
                    )
                    cv2.imshow("Gokboru - Depth Onizleme", ekrana_sigdir(onizleme))
                tus = cv2.waitKey(1) & 0xFF
                if tus in (ord("q"), ord("Q"), 27):
                    break
                if tus in (ord("s"), ord("S")):
                    kayit.fotograf_kaydet(kare, islenmis, kenarlar, histogram,
                                          kare_sayisi, "klavye")
        kayit.bilgi(f"[SONUC] {kare_sayisi} Color karesi islendi.")
    except KeyboardInterrupt:
        if kayit:
            kayit.bilgi("[SONUC] Kullanici islemi durdurdu.")
    except Exception as exc:
        hata_olustu = True
        if kayit:
            kayit.bilgi(f"[HATA] {type(exc).__name__}: {exc}")
        else:
            print(f"[HATA] {type(exc).__name__}: {exc}")
    finally:
        try:
            kaynak.close()
        except Exception as exc:
            print(f"[UYARI] Kaynak kapatilamadi: {exc}")
        if ayarlar["gui"]:
            cv2.destroyAllWindows()
        if kayit is not None:
            try:
                rapor = kayit.rapor_yaz(ayarlar, bos_okuma, perf_counter() - baslangic)
                kayit.bilgi(f"[DOSYALAR] {kayit.oturum}")
                if rapor["toplam_color_karesi"] == 0:
                    hata_olustu = True
            finally:
                kayit.close()
    return 1 if hata_olustu else 0


def main():
    p = argparse.ArgumentParser(description="Gokboru kamera ve goruntu kalitesi laboratuvar yazilimi")
    p.add_argument("--config", default=str(Path(__file__).with_name("ayarlar.json")))
    p.add_argument("--source", choices=["orbbec", "demo", "video", "webcam"])
    depth = p.add_mutually_exclusive_group()
    depth.add_argument("--depth", dest="depth", action="store_true", default=None)
    depth.add_argument("--no-depth", dest="depth", action="store_false")
    gui = p.add_mutually_exclusive_group()
    gui.add_argument("--gui", dest="gui", action="store_true", default=None)
    gui.add_argument("--no-gui", dest="gui", action="store_false")
    p.add_argument("--seconds", type=float, default=None, help="0: sonsuz (Q ya da Ctrl+C ile cik)")
    p.add_argument("--save-video", action="store_true", default=None)
    args = p.parse_args()
    try:
        ayarlar = ayarlari_oku(args)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"[AYAR HATASI] {exc}")
        return 2
    return calistir(ayarlar)


if __name__ == "__main__":
    raise SystemExit(main())

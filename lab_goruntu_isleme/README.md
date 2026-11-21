# GÖKBÖRÜ — Görüntü İşleme Laboratuvarı (Örnek Gelişmiş Sürüm)

**Amaç:** Orbbec Gemini 335L kamerasının Jetson Orin Nano üzerinde Color / Depth görüntülerini okumak, temel OpenCV işlemleri uygulamak, görüntü kalitesi ölçmek, veri kaydetmek ve rapor üretmek. **Hedef tespiti, nesne takibi, nişan alma veya fiziksel müdahale işlevi yoktur.**

Bu proje eğitim ve güvenli laboratuvar testleri için hazırlanmış **örnek yazılımdır**. Gerçek cihaz üzerinde test yapılmadan yarışmaya hazır/çalışır bir ürün olarak görülmemelidir.

## Dosyalar

| Dosya | Görev |
| --- | --- |
| `main.py` | Ayarları okur; program döngüsünü, ölçümleri ve görüntüleme işlemlerini yönetir. |
| `kamera.py` | Orbbec SDK v2, video/webcam ve gerçek kameraya ihtiyaç duymayan demo kaynakları. |
| `goruntu_isleme.py` | Renk dönüşümleri, filtreler, Canny kenar görselleştirmesi, histogram, Color/Depth kalitesi. |
| `kayit.py` | PNG, 16-bit Depth PNG, renkli MP4, CSV, JSON, çalışma logları. |
| `ayarlar.json` | Jetson/Orbbec için temel ayarlar. |
| `ayarlar_demo.json` | Orbbec olmadan otomatik test. |
| `testler/` | Birim testleri. |

## Kurulu Python ortamını kontrol et (Jetson)

```bash
python3 --version
python3 -c "import cv2, numpy; print('OpenCV ve NumPy hazir')"
python3 -c "import pyorbbecsdk; print('Orbbec SDK hazir')"
```

Jetson'da zaten kurulmuş bir SDK varsa yeniden kurmaya gerek yok. Modülün kurulu olduğu **aynı Python ortamından** çalıştır. SDK kurulu değilse güncel resmî belge: <https://github.com/orbbec/pyorbbecsdk/tree/v2-main> (PyPI paket adı `pyorbbecsdk2`, import adı `pyorbbecsdk`). `requirements.txt` yalnızca NumPy/OpenCV bağımlılıklarını gösterir. Jetson sistem Python'u ile pip kurulumunu zorlamayın.

SDK paketi/SDK donanım sürücüsü/JetPack uyumluluğu cihazda ayrıca doğrulanmalıdır. Linux USB erişim izinleri de önemli olabilir.

## İlk olarak kamera olmadan dene

Proje klasöründe:

```bash
python3 main.py --config ayarlar_demo.json
```

`ciktilar_demo/oturum_.../` altında PNG, CSV ve JSON oluşması beklenir. Bu yalnızca **uygulamanın yazılım bölümlerini** test eder; Orbbec bağlantısını test etmez.

Birim testleri:

```bash
python3 -m unittest discover -s testler -v
```

## Jetson + Orbbec gerçek kamera testi

Orbbec Gemini 335L'yi Jetson'ın USB veri bağlantısına takın, SDK kurulu ve cihaz erişilebilir olsun. VS Code Remote SSH terminalinde ilk deneme:

```bash
python3 main.py --source orbbec --depth --no-gui --seconds 20
```

Sadece Color testi:

```bash
python3 main.py --source orbbec --no-depth --no-gui --seconds 20
```

Jetson'a fiziksel monitör bağlı ve grafik ortamı mevcutsa:

```bash
python3 main.py --source orbbec --depth --gui --seconds 0
```

Bu modda **S** ile snapshot, **Q** veya **ESC** ile çıkış yapılır. SSH terminalinde ekran açık değilse `--gui` kullanmayın.

Kayıtlı video için `ayarlar.json` içindeki `source` alanını `video`, `video_path` alanını dosya yolu olarak düzenleyin. `source=webcam` OpenCV UVC kameraları içindir, **Orbbec SDK eşdeğeri değildir**.

## Ayar dosyasındaki alanlar

- `source`: `orbbec`, `demo`, `webcam` veya `video`.
- `depth`: `true` ise Orbbec veya demo Depth akışı etkin. Video/webcam'de Depth yok.
- `gui`: `false` SSH terminalinden ekransız çalışmak için.
- `duration_seconds`: 20 saniye; `0` durdurulana dek devam.
- `output_dir`: oturum klasörlerinin oluşturulacağı yer.
- `filter`: `none`, `gaussian`, `median`, `clahe`.
- `save_video`: `true` MP4 video dosyası kaydını açmayı dener; Jetson codec desteği gereklidir.
- `video_output_fps`: MP4 dosyasının yazma FPS'si; gerçek kamera FPS'sinin ölçümü değildir.
- `snapshot_interval_seconds`: `0` ise ilk kare dışında otomatik fotoğraf yok; pozitifse belirli saniye aralığında snapshot.
- `preview_depth_max_mm`: yalnızca renkli derinlik önizlemesi için üst sınır, **kamera menzilini göstermez**.
- `demo_fps`: yapay demo kaynağındaki hedeflenen hız.
- `video_path`, `webcam_index`: OpenCV dosya / webcam kaynakları.

Komut satırından değiştirilebilen bazı seçenekler: `--source`, `--depth`/`--no-depth`, `--gui`/`--no-gui`, `--seconds`, `--save-video`.

## Çıktı örneği

```text
ciktilar/
  oturum_YYYYMMDD_HHMMSS_us/
    metrikler.csv
    oturum_raporu.json
    calisma.log
    color_kayit.mp4        (save_video=true ise)
    fotograflar/
      kare_000001_001_color.png
      kare_000001_001_filtreli.png
      kare_000001_001_kenarlar.png
      kare_000001_001_depth_mm.png       (Depth geldiyse)
      kare_000001_001_depth_onizleme.png (Depth geldiyse)
      kare_000001_001_histogram.csv
      kare_000001_001_bilgi.json
```

- `*_color.png`: **ham SDK paketinin aynısı değil**, SDK'den BGR'ye çözümlenmiş, filtrelenmemiş renkli görüntü.
- `*_filtreli.png`: Gri tonlamalı laboratuvar işleme sonucu.
- `*_kenarlar.png`: Canny kenar görüntüsü, genel görsel test.
- `*_depth_mm.png`: 16-bit tek kanallı dosya; mm'ye dönüştürülmüş/yuvarlanmış sayılar. İstediğin normal bir fotoğraf uygulaması dosyayı siyah gösterebilir; pikseli 16-bit olarak oku. **Ham SDK derinlik bitlerini korumaz.**
- `*_depth_onizleme.png`: yalnızca renkli gösterim; ölçüm olarak kullanma.
- `*_bilgi.json`: snapshot zaman bilgisi, çözünürlük, SDK ham zaman damgası, Depth ölçeği ve hizalama durumu.
- `metrikler.csv`: her Color karesi için kalite ve zaman ölçümleri.
- `oturum_raporu.json`: oturumun özet sonuçları.

## Performans ve ölçümlerin anlamı

| Alan | Anlamı |
| --- | --- |
| `fps_dongu_ortalama` | Son en fazla 30 yazılım döngüsünün ortalama anlık FPS tahmini. Sensör FPS'si veya gecikme garantisi değil. |
| `okuma_ms` | Kare okuma çağrısında geçirilen süre (SDK bekleme dahil). |
| `isleme_ms` | Color/Depth temel kalite analizi için harcanan süre. Video dosyası yazma/snapshot süresi dahil değil. |
| `parlaklik` | 0–255 aralığında gri görüntünün ortalaması. |
| `kontrast_std` | Gri piksel değerlerinin standart sapması. |
| `netlik_laplacian` | Laplacian varyansı; mutlak kalite eşiği değil. |
| `karanlik_oran_yuzde` | Gri değeri 30 altındaki piksellerin oranı. |
| `aydinlik_oran_yuzde` | Gri değeri 225 üzerindeki piksellerin oranı. |
| `doygunluk_ortalama` | HSV renk doygunluğu ortalaması. |
| `depth_gecerli_yuzde` | 0'dan büyük derinlik piksellerinin oranı. Sıfır dışındaki her değer mutlaka güvenilir demek değildir. |
| `color_sdk_zaman_ham` | SDK'nin döndürdüğü ham zaman damgası; birimi/clock alanı sürüme göre teyit edilir. |

## Sınırlar ve son sürüme geçmeden yapılacaklar

1. **Kamera ve Jetson'da gerçek test şart:** SDK/firmware/JetPack sürümleri ve USB bağlantı hızı kaydedilmeli.
2. **Color/Depth kalibrasyonu ve hizalaması YOK:** Color ve Depth'in karşılık gelen piksel konumları aynı kabul edilmemeli. Resmî Orbbec `AlignFilter` / cihaz kalibrasyon örnekleri laboratuvar amaçlı ayrıca değerlendirilebilir.
3. **Tam kare senkronizasyon garantisi yok:** Bir kare grubunun Color ve Depth zaman bilgileri kaydedilir; zaman ofseti doğrulanmalıdır.
4. **MP4 sabit FPS ile yazılır**, karelerin gerçek sensör zaman damgaları ayrı olarak korunmaz.
5. **Depth sınırları:** 16-bit PNG mm tam sayıya yuvarlama yapar; 0 'ölçüm yok' olarak sayılır. Diğer ölçümlerin belirsizlikleri değerlendirilmeli.
6. **Kesin kare kaybı sayısı ölçülmüyor:** Boş okuma sayısı tek başına kayıp kare adedi değildir.
7. **Hata toparlanması:** 10 başarısız okumadan sonra durur; otomatik yeniden bağlanma henüz yok.
8. **Uzun süreli gerçek cihaz testi yapılmadı:** Jetson sıcaklığı/RAM/CPU kullanımı ve dosya boyutu izlenmeli.
9. Bu uygulama yalnızca görüntü işleme laboratuvar testidir. **Algılama, takip, fiziksel yönlendirme, atış kontrolü veya hedefe müdahale kodu içermez.**

## Resmî referanslar

- Orbbec Python SDK v2: https://github.com/orbbec/pyorbbecsdk/tree/v2-main
- Örnek: `examples/advanced/03_save_image_to_disk.py`
- Örnek: `examples/beginner/03_color_and_depth_aligned.py`
- Gemini 330 serisi USB platform gereksinimleri: https://doc.orbbec.com/documentation/Orbbec%20Gemini%20330%20Series%20Documentation/Gemini%20330%20Series%20Supported%20Hosts%20and%20System%20Requirements%20%28USB%29

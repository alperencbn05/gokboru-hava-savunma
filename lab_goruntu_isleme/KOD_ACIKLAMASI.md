# GÖKBÖRÜ — Kod açıklamaları (başlangıç seviyesine uygun)

Bu belge `main.py`, `kamera.py`, `goruntu_isleme.py` ve `kayit.py` dosyalarını öğrenmek için hazırlanmıştır. Kamera okuma ve kalite analizi dışında nesne algılama / takip / fiziksel kontrol işlemi yoktur.

## 1. Bir kare nasıl ilerler?

1. `main.py` JSON ayarlarını okur.
2. `kamera.kaynak_olustur()` kaynak seçer: Orbbec SDK, demo, video veya webcam.
3. `kaynak.start()` bağlantıyı başlatır.
4. `kaynak.read()` bir `Kare` döndürür. `Kare` içindeki `color_bgr` NumPy dizisidir; varsa `depth_mm` de ayrı NumPy dizisidir.
5. `renk_analizi()` Color'dan gri görüntü, filtre, Canny kenar sonucu ve kalite metrikleri hesaplar.
6. `derinlik_analizi()` geçerli Depth piksel yüzdesi ve sayısal derinlik istatistiklerini hesaplar.
7. `KayitYoneticisi` görselleri, metrikleri ve oturum raporunu kaydeder.
8. Program biterken kaynak, CSV dosyası ve varsa video yazıcısı kapatılır.

## 2. Kamera kaynağı neden ayrı dosya?

`kamera.py` içinde kaynak sınıfları var:

- `OrbbecKaynak`: Jetson'a USB ile bağlanan Gemini 335L için SDK çağrıları.
- `VideoKaynak`: Normal video dosyası veya UVC webcam üzerinden OpenCV kareleri.
- `DemoKaynak`: Kamera olmadan test yapabilmek için bilgisayar tarafından oluşturulan yapay görüntü.

`Kare` veri yapısı, kameranın hangisi olduğundan bağımsız olarak benzer verileri tutar.

```python
@dataclass
class Kare:
    color_bgr: np.ndarray
    depth_mm: Optional[np.ndarray]
    zaman: str
```

- **NumPy dizisi**: Pikselleri sayı tablosu şeklinde tutar.
- **BGR**: OpenCV'nin renkli piksel kanal sırası: mavi, yeşil, kırmızı.
- **uint8**: Color genellikle kanal başına 0–255 sayı.
- **uint16**: Depth için 0–65535 arası tam sayı saklayabilen tür.
- **Optional**: Bazı kaynaklarda Depth bulunmayabilir.

### Color dönüşümü

```python
color = cv2.cvtColor(rgb_kare, cv2.COLOR_RGB2BGR)
```

RGB verisi OpenCV ile gösterilip kaydedilmeden önce BGR biçimine çevrilir. `orbbec_color_bgr` ayrıca MJPG, YUYV, UYVY, NV12, NV21, I420 ve BGR biçimleri için dönüşüm adımları içerir. Kameranın seçtiği formatın bu yöntemlerden biri olup olmadığı gerçek cihazda görülmeli. Bu örnek her olası SDK formatını desteklemez.

### Depth dönüşümü

```python
ham = np.frombuffer(frame.get_data(), dtype=np.uint16).reshape(h, w)
mm = ham.astype(np.float32) * frame.get_depth_scale()
```

1. Kamera hafızasındaki sayılar NumPy ile okunur.
2. Satır ve sütun sayısına göre düzenlenir.
3. SDK'den gelen ölçek faktörü uygulanarak mm cinsine dönüştürülür.
4. PNG için 16-bit tam sayıya yuvarlanır.

**Önemli:** Kamera Depth ve Color kareleri kendiliğinden aynı piksel koordinatına sahip değildir. Bu sürümde hizalama yoktur. Sensör zaman damgaları kaydedilse bile eşzamanlılık kalitesi ayrıca ölçülmelidir.

## 3. Görüntü işleme fonksiyonları

### `renk_analizi` ne yapar?

```python
gri = cv2.cvtColor(color_bgr, cv2.COLOR_BGR2GRAY)
```

Bu işlem renkli görüntüyü gri tonlara dönüştürür. Gri görüntü tek kanallıdır: renk tonu yerine parlaklık bilgisi taşır.

```python
islenmis = cv2.GaussianBlur(gri, (5, 5), 0)
```

Gaussian filtre yakın pikselleri ağırlıklı ortalayarak görüntüyü yumuşatır. Gürültüyü azaltabilir, ancak ayrıntıları da kaybettirebilir. Başka seçenekler:

- `none`: Orijinal gri görüntüyü kullan.
- `median`: Özellikle ani siyah-beyaz nokta gürültüsünü azaltmada faydalı olabilir.
- `clahe`: Küçük bölgelerde kontrastı artırma yöntemi; aşırı uygulandığında gürültüyü de belirginleştirebilir.

```python
kenarlar = cv2.Canny(gri, 70, 140)
```

Canny, görüntüdeki hızlı parlaklık değişimlerini kenar benzeri bir görünümde sunar. Bu sonuç genel görüntü analizi/görselleştirme içindir.

### Ölçümler

```python
parlaklik = float(gri.mean())
kontrast = float(gri.std())
netlik = float(cv2.Laplacian(gri, cv2.CV_64F).var())
```

- **Ortalama parlaklık**: Görüntünün genel aydınlık seviyesinin kaba göstergesi.
- **Kontrast standart sapması**: Gri piksel değerlerinin ne kadar dağıldığının göstergesi.
- **Laplacian varyansı**: Ayrıntı / keskin geçiş miktarına duyarlı ölçü; her sahnede aynı eşik kullanılmamalıdır.
- **Karanlık/aydınlık oranı**: Belirlenen 30 ve 225 gri değer eşiklerini aşan pikseller.
- **Histogram**: 0–255 arasındaki her gri değerin görüntüde kaç kez bulunduğu.

### `derinlik_analizi`

```python
gecerli = depth_mm > 0
gecerli_yuzde = gecerli.mean() * 100
```

Derinlik değeri sıfırdan büyük olan piksellerin oranını hesaplar. **Sıfır olmayan her değer kesin doğru ölçüm demek değildir.** Laboratuvar karşılaştırmaları gereklidir.

`derinlik_onizleme` ise mm değerlerini renklerle görselleştirir. Üretilen renkli PNG ölçüm verisi olarak **kullanılmaz**.

## 4. Kayıt modülü: `kayit.py`

`KayitYoneticisi` her program çalışmasında benzersiz bir oturum klasörü açar.

- Color görüntüsünü filtrelemeden BGR PNG olarak kaydeder.
- Filtrelenmiş gri görüntüyü ayrı kaydeder.
- Canny kenar görüntüsünü ayrı kaydeder.
- Varsa Depth'i **uint16 mm** PNG olarak kaydeder.
- Histogram için iki sütunlu CSV oluşturur.
- Kare çözünürlükleri, zaman bilgisi, Depth ölçeği için JSON oluşturur.
- Her kareyi ölçen `metrikler.csv` ve oturum sonunda `oturum_raporu.json` yazar.
- İsteğe bağlı MP4 kaydı yapar. MP4 yazıcı desteği Jetson ortamında ayrı test gerektirir.

Örnek bir kayıt sözlüğü:

```python
meta = {"zaman": "...", "depth_hizalandi_mi": False, "depth_scale_sdk": 1.0}
```

**JSON** metin tabanlı, anahtar–değer yapısında veri biçimidir. İnsan okuyabilir, farklı programlama dilleri de işleyebilir.

## 5. `main.py` ana döngüsü

Kodun mantığı basitleştirilmiş olarak:

```python
kaynak.start()
while True:
    kare = kaynak.read()
    islenmis, kenarlar, metrikler, histogram = renk_analizi(kare.color_bgr)
    # Depth analizi, CSV ve PNG kaydı, gerekiyorsa GUI gösterimi
kaynak.close()
```

Gerçek kodda bunun çevresinde **hata kontrolleri**, **süre sınırı**, **FPS ölçümü**, **dosya kaydı** ve **kaynakların kapatılması** da vardır.

`try/finally` kullanımı özellikle önemlidir: Program hata alsa da açık kamera ve dosyalar mümkünse düzgün kapatılır.

### FPS ile diğer süreler arasındaki fark

- **FPS** (Frames Per Second): Bir saniyedeki kare sayısı.
- **Okuma süresi**: SDK'den kare bekleme ve alma süresi.
- **İşleme süresi**: Görüntü kalitesi hesaplarının süresi.
- **Toplam sistem gecikmesi**: Kamera pozlaması, aktarım, kuyruklar ve ekran/aktarımı da kapsayabilir. Mevcut sürümde bu toplam güvenilir biçimde ölçülmüyor.

FPS ölçümümüz kameranın üretici ayarı değildir; uygulamanın görüntüyü işleme döngüsüne ilişkin tahmindir.

## 6. Sırasıyla nasıl öğrenmelisin?

1. `ayarlar_demo.json` ile programı çalıştır; dosyaları aç.
2. `goruntu_isleme.py` içindeki gri tonlama ve parlaklık hesaplamalarını incele.
3. `filter` seçeneğini `none`, `gaussian`, `median`, `clahe` arasında değiştir; farkları karşılaştır.
4. `depth_mm.png` dosyasını `cv2.IMREAD_UNCHANGED` ile açıp `dtype` ve `shape` değerlerini yazdır.
5. `metrikler.csv` dosyasındaki parlaklık/işleme süresi değerlerini incele.
6. `kamera.py` içine geçip Orbbec SDK `Pipeline` akışını incele.
7. Gerçek Jetson + Orbbec Color testinden sonra Depth testine geç.

Öğrendiğin kavramları test etmeden bir sonraki adıma geçmek zorunda değilsin.

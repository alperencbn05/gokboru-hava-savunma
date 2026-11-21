# Gokboru Hava Savunma Sistemi

TEKNOFEST 2026 Çelikkubbe Hava Savunma Sistemleri Yarışması için geliştirilen
hedef tespit/takip yazılımı. Bu depo şu an yalnızca **görüntü işleme / hedef
takip** modülünü içeriyor; motor sürücü (firmware), mekanik ve tetik/ateşleme
donanımı ayrı ekip üyeleri tarafından geliştirilecek ve aşağıdaki protokol
üzerinden bu koda bağlanacak.

## Dosya yapısı

| Dosya | Sorumluluk |
|---|---|
| `config.py` | Tüm kalibrasyon sabitleri (kamera, HSV renkleri, mesafe, menzil kuralları) |
| `kamera.py` | Kamera kaynağı (Orbbec/webcam/video/demo) — takım arkadaşının görüntü işleme lab projesinden alındı, bkz. `lab_goruntu_isleme/` |
| `vision_detector.py` | YOLO+ByteTrack ile tespit, dost/düşman renk sınıflandırması, mesafe (gerçek derinlik varsa onu, yoksa pinhole tahmini) |
| `target_lock.py` | Tıklayarak kilitleme, ID kaybında kurtarma, otomatik hedef seçimi |
| `engagement.py` | "Ateş serbest mi?" kuralları (aşama, dost/düşman, menzil, yasak bölge, acil durdur) |
| `serial_link.py` | Arduino ile seri haberleşme + acil durdur durumunu okuma |
| `ui_panel.py` | Video görüntüsünün yanındaki tıklanabilir kontrol paneli (buton + durum yazıları) |
| `main.py` | Kamera döngüsü, çizimler, panel/klavye kontrolleri — her modülü birleştiren yer |

## Neden bu şekilde ayrıldı (ekip entegrasyonu)

5-6 kişilik bir ekipte herkesin tek bir `targetTracker.py` dosyasını aynı anda
düzenlemesi sürekli merge çatışması (conflict) yaratır. Bunun yerine her
modül **net bir girdi/çıktı sözleşmesine** sahip:

- Görüntü işleme ekibi (sen) → `vision_detector.py` + `target_lock.py` içinde
  çalışır, dışarıya `Target` nesneleri (id, kutu, dost/düşman, tip, mesafe)
  üretir. Kamera erişimi artık `kamera.py` üzerinden (bkz. aşağıdaki
  "Kamera kaynağı" bölümü) — kendi `cv2.VideoCapture` çağrısı yazmaya
  gerek yok.
- Gömülü/elektronik ekip → `firmware/gokboru_turret/gokboru_turret.ino`
  başlangıç noktası olarak verildi (pan/tilt servo + tetik/lazer rölesi +
  acil durdur okuma). Bu, gerçek donanımla **hiç test edilmedi** —
  pin numaraları, `GAIN`, `FIRE_PULSE_MS`, açı sınırları saha testinde
  kalibre edilmeli. Python tarafına dokunmaya gerek yok.
- Mekanik/güvenlik ekibi → acil durdur butonunun gerçekten motoru/ateşi
  kesmesinden sorumlu (bu yazılımla değil donanımla sağlanmalı, bkz. Şartname
  4.2); yazılım tarafında sadece `config.NO_FIRE_ZONE_X_FRACTION` ve
  `ENGAGEMENT_RANGES_M` değerlerini saha ölçümlerine göre güncellemeleri
  yeterli.
- Arayüz (UI) ekibi → şu an `ui_panel.py` içinde video görüntüsünün yanına
  gömülü basit bir panel var (buton + durum yazıları, aynı OpenCV
  penceresinde). Ayrı bir UI (joystick, harici ekran, web paneli vb.) 
  geliştirilecekse `main.py`'deki `on_mouse`/klavye kısmı yerine o UI'nin
  çağıracağı aynı fonksiyonlar kullanılacak (`lock.release()`,
  `state["stage"]`, `state["mode"]`, `state["fire_once"]`) — diğer modüllere
  dokunulmayacak.

**Pratik kural:** Herkes kendi dosyasında/modülünde çalışıp GitHub'da ayrı
branch açsın (örn. `feature/firmware-protokol`, `feature/mesafe-kalibrasyon`,
`feature/ui`), işi bitince `main` branch'ine Pull Request ile birleştirsin.
Böylece `main.py` dışındaki dosyalarda çatışma riski çok düşer.

## Seri Protokol (Python <-> Arduino)

```
PC -> Arduino : "X{dx}Y{dy}F{fire}\n"
                 dx, dy : piksel hatası (int, pozitif/negatif)
                 fire   : 0 veya 1 (1 = tetikle)

Arduino -> PC : "ESTOP:0\n" veya "ESTOP:1\n"
                 Acil durdur butonunun anlık durumu.
                 (Gerçek enerji/ateş kesimi donanımda olmalı; bu satır
                  yazılımın da aynı duruma uymasını sağlar.)
```

Firmware tarafını yazan arkadaş bu formatı değiştirmek isterse önce burada
(README) güncellesin, sonra `serial_link.py`'deki `send`/`poll_estop`
fonksiyonlarını güncelleyelim — tek doğru kaynak burası olsun.

Not: `fire=1` isteği `SerialLink.request_fire()` ile kuyruğa alınır ve bir
sonraki `send()` çağrısında -throttle penceresine denk gelse bile- kesin
iletilir. Eski sürümde `fire` doğrudan `send()`'e parametre olarak
geçiyordu ve throttle penceresine denk gelen bir ateş isteği sessizce
kaybolabiliyordu; bu düzeltildi.

## Firmware (Arduino)

`firmware/gokboru_turret/gokboru_turret.ino`: pan/tilt servoyu P
kontrolcüyle sürer, `fire=1` geldiğinde tetik/lazer rölesini kısa bir
pulse için tetikler, acil durdur butonunu okuyup `ESTOP:` satırlarını
gönderir. **Gerçek donanımla hiç denenmedi** — Arduino IDE kurulu
olmadığı için bu ortamda derlenemedi de; flaşlamadan önce bir arkadaşın
Arduino IDE'de açıp derlemesi/yüklemesi gerekiyor.

Varsayılan pinler (kendi devrenize göre dosyanın başında değiştirin):
- `PIN_SERVO_PAN = 9`, `PIN_SERVO_TILT = 10`
- `PIN_FIRE = 7` (röle/MOSFET → airsoft tetiği veya lazer)
- `PIN_ESTOP = 2` (buton, `INPUT_PULLUP`, basılı = LOW)

**Güvenlik:** Bu firmware'deki acil durdur kontrolü ek bir yazılım
katmanıdır. Şartname 4.2'ye göre gerçek kesme donanımda olmalı — buton,
motor sürücü ve ateş rölesinin besleme hattında mikrodenetleyiciden
bağımsız şekilde seri bağlanmalı.

## Kalibrasyon / TODO (yarışmadan önce yapılması gerekenler)

- [ ] `config.RED_HSV_RANGE_*` / `BLUE_HSV_RANGE`: gerçek hedef maketleri ve
      saha ışığıyla test edip aralıkları daraltın (şu an kaba varsayılan).
- [ ] `config.FOCAL_PX` (sadece Orbbec/derinlik yoksa kullanılan yedek
      yöntem için): bilinen bir mesafede (örn. 5 m) gerçek maketle ölçüp
      hesaplayın: `FOCAL_PX = (bbox_yükseklik_px * bilinen_mesafe_m) / gerçek_yükseklik_m`
- [ ] `config.REAL_HEIGHT_M`: her hedef tipinin gerçek yüksekliğini ölçüp
      girin (yalnızca pinhole yedek yöntemi için gerekli).
- [ ] Orbbec derinliği kullanılacaksa: `tools/test_depth.py` ile gerçek
      donanımda mesafe değerlerinin doğruluğunu onaylayın.
- [ ] `config.MODEL_PATH` + `CLASS_NAME_MAP`: F16/Helikopter/Balistik
      Füze/Mini-Micro İHA maketlerinin fotoğraflarıyla özel bir YOLO modeli
      eğitilince buraya bağlanacak (şu an `yolov8n.pt` bu sınıfları bilmiyor,
      sadece genel COCO nesneleri tanıyor — Aşama-3 ve KTR Yetenek-6 için bu
      adım zorunlu).
- [ ] `config.NO_FIRE_ZONE_X_FRACTION`: saha/hakem ölçümlerine göre
      ayarlanmalı.

## Jetson Orin Nano kurulumu

`jetson/setup_jetson.sh` — apt paketleri, performans modu, dialout izni,
ultralytics/pyserial kurulumunu otomatikler. **PyTorch adımı otomatik
değil** (JetPack sürümüne özel wheel elle indirilip kurulmalı, script
bunu ortada durup hatırlatır). Gerçek bir Jetson'da test edilmedi —
adım adım çalıştırıp her çıktıyı kontrol edin.

```bash
chmod +x jetson/setup_jetson.sh
./jetson/setup_jetson.sh
```

## Kamera kaynağı (`kamera.py`)

Bir takım arkadaşı ayrı bir "görüntü işleme laboratuvarı" projesi
yazdı (bkz. `lab_goruntu_isleme/`) — kamera erişimi, format dönüşümleri
ve derinlik okuma kısmı benim ilk yazdığım tahmini koddan çok daha
sağlam ve **birim testleri geçiyor** (`lab_goruntu_isleme/testler/`).
Bu yüzden `main.py` artık kendi `kamera.py`'sini (oradan kopyalanan,
değiştirilmemiş hali) kullanıyor, benim eski `depth_source.py`'m
kaldırıldı.

`config.CAMERA_SOURCE` dört değer alabilir:
- `"webcam"` — normal USB kamera (şu anki Windows geliştirme varsayılanı)
- `"orbbec"` — gerçek Orbbec Gemini 335L (Jetson'da, `pyorbbecsdk2` kurulu olmalı)
- `"video"` — kayıtlı bir dosya (`config.CAMERA_VIDEO_PATH`)
- `"demo"` — hiçbir donanım gerektirmeyen sahte görüntü (yazılım testi için)

`config.CAMERA_DEPTH = True` + `CAMERA_SOURCE = "orbbec"` ise
`vision_detector.py` artık **gerçek derinlik verisini** kullanır (hedefin
piksel konumundaki küçük bir pencerenin medyan derinliği) — `config.FOCAL_PX`
pinhole tahmini sadece derinlik yoksa veya o noktada geçerli ölçüm
bulunamazsa devreye girer.

**Doğrulanmış:** `lab_goruntu_isleme`'deki 5 birim testini ve `demo`
kaynağıyla uçtan uca çalıştırdım, hepsi geçti. **Doğrulanmamış:** gerçek
Orbbec donanımıyla hiç denenmedi — `tools/test_depth.py` ile önce tek
başına doğrulayın:

```bash
python tools/test_depth.py
```

**Bilinen risk:** Kamera fiziksel olarak takılı/açık değilken
`Pipeline()` oluşturma adımı temiz bir Python hatası vermeden süreci
sert biçimde sonlandırabiliyor (try/except ile yakalanamıyor) — bunu
bu makinede pyorbbecsdk kuruluyken (kamerasız) denerken gördüm. Hata
mesajı görmeden program aniden kapanırsa önce kameranın takılı/açık
olduğunu kontrol edin.

## `lab_goruntu_isleme/` — takım arkadaşının bağımsız lab aracı

Bu klasör, hedef tespiti/takip/ateşleme **içermeyen**, sadece kamera +
görüntü kalitesi + kayıt yapan bağımsız bir araç (kendi `README.md` ve
`KOD_ACIKLAMASI.md`'si var). `main.py`'den tamamen ayrı çalışır —
kalibrasyon, görüntü kalitesi ölçümü (parlaklık/netlik/histogram) ve
Color+Depth kare kaydı için kullanışlı. Kendi `kamera.py` kopyasını
içinde tutuyor (repo kökündeki ile aynı, değiştirilmedi).

```bash
cd lab_goruntu_isleme
python main.py --config ayarlar_demo.json   # kamerasiz hizli test
python -m unittest discover -s testler -v   # birim testleri
```

## Parça parça test (yeni makinede / Jetson'da)

`main.py`'yi tam haliyle çalıştırmadan önce şu sırayla doğrulayın:

1. `python tools/test_camera.py` — sadece kamera açılıyor mu, FPS ne?
2. `python tools/test_serial.py` — sadece Arduino bağlantısı, pan servo salınımı, bir atımlık ateş.
3. (Opsiyonel) `python tools/test_depth.py` — Orbbec derinlik okuması gerçekçi mi?
4. İkisi/üçü de çalışıyorsa `python main.py` ile tam sistemi deneyin.

## Çalıştırma

```bash
pip install -r requirements.txt
python main.py
```

Hiç kamera/Arduino yokken sadece yazılımı denemek için `config.py`'de
`CAMERA_SOURCE = "demo"` yapın — gerçek donanım gerekmez. Arduino bağlı
değilse veya COM portu farklıysa `serial_link.py` otomatik "SİMÜLASYON
modu" ile devam eder (motor komutları gönderilmez, görüntü işleme ve
klavye kontrolleri yine test edilebilir).

Pencere açılınca sağda bir kontrol paneli görünür: **ASAMA 1/2/3**, **MOD
DEĞİŞTİR**, **KİLİDİ BIRAK**, **ATEŞ** butonları + anlık durum (kilit,
dost/düşman, tip, mesafe, ateş izni/sebebi, acil durdur). Video alanında
sol tık hedefe kilitler, sağ tık kilidi bırakır. Aynı işlevler klavyeden de
çalışır: `1`/`2`/`3` aşama seçimi, `M` manuel/otonom geçiş, `SPACE` tek
atımlık ateş isteği, `Q` çıkış.

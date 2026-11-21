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
| `vision_detector.py` | YOLO+ByteTrack ile tespit, dost/düşman renk sınıflandırması, mesafe tahmini |
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
  üretir.
- Gömülü/elektronik ekip → Arduino tarafında `serial_link.py`'nin beklediği
  protokolü (aşağıda) uygulayan bir firmware yazar. Python tarafına
  dokunmasına gerek yok.
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

## Kalibrasyon / TODO (yarışmadan önce yapılması gerekenler)

- [ ] `config.RED_HSV_RANGE_*` / `BLUE_HSV_RANGE`: gerçek hedef maketleri ve
      saha ışığıyla test edip aralıkları daraltın (şu an kaba varsayılan).
- [ ] `config.FOCAL_PX`: bilinen bir mesafede (örn. 5 m) gerçek maketle
      ölçüp hesaplayın: `FOCAL_PX = (bbox_yükseklik_px * bilinen_mesafe_m) / gerçek_yükseklik_m`
- [ ] `config.REAL_HEIGHT_M`: her hedef tipinin gerçek yüksekliğini ölçüp
      girin.
- [ ] `config.MODEL_PATH` + `CLASS_NAME_MAP`: F16/Helikopter/Balistik
      Füze/Mini-Micro İHA maketlerinin fotoğraflarıyla özel bir YOLO modeli
      eğitilince buraya bağlanacak (şu an `yolov8n.pt` bu sınıfları bilmiyor,
      sadece genel COCO nesneleri tanıyor — Aşama-3 ve KTR Yetenek-6 için bu
      adım zorunlu).
- [ ] `config.NO_FIRE_ZONE_X_FRACTION`: saha/hakem ölçümlerine göre
      ayarlanmalı.

## Çalıştırma

```bash
pip install -r requirements.txt
python main.py
```

Arduino bağlı değilse veya COM portu farklıysa `serial_link.py` otomatik
"SİMÜLASYON modu" ile devam eder (motor komutları gönderilmez, görüntü
işleme ve klavye kontrolleri yine test edilebilir).

Pencere açılınca sağda bir kontrol paneli görünür: **ASAMA 1/2/3**, **MOD
DEĞİŞTİR**, **KİLİDİ BIRAK**, **ATEŞ** butonları + anlık durum (kilit,
dost/düşman, tip, mesafe, ateş izni/sebebi, acil durdur). Video alanında
sol tık hedefe kilitler, sağ tık kilidi bırakır. Aynı işlevler klavyeden de
çalışır: `1`/`2`/`3` aşama seçimi, `M` manuel/otonom geçiş, `SPACE` tek
atımlık ateş isteği, `Q` çıkış.

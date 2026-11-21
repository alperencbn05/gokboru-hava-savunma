"""
Gokboru Hava Savunma Sistemi - Merkezi Ayarlar

Tum kalibrasyon ve donanim sabitleri burada toplanir. Baska bir modulde
sayi/esik degeri hardcode etmek yerine buraya ekleyip oradan import edin.
"""

import platform

import cv2

# --- Kamera ---
CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Gelistirme Windows'ta basladi (CAP_DSHOW Windows'a ozel bir backend).
# Jetson/Linux'ta bu backend yok; orada V4L2 kullanilir. USB webcam icin
# asagidaki yeterli olmali. CSI (seritli) kamera kullanacaksaniz
# CAMERA_INDEX yerine bir GStreamer pipeline string'i gerekir - o zaman
# haber verin, main.py'yi ona gore guncelleriz.
CAMERA_BACKEND = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_V4L2

# --- Model ---
# Su an yolov8n.pt COCO ile egitilmis genel bir model; "F16", "Helikopter",
# "Balistik Fuze", "Mini/Micro IHA" siniflarini TANIMIYOR. Asama-3 ve KTR
# Yetenek-6 icin kendi hedef maketlerinizle egitilmis ozel bir model gerekiyor.
# O model hazir oldugunda sadece MODEL_PATH ve CLASS_NAME_MAP'i guncelleyin,
# baska hicbir dosyaya dokunmaniz gerekmez.
MODEL_PATH = "yolov8n.pt"

# Ozel model egitilince: {class_id: "F16" | "HELIKOPTER" | "BALISTIK_FUZE" | "MINI_MICRO_IHA"}
CLASS_NAME_MAP: dict[int, str] = {}

# --- Seri Port (Arduino) ---
# Windows'ta "COM4" gibi, Linux/Jetson'da "/dev/ttyACM0" veya "/dev/ttyUSB0"
# gibi olur. Jetson'da Arduino'yu takip cikarip `ls /dev/tty*` ile hangi
# portun degistigine bakarak bulun, sonra burayi guncelleyin.
SERIAL_PORT = "COM4" if platform.system() == "Windows" else "/dev/ttyACM0"
BAUD_RATE = 115200
SERIAL_INTERVAL = 0.030  # saniye, komut gonderme araligi

# --- Nisangah / Kilit ---
DEADZONE = 15
MAX_LOST_FRAMES = 20
MAX_RECOVERY_DISTANCE = 80
# Otomatik secimde (kilit yokken) hedef degistirmeden once yeni hedefin
# eskisinden kac piksel daha yakin olmasi gerektigi. Titremeyi (flicker) onler.
AUTO_SWITCH_HYSTERESIS_PX = 40

WINDOW_NAME = "Gokboru Hava Savunma - Target Tracker"

# --- Dost / Dusman Renk Siniflandirmasi ---
# Sartname 5.4: Hedef maketinin GOVDESI kirmizi (dusman) veya mavi (dost).
# Maketin ALTINDAKI balon HER ZAMAN kirmizidir -> siniflandirmada kullanilmaz,
# bu yuzden kutunun yalnizca ust kismi (govde) ornekleniyor.
FACTION_BODY_TOP_RATIO = 0.75  # bbox'in sadece ust %75'i govde kabul edilir
FACTION_MIN_COVERAGE = 0.12    # kirmizi/mavi piksel orani bu esigin altindaysa "BILINMIYOR"

# HSV araliklari saha isiginda kalibre edilmeli (gercek maketle test edin).
RED_HSV_RANGE_1 = ((0, 90, 60), (10, 255, 255))
RED_HSV_RANGE_2 = ((170, 90, 60), (180, 255, 255))
BLUE_HSV_RANGE = ((95, 80, 50), (135, 255, 255))

# --- Mesafe Tahmini (pinhole model) ---
# distance_m = (gercek_yukseklik_m * FOCAL_PX) / bbox_yukseklik_px
# FOCAL_PX bilinen bir mesafede (orn. 5m) gercek hedefle olculerek bulunur:
#   FOCAL_PX = (bbox_yukseklik_px * bilinen_mesafe_m) / gercek_yukseklik_m
# Kalibre edilmeden None birakilir; UI "KALIBRE EDILMEDI" gosterir.
FOCAL_PX: float | None = None

REAL_HEIGHT_M = {
    "F16": 0.30,             # TODO: gercek maketi olcup guncelleyin
    "HELIKOPTER": 0.25,
    "BALISTIK_FUZE": 0.35,
    "MINI_MICRO_IHA": 0.15,
    "DEFAULT": 0.25,
}

# --- Asama 3 Menzil Kurallari (Sartname 6.3) ---
# (min_m, max_m) - bu araligin disindaki imha puana katilmiyor.
ENGAGEMENT_RANGES_M = {
    "F16": (10, 15),
    "HELIKOPTER": (5, 15),
    "BALISTIK_FUZE": (5, 15),
    "MINI_MICRO_IHA": (0, 15),
}

# --- Atisa Yasak Bolge (Sartname 4.2) ---
# Kare genisliginin (0.0-1.0) hangi kismina ates izni var. Varsayilan: tum kare acik.
# Saha/hakem olcumlerine gore mutlaka guncelleyin. Gercek guvenlik siniri
# MEKANIK olmali (sistem fiziksel olarak donemesin); bu sadece yazilim katmaninda
# ek bir emniyet kemeri.
NO_FIRE_ZONE_X_FRACTION = (0.0, 1.0)

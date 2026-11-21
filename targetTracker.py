import cv2
import numpy as np
import serial
import time
from ultralytics import YOLO

# 1. Model Yükleme
model = YOLO("yolov8n.pt")

# 2. Seri Port (Arduino) Başlatma
SERIAL_PORT = "COM4"
BAUD_RATE = 115200

try:
    arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.01)
    time.sleep(2)
    print(f"[BAGLANTI] Arduino {SERIAL_PORT} baglantisi basarili.")
except Exception as e:
    arduino = None
    print(f"[UYARI] Arduino baglanamadi ({e}). SIMULASYON modu aktif.")

# 3. Kamerayı Başlatma
# Orbbec veya harici kamera genelde 0, 1 veya 2 indeksinde olur
CAMERA_INDEX = 0
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

DEADZONE = 15
WINDOW_NAME = "Gokboru Hava Savunma - Target Tracker"

# Hedef Takip ve Hafıza Parametreleri
manual_locked_id = None
last_known_center = None
lost_counter = 0
MAX_LOST_FRAMES = 20
MAX_RECOVERY_DISTANCE = 80

clicked_point = None
last_serial_time = 0
SERIAL_INTERVAL = 0.030

# Fareyle Seçim Fonksiyonu
def mouse_callback(event, x, y, flags, param):
    global clicked_point, manual_locked_id, last_known_center, lost_counter
    if event == cv2.EVENT_LBUTTONDOWN:
        clicked_point = (x, y)
    elif event == cv2.EVENT_RBUTTONDOWN:
        manual_locked_id = None
        last_known_center = None
        lost_counter = 0
        clicked_point = None
        print("[BILGI] Kilit serbest birakildi.")

cv2.namedWindow(WINDOW_NAME)
cv2.setMouseCallback(WINDOW_NAME, mouse_callback)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("[HATA] Kameradan goruntu alinamiyor. CAMERA_INDEX degerini 1 veya 2 yapmayi deneyin.")
        break

    # Ayna etkisini düzeltme (Yatayda çevir)
    frame = cv2.flip(frame, 1)

    height, width, _ = frame.shape
    frame_cx, frame_cy = width // 2, height // 2

    # Merkez Nişangah Çizimi
    cv2.line(frame, (frame_cx - 20, frame_cy), (frame_cx + 20, frame_cy), (0, 255, 0), 1)
    cv2.line(frame, (frame_cx, frame_cy - 20), (frame_cx, frame_cy + 20), (0, 255, 0), 1)
    cv2.circle(frame, (frame_cx, frame_cy), DEADZONE, (0, 255, 0), 1)

    # 4. Yapay Zeka Takip (ByteTrack)
    results = model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)

    active_targets = []
    primary_target = None
    min_distance = float("inf")

    if results and results[0].boxes and results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.int().cpu().numpy()

        for box, track_id in zip(boxes, track_ids):
            x1, y1, x2, y2 = box
            
            # Yukarı çıkamama sorununu çözen hedefleme noktası (üstten %30)
            target_cx = int((x1 + x2) / 2)
            target_cy = int(y1 + (y2 - y1) * 0.3)

            dist_to_center = np.hypot(target_cx - frame_cx, target_cy - frame_cy)

            target_data = {
                "id": track_id,
                "box": (int(x1), int(y1), int(x2), int(y2)),
                "center": (target_cx, target_cy),
                "dist": dist_to_center,
                "dx": target_cx - frame_cx,
                "dy": target_cy - frame_cy
            }
            active_targets.append(target_data)

            # Tıklanan noktaya göre kilitleme
            if clicked_point is not None:
                cx, cy = clicked_point
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    manual_locked_id = track_id
                    last_known_center = (target_cx, target_cy)
                    lost_counter = 0
                    clicked_point = None
                    print(f"[KILIT] ID: {manual_locked_id} hedefine kilitlendi.")

        # --- GELİŞMİŞ KİLİT KORUMA VE KURTARMA ---
        if manual_locked_id is not None:
            # 1. Kilitli ID hala aktif mi?
            for target in active_targets:
                if target["id"] == manual_locked_id:
                    primary_target = target
                    last_known_center = target["center"]
                    lost_counter = 0
                    break

            # 2. ID anlık değiştiyse yakınlık kurtarması yap
            if primary_target is None and last_known_center is not None:
                closest_target = None
                min_drift = float("inf")

                for target in active_targets:
                    drift = np.hypot(target["center"][0] - last_known_center[0],
                                     target["center"][1] - last_known_center[1])
                    if drift < min_drift and drift < MAX_RECOVERY_DISTANCE:
                        min_drift = drift
                        closest_target = target

                if closest_target is not None:
                    manual_locked_id = closest_target["id"]
                    primary_target = closest_target
                    last_known_center = primary_target["center"]
                    lost_counter = 0

            # 3. Kilit tamamen düştü mü kontrolü
            if primary_target is None:
                lost_counter += 1
                if lost_counter > MAX_LOST_FRAMES:
                    manual_locked_id = None
                    last_known_center = None
                    lost_counter = 0
        else:
            # Manuel seçim yoksa merkeze en yakın olanı otomatik seç
            for target in active_targets:
                if target["dist"] < min_distance:
                    min_distance = target["dist"]
                    primary_target = target

    # --- ÇİZİMLER VE KONTROL ---
    for target in active_targets:
        x1, y1, x2, y2 = target["box"]
        tcx, tcy = target["center"]
        t_id = target["id"]

        if primary_target and t_id == primary_target["id"]:
            # KİLİTLİ HEDEF (Kırmızı Kutu)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.circle(frame, (tcx, tcy), 5, (0, 0, 255), -1)
            cv2.line(frame, (frame_cx, frame_cy), (tcx, tcy), (0, 0, 255), 2)
            cv2.putText(frame, f"[LOCKED] ID:{t_id}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

            dx, dy = target["dx"], target["dy"]
            motor_x = 0 if abs(dx) < DEADZONE else dx
            motor_y = 0 if abs(dy) < DEADZONE else dy

            cv2.putText(frame, f"Kilitli ID: {t_id} | Hata: ({motor_x}, {motor_y})", 
                        (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            # Arduino'ya Veri Gönderme
            current_time = time.time()
            if arduino is not None and (current_time - last_serial_time) > SERIAL_INTERVAL:
                command = f"X{motor_x}Y{motor_y}\n"
                arduino.write(command.encode("utf-8"))
                last_serial_time = current_time
        else:
            # DİĞER HEDEFLER (Sarı Kutu)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 1)
            cv2.circle(frame, (tcx, tcy), 3, (0, 255, 255), -1)
            cv2.putText(frame, f"ID:{t_id}", (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    # Hedef geçici kayıp uyarısı
    if manual_locked_id is not None and primary_target is None and last_known_center is not None:
        cv2.putText(frame, f"HEDEF KAYIP! BEKLENIYOR ({lost_counter}/{MAX_LOST_FRAMES})", 
                    (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
        cv2.circle(frame, last_known_center, 20, (0, 165, 255), 1)

    status_str = f"KILIT: ID {manual_locked_id}" if manual_locked_id else "OTO SECIM MODU"
    cv2.putText(frame, f"Toplam: {len(active_targets)} | {status_str}", (20, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

    cv2.imshow(WINDOW_NAME, frame)

    # Temiz Kapanış
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
        break

if arduino is not None:
    arduino.close()
cap.release()
cv2.destroyAllWindows()
cv2.waitKey(1)
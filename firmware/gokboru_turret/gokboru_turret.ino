/*
  Gokboru Hava Savunma Sistemi - Turret Firmware
  TEKNOFEST 2026 Celikkubbe Hava Savunma Sistemleri Yarismasi

  Protokol (bkz. ../../serial_link.py ve ../../README.md "Seri Protokol"):
    PC -> Arduino : "X{dx}Y{dy}F{fire}\n"
                     dx, dy : piksel hatasi (int, +/-), pan/tilt servosuna
                              kucuk bir adim olarak eklenir (P kontrolcu)
                     fire   : 0 veya 1 (1 = bir atimlik tetikleme istegi)
    Arduino -> PC : "ESTOP:0\n" / "ESTOP:1\n"
                     Acil durdur butonunun anlik durumu degisince gonderilir.

  ---------------------------------------------------------------------
  ONEMLI GUVENLIK NOTU (Sartname 4.2):
  Bu kod acil durdur butonunu okuyup hareket/ates komutlarini yazilim
  seviyesinde keser. AMA yarisma kurali gercek kesmenin DONANIMDA
  olmasini sart kosuyor: e-stop butonu, motor/tetik gucunu dogrudan
  (rolenin BESLEME hattinda, mikrodenetleyiciden BAGIMSIZ) kesecek
  sekilde kablolanmali. Yani PIN_ESTOP'a bagli olan bu yazilimsal kontrol
  ikinci bir guvenlik katmanidir; birincil kesme butonun kendisi + guc
  devresi olmalidir (orn. buton, motor surucu ve ates rolesinin ortak
  besleme hattinda seri olarak baglanir).
  ---------------------------------------------------------------------
*/

#include <Servo.h>
#include <stdlib.h>   // atoi
#include <string.h>   // strchr

// ---- Pin tanimlari (kendi devrenize gore guncelleyin) ----
const uint8_t PIN_SERVO_PAN  = 9;    // yatay eksen (yaw)
const uint8_t PIN_SERVO_TILT = 10;   // dikey eksen (pitch)
const uint8_t PIN_FIRE       = 7;    // role/MOSFET -> airsoft tetigi veya lazer
const uint8_t PIN_ESTOP      = 2;    // acil durdur butonu (INPUT_PULLUP, basili = LOW)

// ---- Yazilimsal aci siniri (ek emniyet katmani, Sartname 4.2) ----
// GERCEK hareket-yasak-alani SINIRLAMASI mekanik olmali (sistem fiziksel
// olarak bu sinirlarin disina donemeyecek sekilde kurulmali). Asagidaki
// degerler servo yanmasini/mekanizmaya carpmasini onlemek icin ek bir
// yazilim siniri, mekanik sinirin YERINE GECMEZ.
const int PAN_MIN_DEG  = 20;
const int PAN_MAX_DEG  = 160;
const int TILT_MIN_DEG = 60;
const int TILT_MAX_DEG = 150;

// ---- Kontrol ayarlari (saha testinde kalibre edin) ----
float GAIN = 0.03f;                          // piksel hatasi -> derece adimi
const unsigned long FIRE_PULSE_MS     = 150;  // tetik/lazer acik kalma suresi
const unsigned long FIRE_COOLDOWN_MS  = 400;  // iki ates arasi minimum sure

Servo panServo;
Servo tiltServo;

float panAngle  = 90.0f;
float tiltAngle = 90.0f;

bool estopActive   = false;
bool firing         = false;
unsigned long fireStartedAt = 0;
unsigned long lastFireAt    = 0;

void setup() {
  Serial.begin(115200);

  pinMode(PIN_FIRE, OUTPUT);
  digitalWrite(PIN_FIRE, LOW);

  pinMode(PIN_ESTOP, INPUT_PULLUP);

  panServo.attach(PIN_SERVO_PAN);
  tiltServo.attach(PIN_SERVO_TILT);
  panServo.write((int)panAngle);
  tiltServo.write((int)tiltAngle);

  // Baslangicta anlik estop durumunu PC'ye bildir.
  estopActive = (digitalRead(PIN_ESTOP) == LOW);
  Serial.print("ESTOP:");
  Serial.println(estopActive ? "1" : "0");
}

void loop() {
  updateEstop();
  readSerialCommands();
  updateFirePulse();
}

// --- Acil durdur: her dongude okunur, degisince PC'ye raporlanir ---
void updateEstop() {
  bool pressed = (digitalRead(PIN_ESTOP) == LOW);
  if (pressed != estopActive) {
    estopActive = pressed;
    if (estopActive) {
      // Ates aninda kesilir; hareket komutlari asagida zaten yok sayilacak.
      digitalWrite(PIN_FIRE, LOW);
      firing = false;
    }
    Serial.print("ESTOP:");
    Serial.println(estopActive ? "1" : "0");
  }
}

// --- Seri porttan satir satir komut okuma (blocking olmayan) ---
void readSerialCommands() {
  static char buf[32];
  static uint8_t idx = 0;

  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      buf[idx] = '\0';
      parseCommand(buf);
      idx = 0;
    } else if (c != '\r' && idx < sizeof(buf) - 1) {
      buf[idx++] = c;
    }
  }
}

// --- "X<dx>Y<dy>F<fire>" formatini ayristirir ---
void parseCommand(char *line) {
  char *xPos = strchr(line, 'X');
  char *yPos = strchr(line, 'Y');
  char *fPos = strchr(line, 'F');
  if (xPos == NULL || yPos == NULL || fPos == NULL) {
    return;  // bozuk/eksik satir, yok say
  }

  int dx = atoi(xPos + 1);
  int dy = atoi(yPos + 1);
  int fireReq = atoi(fPos + 1);

  if (estopActive) {
    return;  // acil durdurda hareket/ates komutlari tamamen yok sayilir
  }

  // P kontrolcu: hata sifira yaklasana kadar aciya kucuk adimlar ekler.
  // Python tarafi hedef deadzone icindeyken dx=dy=0 gonderdigi icin,
  // hedef ortalaninca aci kendiliginden sabitlenir.
  panAngle  = constrain(panAngle  + dx * GAIN, PAN_MIN_DEG, PAN_MAX_DEG);
  tiltAngle = constrain(tiltAngle - dy * GAIN, TILT_MIN_DEG, TILT_MAX_DEG);
  // NOT: dy, goruntude asagi yonde pozitif; servo yonunuz tersiyse
  // yukaridaki eksi isaretini kaldirin.

  panServo.write((int)panAngle);
  tiltServo.write((int)tiltAngle);

  if (fireReq == 1) {
    requestFire();
  }
}

// --- Ates isteğini debounce/cooldown ile tetikler ---
void requestFire() {
  if (estopActive || firing) {
    return;
  }
  unsigned long now = millis();
  if (now - lastFireAt < FIRE_COOLDOWN_MS) {
    return;
  }

  digitalWrite(PIN_FIRE, HIGH);
  firing = true;
  fireStartedAt = now;
  lastFireAt = now;
}

// --- Tetik/lazer pininin ates pulse suresi dolunca kapatilmasi ---
void updateFirePulse() {
  if (firing && (millis() - fireStartedAt >= FIRE_PULSE_MS)) {
    digitalWrite(PIN_FIRE, LOW);
    firing = false;
  }
}

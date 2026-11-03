// ESP32 firmware for the patient monitor
// Board: "ESP32 Dev Module"   Serial speed: 115200
//
// WIRING
//   GPIO 26 -> 220 ohm resistor -> LED (+), LED (-) -> GND
//   GPIO 27 -> passive buzzer (+), buzzer (-) -> GND
//
// COMMANDS from the laptop (USB serial):
//   'F' = fell down : LED ON + buzzer ON
//   'H' = abnormal movement : LED OFF + buzzer ON
//   'L' = person left : LED ON + buzzer OFF
//   'E' = person enter : LED OFF + buzzer OFF
//   '0' = normal/single movement/rest : all OFF
// The laptop repeats the command every ~1 s. If nothing arrives for 3 s,
// both LED and buzzer are switched OFF (safe state).

const int LED_PIN = 26;
const int BUZZER_PIN = 27;

const unsigned long LINK_TIMEOUT = 3000;   // ms without data = link lost
char mode = '0';
bool linkSeen = false;
unsigned long lastRx = 0;

void setup() {
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.begin(115200);

  // boot self-test: 2 quick LED blinks
  for (int i = 0; i < 2; i++) {
    digitalWrite(LED_PIN, HIGH); delay(150);
    digitalWrite(LED_PIN, LOW);  delay(150);
  }
  Serial.println("READY");
}

void loop() {
  unsigned long now = millis();

  while (Serial.available()) {
    char c = Serial.read();
    if (c == '0' || c == 'H' || c == 'F' || c == 'L' || c == 'E') {
      mode = c;
      lastRx = now;
      linkSeen = true;
      Serial.print("ACK:");
      Serial.println(c);
    }
  }

  // Link lost: safe state — both OFF
  if (linkSeen && now - lastRx > LINK_TIMEOUT) {
    digitalWrite(LED_PIN, LOW);
    noTone(BUZZER_PIN);
    return;
  }

  // FALL: LED ON + buzzer ON
  if (mode == 'F') {
    digitalWrite(LED_PIN, HIGH);
    tone(BUZZER_PIN, 2000);
  }
  // ABNORMAL MOVEMENT: LED OFF + buzzer ON
  else if (mode == 'H') {
    digitalWrite(LED_PIN, LOW);
    tone(BUZZER_PIN, 2000);
  }
  // PERSON LEFT: LED ON + buzzer OFF
  else if (mode == 'L') {
    digitalWrite(LED_PIN, HIGH);
    noTone(BUZZER_PIN);
  }
  // PERSON ENTER / NORMAL / SINGLE MOVEMENT / REST: both OFF
  else {
    digitalWrite(LED_PIN, LOW);
    noTone(BUZZER_PIN);
  }
}

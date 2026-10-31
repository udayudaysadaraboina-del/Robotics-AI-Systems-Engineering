#include <Arduino.h>

const int PIN_LED_PRIMARY = 25;
const int PIN_LED_ALT     = 13;  // Breadboard green wire column
const int PIN_BUZZER      = 26;
const int PIN_BOARD_LED   = 2;   // Kept LOW to prevent pink glow

const int PIN_BTN_P1 = 32;
const int PIN_BTN_P2 = 33;

const unsigned long COUNTDOWN_MS     = 5000;       // 5-second countdown
const unsigned long CUTOFF_WINDOW_MS = 7000UL;     // Strict 7,000 ms active window
const unsigned long DEBOUNCE_MS      = 5UL;        // 5 ms response filter

void setLedState(bool state) {
    pinMode(PIN_BOARD_LED, OUTPUT);
    digitalWrite(PIN_BOARD_LED, LOW);

    pinMode(PIN_LED_PRIMARY, OUTPUT);
    digitalWrite(PIN_LED_PRIMARY, state ? HIGH : LOW);

    pinMode(PIN_LED_ALT, OUTPUT);
    digitalWrite(PIN_LED_ALT, state ? HIGH : LOW);
}

void runReactionTrial(bool isLedMode) {
    setLedState(false);
    pinMode(PIN_BUZZER, OUTPUT);
    digitalWrite(PIN_BUZZER, LOW);
    pinMode(PIN_BTN_P1, INPUT_PULLUP);
    pinMode(PIN_BTN_P2, INPUT_PULLUP);

    // 1. Exact 5-second countdown
    Serial.println("STATUS:COUNTDOWN_5S");
    delay(COUNTDOWN_MS);

    bool p1Captured = false;
    bool p2Captured = false;
    unsigned long p1TouchMs = 0;
    unsigned long p2TouchMs = 0;
    float p1ReactionMs = -1.00;
    float p2ReactionMs = -1.00;

    // 2. Turn ON LED or Buzzer and record exact start timestamp (t_on)
    unsigned long stimulusStartMs = millis();
    if (isLedMode) {
        setLedState(true);
    } else {
        digitalWrite(PIN_BUZZER, HIGH);
    }

    Serial.println("STATUS:STIMULUS_ON");

    // 3. STRICT 7.000-SECOND ACTIVE WINDOW (Stable non-flickering loop)
    unsigned long lastTickMs = stimulusStartMs;
    while (millis() - stimulusStartMs < CUTOFF_WINDOW_MS) {
        unsigned long now = millis();

        // Maintain continuous static voltage
        if (isLedMode) {
            digitalWrite(PIN_LED_PRIMARY, HIGH);
            digitalWrite(PIN_LED_ALT, HIGH);
        } else {
            // Keep buzzer ringing
            digitalWrite(PIN_BUZZER, HIGH);
            delayMicroseconds(200);
            digitalWrite(PIN_BUZZER, LOW);
            delayMicroseconds(200);
        }

        // Check Serial triggers from Python ([A]/[1] for P1, [L]/[2] for P2)
        while (Serial.available() > 0) {
            char c = Serial.read();
            if (c == '1' && !p1Captured) {
                p1ReactionMs = (float)(millis() - stimulusStartMs);
                p1Captured = true;
                Serial.print("EVENT:P1_CLICKED:");
                Serial.println(p1ReactionMs, 2);
            } else if (c == '2' && !p2Captured) {
                p2ReactionMs = (float)(millis() - stimulusStartMs);
                p2Captured = true;
                Serial.print("EVENT:P2_CLICKED:");
                Serial.println(p2ReactionMs, 2);
            }
        }

        // Physical Push Button 1 (GPIO 32)
        if (!p1Captured) {
            if (digitalRead(PIN_BTN_P1) == LOW) {
                if (p1TouchMs == 0) p1TouchMs = now;
                else if (now - p1TouchMs >= DEBOUNCE_MS) {
                    p1ReactionMs = (float)(p1TouchMs - stimulusStartMs);
                    p1Captured = true;
                    Serial.print("EVENT:P1_CLICKED:");
                    Serial.println(p1ReactionMs, 2);
                }
            } else {
                p1TouchMs = 0;
            }
        }

        // Physical Push Button 2 (GPIO 33)
        if (!p2Captured) {
            if (digitalRead(PIN_BTN_P2) == LOW) {
                if (p2TouchMs == 0) p2TouchMs = now;
                else if (now - p2TouchMs >= DEBOUNCE_MS) {
                    p2ReactionMs = (float)(p2TouchMs - stimulusStartMs);
                    p2Captured = true;
                    Serial.print("EVENT:P2_CLICKED:");
                    Serial.println(p2ReactionMs, 2);
                }
            } else {
                p2TouchMs = 0;
            }
        }

        // 1-second progress ticks
        if (now - lastTickMs >= 1000) {
            lastTickMs = now;
            int secNum = (int)((now - stimulusStartMs) / 1000);
            if (secNum <= 7) {
                Serial.print("TICK:");
                Serial.println(secNum);
            }
        }
        delay(2);
    }

    // 4. Exactly 7.000 seconds completed -> Turn OFF LED and Buzzer
    setLedState(false);
    digitalWrite(PIN_BUZZER, LOW);
    Serial.println("STATUS:CUTOFF_7S_COMPLETE");

    Serial.print("RESULT:P1=");
    Serial.print(p1ReactionMs, 2);
    Serial.print(",P2=");
    Serial.print(p2ReactionMs, 2);
    Serial.println("");
    Serial.println("STATUS:READY");
}

void setup() {
    Serial.begin(115200);
    setLedState(false);
    pinMode(PIN_BUZZER, OUTPUT);
    digitalWrite(PIN_BUZZER, LOW);
    pinMode(PIN_BTN_P1, INPUT_PULLUP);
    pinMode(PIN_BTN_P2, INPUT_PULLUP);
    Serial.println("STATUS:READY");
}

void loop() {
    if (Serial.available() > 0) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();

        if (cmd == "CMD:TRIAL:LED") {
            runReactionTrial(true);
        } else if (cmd == "CMD:TRIAL:BUZZER") {
            runReactionTrial(false);
        }
    }
}

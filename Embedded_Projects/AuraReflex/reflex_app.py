import os
import sys
import time
import csv
import subprocess
import msvcrt
from datetime import datetime
import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
import numpy as np

PORT = "COM5"
BAUD = 115200
NUM_TRIALS = 3

PIO_PROJECT_DIR = os.path.join("Embedded_Projects", "AuraReflex", "Firmware_ESP32", "Firmware_ESP32")
MAIN_CPP_PATH = os.path.join(PIO_PROJECT_DIR, "src", "main.cpp")

# ==============================================================================
# FINAL ECE PROTOTYPE FIRMWARE (7s STABLE LED + BUZZER + SESSION EXPORTS)
# ==============================================================================
FIRMWARE_CPP_CODE = r"""#include <Arduino.h>

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
"""

def auto_flash_esp32():
    print("\n======================================================================")
    print("   AUTO-UPDATING main.cpp & FLASHING ULTIMATE FIRMWARE TO ESP32       ")
    print("======================================================================")
    os.makedirs(os.path.dirname(MAIN_CPP_PATH), exist_ok=True)
    with open(MAIN_CPP_PATH, "w", encoding="utf-8") as f:
        f.write(FIRMWARE_CPP_CODE)
    print(f"[OK] Saved firmware to: {MAIN_CPP_PATH}")
    print("[INFO] Uploading to ESP32 via PlatformIO...")
    subprocess.run(["pio", "run", "-d", PIO_PROJECT_DIR, "--target", "upload"], shell=True)
    print("[SUCCESS] ESP32 ready!\n")

auto_flash_esp32()

results = {"LED": {"P1": [], "P2": []}, "BUZZER": {"P1": [], "P2": []}}

ports = [p.device for p in serial.tools.list_ports.comports()]
ser = serial.Serial(PORT, BAUD, timeout=0.02)
time.sleep(2.0)
ser.reset_input_buffer()
print(f"[SUCCESS] Connected to ESP32 on {PORT}!\n")

def flush_keyboard():
    while msvcrt.kbhit():
        msvcrt.getch()

def run_single_trial(test_type, trial_num):
    cmd = b"CMD:TRIAL:LED\n" if test_type == "LED" else b"CMD:TRIAL:BUZZER\n"
    while True:
        print(f"\n--- [{test_type} EXPERIMENT] - TRIAL {trial_num} OF {NUM_TRIALS} ---")
        print(" -> Press Physical Push Buttons OR tap [A] for P1 and [L] for P2!")
        flush_keyboard()
        ser.reset_input_buffer()
        ser.write(cmd)

        p1_ms, p2_ms = None, None
        stimulus_active = False
        p1_done = False
        p2_done = False
        start_wait = time.time()

        while time.time() - start_wait < 22.0:
            if stimulus_active and msvcrt.kbhit():
                ch = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                if ch in ("a", "1", " ") and not p1_done:
                    ser.write(b"1")
                elif ch in ("l", "2", "\r") and not p2_done:
                    ser.write(b"2")

            if ser.in_waiting > 0:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                if line == "STATUS:COUNTDOWN_5S":
                    for sec in range(5, 0, -1):
                        print(f"  [Countdown] {sec}...", flush=True)
                        time.sleep(0.95)
                    flush_keyboard()
                elif line == "STATUS:STIMULUS_ON":
                    stimulus_active = True
                    print(f"\n  >>> {test_type} IS ON CONTINUOUSLY (7s)! PRESS BUTTONS NOW! <<<")
                elif line.startswith("EVENT:P1_CLICKED:"):
                    p1_done = True
                    print(f"  * P1 Reaction Time = {line.split(':')[-1]} ms!")
                elif line.startswith("EVENT:P2_CLICKED:"):
                    p2_done = True
                    print(f"  * P2 Reaction Time = {line.split(':')[-1]} ms!")
                elif line.startswith("TICK:"):
                    print(f"    [{test_type} ON... {line.split(':')[-1]}/7s]")
                elif line == "STATUS:CUTOFF_7S_COMPLETE":
                    stimulus_active = False
                    print(f"  >>> [7.0s Cutoff Reached] Turned OFF. <<<")
                elif line.startswith("RESULT:"):
                    parts = line.replace("RESULT:", "").split(",")
                    p1_ms = float(parts[0].split("=")[1])
                    p2_ms = float(parts[1].split("=")[1])
                elif line == "STATUS:READY" and p1_ms is not None:
                    break
            time.sleep(0.002)

        if p1_ms is None or p2_ms is None:
            continue
        if p1_ms <= 0 or p2_ms <= 0:
            retry = input("  Incomplete press. Press [Enter] to re-run (or 's' to skip): ").strip().lower()
            if retry != "s":
                continue
        print(f"  [OFFICIAL] P1: {p1_ms:.2f} ms | P2: {p2_ms:.2f} ms")
        return p1_ms, p2_ms

def compute_metrics(times):
    valid = [t for t in times if t > 0]
    if not valid: return 0.0, 0.0, 0.0
    return round(float(np.mean(valid)), 2), round(float(np.min(valid)), 2), round(float(np.std(valid)), 2)

def run_experiment(test_type):
    results[test_type]["P1"].clear()
    results[test_type]["P2"].clear()
    print(f"\n================ STARTING {test_type} EXPERIMENT ================")
    for trial in range(1, NUM_TRIALS + 1):
        if trial > 1: input(f"\nPress [Enter] for Trial {trial}...")
        p1, p2 = run_single_trial(test_type, trial)
        results[test_type]["P1"].append(p1)
        results[test_type]["P2"].append(p2)
    
    p1_avg, p1_best, p1_sd = compute_metrics(results[test_type]["P1"])
    p2_avg, p2_best, p2_sd = compute_metrics(results[test_type]["P2"])
    print(f"\n[{test_type} SUMMARY] P1 Avg: {p1_avg}ms | P2 Avg: {p2_avg}ms")

    if len(results["LED"]["P1"]) == NUM_TRIALS and len(results["BUZZER"]["P1"]) == NUM_TRIALS:
        display_graphs()

def save_csv_report(export_dir, ts):
    csv_file = os.path.join(export_dir, f"AuraReflex_ECE_Results_{ts}.csv")
    with open(csv_file, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Stimulus_Type", "Participant", "Trial_1_ms", "Trial_2_ms", "Trial_3_ms",
                         "Average_Time_ms", "Best_Time_ms", "Std_Dev_ms"])
        for mode in ["LED", "BUZZER"]:
            for p_code, p_name in [("P1", "Participant 1"), ("P2", "Participant 2")]:
                t_vals = results[mode][p_code]
                if len(t_vals) == NUM_TRIALS:
                    avg_v, best_v, sd_v = compute_metrics(t_vals)
                    writer.writerow([mode, p_name, t_vals[0], t_vals[1], t_vals[2], avg_v, best_v, sd_v])
    print(f"[SAVED] CSV Data exported to: {csv_file}")

def display_graphs():
    export_dir = os.path.join("Embedded_Projects", "AuraReflex", "Session_Exports")
    os.makedirs(export_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_csv_report(export_dir, ts)
    
    # Create 4-Panel Master ECE Dashboard (2x2 grid)
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    fig.suptitle("AuraReflex ECE Project: Real-Time Visual (LED) & Auditory (Buzzer) Reaction Analysis",
                 fontsize=13, fontweight="bold")
    trials_x = [1, 2, 3]

    # Panel 1: LED Line Plot
    ax1 = axes[0, 0]
    if len(results["LED"]["P1"]) == NUM_TRIALS:
        ax1.plot(trials_x, results["LED"]["P1"], marker="o", linewidth=2.2, color="#1f77b4", label="Participant 1 (LED)")
        ax1.plot(trials_x, results["LED"]["P2"], marker="s", linewidth=2.2, color="#ff7f0e", label="Participant 2 (LED)")
    ax1.set_title("1. LED Test (Visual) - 3-Trial Reaction Curve")
    ax1.set_xlabel("Trial Number")
    ax1.set_ylabel("Reaction Time (ms)")
    ax1.set_xticks(trials_x)
    ax1.grid(True, linestyle="--", alpha=0.6)
    ax1.legend()

    # Panel 2: Buzzer Line Plot
    ax2 = axes[0, 1]
    if len(results["BUZZER"]["P1"]) == NUM_TRIALS:
        ax2.plot(trials_x, results["BUZZER"]["P1"], marker="o", linewidth=2.2, color="#2ca02c", label="Participant 1 (Buzzer)")
        ax2.plot(trials_x, results["BUZZER"]["P2"], marker="s", linewidth=2.2, color="#d62728", label="Participant 2 (Buzzer)")
    ax2.set_title("2. Buzzer Test (Auditory) - 3-Trial Reaction Curve")
    ax2.set_xlabel("Trial Number")
    ax2.set_ylabel("Reaction Time (ms)")
    ax2.set_xticks(trials_x)
    ax2.grid(True, linestyle="--", alpha=0.6)
    ax2.legend()

    p1_led_avg, p1_led_best, _ = compute_metrics(results["LED"]["P1"])
    p2_led_avg, p2_led_best, _ = compute_metrics(results["LED"]["P2"])
    p1_buz_avg, p1_buz_best, _ = compute_metrics(results["BUZZER"]["P1"])
    p2_buz_avg, p2_buz_best, _ = compute_metrics(results["BUZZER"]["P2"])

    # Panel 3: Average Comparison Bar Chart
    ax3 = axes[1, 0]
    avg_cats = ["LED Average", "Buzzer Average"]
    p1_avgs = [p1_led_avg, p1_buz_avg]
    p2_avgs = [p2_led_avg, p2_buz_avg]
    x_pos = np.arange(len(avg_cats))
    bar_w = 0.32
    b1 = ax3.bar(x_pos - bar_w / 2, p1_avgs, bar_w, label="Participant 1", color="#1f77b4")
    b2 = ax3.bar(x_pos + bar_w / 2, p2_avgs, bar_w, label="Participant 2", color="#ff7f0e")
    ax3.set_title("3. Combined Average Response Time Comparison")
    ax3.set_ylabel("Average Reaction Time (ms)")
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(avg_cats)
    ax3.grid(True, axis="y", linestyle="--", alpha=0.6)
    ax3.legend()
    for bar in b1 + b2:
        h = bar.get_height()
        if h > 0:
            ax3.annotate(f"{h:.2f} ms", xy=(bar.get_x() + bar.get_width() / 2, h),
                         xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8)

    # Panel 4: Best Comparison Bar Chart
    ax4 = axes[1, 1]
    best_cats = ["LED Best", "Buzzer Best"]
    p1_bests = [p1_led_best, p1_buz_best]
    p2_bests = [p2_led_best, p2_buz_best]
    b3 = ax4.bar(x_pos - bar_w / 2, p1_bests, bar_w, label="Participant 1", color="#2ca02c")
    b4 = ax4.bar(x_pos + bar_w / 2, p2_bests, bar_w, label="Participant 2", color="#d62728")
    ax4.set_title("4. Combined Best (Fastest) Response Time Comparison")
    ax4.set_ylabel("Best Reaction Time (ms)")
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels(best_cats)
    ax4.grid(True, axis="y", linestyle="--", alpha=0.6)
    ax4.legend()
    for bar in b3 + b4:
        h = bar.get_height()
        if h > 0:
            ax4.annotate(f"{h:.2f} ms", xy=(bar.get_x() + bar.get_width() / 2, h),
                         xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    
    # Auto-maximize graph window to fit screen perfectly
    try:
        manager = plt.get_current_fig_manager()
        manager.window.state('zoomed')
    except Exception:
        pass

    img_file = os.path.join(export_dir, f"AuraReflex_ECE_Graphs_{ts}.png")
    plt.savefig(img_file, dpi=300)
    print(f"[SAVED] High-Resolution 4-Panel Chart saved to: {img_file}")
    plt.show()

def show_menu():
    print("\n================ AURA REFLEX ECE MENU ================")
    print("1. Start LED Reaction Test (5s Delay -> 7s Continuous Glow)")
    print("2. Start Buzzer Reaction Test (5s Delay -> 7s Continuous Sound)")
    print("3. Quit")
    print("======================================================")

while __name__ == "__main__":
    show_menu()
    choice = input("Enter choice (1-3): ").strip()
    if choice == "1": run_experiment("LED")
    elif choice == "2": run_experiment("BUZZER")
    elif choice == "3": ser.close(); break
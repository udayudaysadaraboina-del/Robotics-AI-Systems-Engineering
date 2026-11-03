"""
PATIENT MONITOR - USB CAMERA + YOLOv8-Pose + ESP32 LED/buzzer
================================================================
This ONE file uses the external USB/UVC camera connected to the laptop and contains everything for the laptop side, including the
ESP32 firmware (embedded below as SKETCH; export it with --export-sketch).

BEHAVIOUR
  PERSON FELL DOWN (visible in camera but outside the bed region) -> LED ON + BUZZER ON
  PERSON LEFT (absent from full camera for 5 sec)                  -> LED ON + BUZZER OFF
  PERSON ENTER (returns after being LEFT)                         -> LED OFF + BUZZER OFF
  SINGLE MOVEMENT (head/hands/shoulders/legs)                     -> LED OFF + BUZZER OFF
  ABNORMAL MOVEMENT (any 2 or more of 4 regions continuously > 1.5 sec)    -> LED OFF + BUZZER ON
  NORMAL / REST                                                   -> LED OFF + BUZZER OFF

ESP32 PINS (must match the firmware below)
  GPIO 26 -> LED   (through 220 ohm resistor to LED +, LED - to GND)
  GPIO 27 -> BUZZER (passive buzzer +, buzzer - to GND)

COMMANDS
  pip install ultralytics opencv-python numpy pyserial
  python patient_monitor_USB_camera_final.py                  run the monitor
  python patient_monitor_USB_camera_final.py --list-ports     show serial ports
  python patient_monitor_USB_camera_final.py --test-hardware  test LED + buzzer (no camera)
  python patient_monitor_USB_camera_final.py --export-sketch  write the ESP32 .ino file
  python patient_monitor_USB_camera_final.py --port COM5      choose port manually
  python patient_monitor_USB_camera_final.py --camera 1       use the external USB camera
  python patient_monitor_USB_camera_final.py --no-hardware    camera/AI only (no ESP32)

KEYS (in the video window)
  q = quit    r = re-select bed region    p = pause / resume monitoring
"""

import argparse
import ast
import datetime
import os
import sys
import time
from collections import deque

# ----------------------------- CONFIG ---------------------------------
MODEL_PATH = "yolov8n-pose.pt"   # auto-downloads on first run (needs internet)
BAUD = 115200                    # must match the ESP32 firmware
HEARTBEAT = 1.0                  # seconds between repeated commands
LED_ON_HAND_MOVEMENT = False     # hand/short movement never turns LED on

SMOOTHING_WINDOW = 7             # smoother body keypoints; reduces YOLO jitter
KP_CONF = 0.35                   # min keypoint confidence
ABSENT_SECONDS = 5.0             # not in region this long -> fell down
BLINK_INTERVAL = 0.5             # on-screen blink speed (medium)

ANALYSIS_WINDOW = 6.5            # seconds of recent movement history
MOVEMENT_LOOKBACK = 0.70          # compare current position with ~0.70 s ago
HEAD_THRESHOLD = 0.12             # torso-lengths: meaningful head displacement
HAND_THRESHOLD = 0.15             # torso-lengths: meaningful hand displacement
SHOULDER_THRESHOLD = 0.08         # torso-lengths: meaningful shoulder displacement
TORSO_THRESHOLD = 0.08            # torso-lengths: meaningful torso displacement
LEG_THRESHOLD = 0.12              # torso-lengths: meaningful leg displacement
REGION_SPAN_THRESHOLD = 0.055     # minimum recent movement range
MOVEMENT_MIN_POINTS = 8            # ignore decisions with too few samples
ABNORMAL_SECONDS = 1.6             # any 2 or more regions must move continuously for 1.6 sec
SAFE_IDLE_SECONDS = 0.8             # after movement stops, show SAFE briefly
REST_IDLE_SECONDS = 2.5             # then return to REST
RESTING_SPEED = 0.15
LYING_RATIO = 1.0

LOG_DIR = "alert_logs"
LOG_COOLDOWN = 5.0               # seconds between saved snapshots

NOSE, L_SH, R_SH, L_WR, R_WR, L_HIP, R_HIP = 0, 5, 6, 9, 10, 11, 12
SKELETON = [(5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11), (6, 12),
            (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)]

# ------------------------- ESP32 FIRMWARE -----------------------------
SKETCH = r"""// ESP32 firmware for the patient monitor
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
"""


def export_sketch():
    folder = "esp32_patient_monitor"
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "esp32_patient_monitor.ino")
    with open(path, "w", encoding="utf-8") as f:
        f.write(SKETCH)
    print("Sketch written to:", os.path.abspath(path))
    print("Open it in Arduino IDE, select 'ESP32 Dev Module' + your port, Upload.")


# ------------------------- ESP32 LINK ---------------------------------
try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None


def show_ports():
    if list_ports is None:
        print("pyserial missing: pip install pyserial")
        return
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found. Check the USB cable (must be a DATA cable)"
              " and install the CP210x / CH340 driver.")
    for p in ports:
        print(f"{p.device}: {p.description}")


class Hardware:
    """Serial link to the ESP32: sends codes + heartbeat, reads ACKs."""

    def __init__(self, port, enabled=True):
        self.port = port
        self.enabled = enabled and serial is not None
        self.ser = None
        self.last_code, self.last_send = None, 0.0
        self.last_ack = 0.0
        self.buf = b""
        self.next_retry = 0.0
        if enabled and serial is None:
            print("pyserial not installed -> hardware disabled "
                  "(pip install pyserial)")
        if self.enabled:
            self.connect()

    @staticmethod
    def find_port():
        keys = ("cp210", "ch340", "ch910", "silicon labs", "usb serial",
                "usb-serial", "esp32", "uart")
        for p in list_ports.comports():
            text = f"{p.description} {p.manufacturer or ''}".lower()
            if any(k in text for k in keys):
                return p.device
        return None

    def connect(self):
        port = self.port or self.find_port()
        if not port:
            print("ESP32 not found. Run --list-ports, then use --port COMx")
            return
        try:
            s = serial.Serial()
            s.port, s.baudrate, s.timeout = port, BAUD, 0
            s.dtr, s.rts = False, False      # avoid resetting the ESP32
            s.open()
            time.sleep(1.5)
            self.ser = s
            self.last_code = None
            print("ESP32 port opened:", port)
        except Exception as e:
            print(f"Could not open {port}: {e}")
            print("(Close Arduino Serial Monitor / other programs using it.)")
            self.ser = None

    def send(self, code, now):
        if not self.enabled:
            return
        if self.ser is None:
            if now >= self.next_retry:
                self.next_retry = now + 3.0
                self.connect()
            return
        if code != self.last_code or now - self.last_send >= HEARTBEAT:
            try:
                self.ser.write(code.encode())
                self.last_code, self.last_send = code, now
            except Exception:
                print("ESP32 link lost, retrying...")
                self.ser = None

    def poll(self, now):
        if self.ser is None:
            return
        try:
            n = self.ser.in_waiting
            if n:
                self.buf += self.ser.read(n)
        except Exception:
            self.ser = None
            return
        while b"\n" in self.buf:
            line, self.buf = self.buf.split(b"\n", 1)
            if line.decode(errors="ignore").strip().startswith("ACK:"):
                self.last_ack = now

    def connected(self, now):
        return self.ser is not None and now - self.last_ack < 3.0

    def close(self):
        if self.ser:
            try:
                self.ser.write(b"0")
                time.sleep(0.1)
                self.ser.close()
            except Exception:
                pass


def test_hardware(port):
    hw = Hardware(port)
    if hw.ser is None:
        print("Test aborted: ESP32 not connected.")
        return
    steps = (("F", "PERSON FELL DOWN: LED ON + BUZZER ON", 3),
             ("H", "ABNORMAL MOVEMENT: LED OFF + BUZZER ON", 3),
             ("L", "PERSON LEFT: LED ON + BUZZER OFF", 3),
             ("E", "PERSON ENTER: LED OFF + BUZZER OFF", 2),
             ("0", "normal/rest/single movement: everything OFF", 2))
    for code, text, secs in steps:
        print(f"Sending '{code}': {text}")
        end = time.time() + secs
        while time.time() < end:
            now = time.time()
            hw.send(code, now)
            hw.poll(now)
            time.sleep(0.05)
    ok = time.time() - hw.last_ack < 3.0
    print("ESP32 acknowledged commands:", "YES" if ok else
          "NO (check baud 115200 and that the sketch is uploaded)")
    hw.close()


# ----------------------------- HELPERS --------------------------------
def prune(dq, now, window):
    while dq and now - dq[0][0] > window:
        dq.popleft()


def count_reversals(values, min_step):
    """Zig-zag counter: returns (reversals, largest swing)."""
    if len(values) < 3:
        return 0, 0.0
    direction, extreme, reversals, max_swing = 0, values[0], 0, 0.0
    for v in values[1:]:
        if direction >= 0:
            if v > extreme:
                extreme = v
            elif extreme - v >= min_step:
                if direction == 1:
                    reversals += 1
                max_swing = max(max_swing, extreme - v)
                direction, extreme = -1, v
        if direction <= 0:
            if v < extreme:
                extreme = v
            elif v - extreme >= min_step:
                if direction == -1:
                    reversals += 1
                max_swing = max(max_swing, v - extreme)
                direction, extreme = 1, v
    return reversals, max_swing


def inside(pt, roi):
    x, y, w, h = roi
    return x <= pt[0] <= x + w and y <= pt[1] <= y + h


# ------------------------------ MAIN ----------------------------------
def run(port, camera, use_hw):
    import cv2
    import numpy as np
    from ultralytics import YOLO

    class Smoother:
        def __init__(self, n):
            self.buf = deque(maxlen=n)

        def add(self, kp):
            self.buf.append(kp)
            return np.mean(self.buf, axis=0)

        def reset(self):
            self.buf.clear()

    def open_camera(idx):
        # This project uses the external USB/UVC camera shown by the user.
        # On Windows the laptop's built-in camera is commonly index 0 and
        # the external USB camera is commonly index 1.
        cap = (cv2.VideoCapture(idx, cv2.CAP_DSHOW) if os.name == "nt"
               else cv2.VideoCapture(idx))
        if not cap.isOpened():
            return None

        # Request the camera's native/common 640x480 mode.
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        for _ in range(10):         # let the USB camera warm up
            cap.read()
        return cap

    def select_region(cap):
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("Cannot read from camera")
        print("Draw the BED region with the mouse, press ENTER/SPACE to confirm.")
        roi = cv2.selectROI("Select region", frame, showCrosshair=False)
        cv2.destroyWindow("Select region")
        if roi[2] == 0 or roi[3] == 0:
            h, w = frame.shape[:2]
            roi = (0, 0, w, h)
        print("Bed region set to:", roi)
        return roi

    def person_is_in_bed(kp, bbox, roi):
        """Robust bed-membership test. Do not use bbox center alone.

        A person whose body is substantially in the selected bed ROI is treated
        as being in bed even when the bounding-box center is outside the ROI.
        This prevents normal in-bed movement from being misclassified as FALL.
        """
        rx, ry, rw, rh = roi
        bx1, by1, bx2, by2 = map(float, bbox)
        bw = max(1.0, bx2 - bx1)
        bh = max(1.0, by2 - by1)

        # Strongest test: torso center (shoulders + hips) inside the bed ROI.
        def valid(i):
            return i < len(kp) and float(kp[i][2]) >= KP_CONF

        torso_points = []
        for i in (L_SH, R_SH, L_HIP, R_HIP):
            if valid(i):
                torso_points.append(kp[i][:2])
        if len(torso_points) >= 2:
            tc = np.mean(np.asarray(torso_points, dtype=float), axis=0)
            if inside((float(tc[0]), float(tc[1])), roi):
                return True

        # Secondary test: enough important body keypoints are inside the bed.
        important = [NOSE, L_SH, R_SH, L_HIP, R_HIP, L_WR, R_WR]
        visible = []
        inside_count = 0
        for i in important:
            if valid(i):
                visible.append(i)
                if inside((float(kp[i][0]), float(kp[i][1])), roi):
                    inside_count += 1
        if len(visible) >= 4 and inside_count / len(visible) >= 0.40:
            return True

        # Final safeguard for a lying person: require meaningful bbox overlap.
        ix1 = max(bx1, rx)
        iy1 = max(by1, ry)
        ix2 = min(bx2, rx + rw)
        iy2 = min(by2, ry + rh)
        intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        overlap = intersection / (bw * bh)
        return overlap >= 0.30

    def log_alert(frame, status):
        os.makedirs(LOG_DIR, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(LOG_DIR,
                            f"alert_{status.replace(' ', '_')}_{stamp}.jpg")
        cv2.imwrite(path, frame)
        print(f"[LOGGED] {stamp} - {status} -> {path}")

    cap = open_camera(camera)
    if cap is None:
        print(f"Cannot open camera {camera}. Try --camera 1, and close other "
              "apps using the webcam.")
        return
    model = YOLO(MODEL_PATH)
    roi = select_region(cap)
    hw = Hardware(port, enabled=use_hw)

    smoother = Smoother(SMOOTHING_WINDOW)
    ratio_hist = deque(maxlen=SMOOTHING_WINDOW)
    center_hist = deque()
    wrist_hist = {L_WR: deque(), R_WR: deque()}
    head_hist = deque()
    shoulder_hist = deque()
    torso_hist = deque()
    leg_hist = {0: deque(), 1: deque()}  # left leg, right leg
    abnormal_since = None
    last_movement_time = None
    had_short_movement = False
    last_seen = time.time()
    blink_on, last_toggle = True, time.time()
    last_log = 0.0
    paused = False
    fail_reads = 0
    ever_seen = False
    left_reported = False
    absent_since = None
    enter_until = 0.0
    ENTER_DISPLAY_SECONDS = 1.5
    PERSON_CONFIDENCE = 0.45
    RETURN_CONFIRM_FRAMES = 2
    return_confirm_count = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                fail_reads += 1
                if fail_reads > 30:
                    print("Camera stopped delivering frames.")
                    break
                time.sleep(0.03)
                continue
            fail_reads = 0
            now = time.time()

            # ---------------- paused ----------------
            if paused:
                hw.send("0", now)
                hw.poll(now)
                cv2.putText(frame, "PAUSED (press p to resume)", (20, 45),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 255), 3)
                cv2.imshow("Patient Monitor", frame)
                k = cv2.waitKey(1) & 0xFF
                if k == ord("q"):
                    break
                if k == ord("p"):
                    paused = False
                    last_seen = time.time()
                    smoother.reset()
                continue

            # ---------------- detection ----------------
            res = model(frame, verbose=False)[0]
            person, best_area, pbox = None, 0, None

            # Select the largest detected person ANYWHERE in the camera frame.
            # The bed ROI is checked only after the person is selected so that
            # a visible person outside the bed is reported as FALL, not LEFT.
            if res.keypoints is not None and len(res.boxes) > 0:
                kps = res.keypoints.data.cpu().numpy()
                boxes = res.boxes.xyxy.cpu().numpy()
                confs = res.boxes.conf.cpu().numpy()
                for kp_candidate, b, conf in zip(kps, boxes, confs):
                    # Ignore weak pose detections so a background false
                    # positive cannot cancel the PERSON LEFT timer.
                    if float(conf) < PERSON_CONFIDENCE:
                        continue
                    area = max(0.0, (b[2] - b[0]) * (b[3] - b[1]))
                    if area > best_area:
                        person, best_area, pbox = kp_candidate, area, b

            status, alert = "REST", False
            enter_event = False

            if person is None:
                # No person anywhere in the camera. This is NOT a fall.
                smoother.reset()
                center_hist.clear()
                for d in wrist_hist.values():
                    d.clear()
                head_hist.clear()
                shoulder_hist.clear()
                torso_hist.clear()
                for d in leg_hist.values():
                    d.clear()
                abnormal_since = None
                last_movement_time = None
                had_short_movement = False

                if ever_seen:
                    if absent_since is None:
                        absent_since = now
                        return_confirm_count = 0

                    absence_duration = now - absent_since
                    if absence_duration >= ABSENT_SECONDS:
                        # Confirmed absence from the FULL camera frame.
                        # This is PERSON LEFT, never PERSON FELL DOWN.
                        status, alert = "PERSON LEFT", True
                        left_reported = True
                    else:
                        status, alert = "CHECKING...", False
                else:
                    status, alert = "WAITING FOR PERSON", False
            else:
                # Person is visible somewhere in the FULL camera frame.
                # Require two consecutive valid detections before declaring a
                # return, preventing a one-frame YOLO false positive from
                # cancelling PERSON LEFT.
                ever_seen = True
                if left_reported:
                    return_confirm_count += 1
                    if return_confirm_count >= RETURN_CONFIRM_FRAMES:
                        left_reported = False
                        absent_since = None
                        return_confirm_count = 0
                        enter_until = now + ENTER_DISPLAY_SECONDS
                    else:
                        status, alert = "PERSON LEFT", True
                        hw.send("L", now)
                        hw.poll(now)
                        cv2.putText(frame, "RETURN CHECK...", (20, 75),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
                        cv2.imshow("Patient Monitor", frame)
                        k = cv2.waitKey(1) & 0xFF
                        if k == ord("q"):
                            break
                        if k == ord("p"):
                            paused = True
                        continue
                else:
                    return_confirm_count = 0

                absent_since = None
                was_left = (now < enter_until)

                # First confirmed frame after PERSON LEFT starts PERSON ENTER.
                if now < enter_until:
                    pass

                # IMPORTANT: do not use the bounding-box center alone.
                # During normal movement/lying, the bbox center can leave the
                # ROI even though the person's body is still in the bed.
                inside_bed = person_is_in_bed(person, pbox, roi)

                if now < enter_until:
                    # ENTER has priority for the short return event.
                    status, alert = "PERSON ENTER", False
                    smoother.reset()
                    center_hist.clear()
                    for d in wrist_hist.values():
                        d.clear()
                    head_hist.clear()
                    shoulder_hist.clear()
                    torso_hist.clear()
                    for d in leg_hist.values():
                        d.clear()
                    abnormal_since = None
                    last_movement_time = None
                    had_short_movement = False
                elif not inside_bed:
                    # Visible but outside bed ROI = FALL.
                    status, alert = "PERSON FELL DOWN", True
                    smoother.reset()
                    center_hist.clear()
                    for d in wrist_hist.values():
                        d.clear()
                    head_hist.clear()
                    shoulder_hist.clear()
                    torso_hist.clear()
                    for d in leg_hist.values():
                        d.clear()
                    abnormal_since = None
                    last_movement_time = None
                    had_short_movement = False
                else:
                    # Person is visible and inside bed: perform movement analysis.
                    kp = smoother.add(person)

                    def ok_pt(i):
                        return i < len(kp) and kp[i][2] >= KP_CONF

                    bw, bh = pbox[2] - pbox[0], pbox[3] - pbox[1]
                    if ok_pt(L_SH) and ok_pt(R_SH) and ok_pt(L_HIP) and ok_pt(R_HIP):
                        sh = (kp[L_SH][:2] + kp[R_SH][:2]) / 2
                        hp = (kp[L_HIP][:2] + kp[R_HIP][:2]) / 2
                        torso = max(np.linalg.norm(sh - hp), 0.25 * max(bw, bh))
                        center = (sh + hp) / 2
                    else:
                        sh = None
                        torso = 0.35 * max(bw, bh)
                        center = np.array([(pbox[0] + pbox[2]) / 2,
                                           (pbox[1] + pbox[3]) / 2])
                    torso = max(torso, 20.0)

                    center_hist.append((now, center[0] / torso, center[1] / torso))
                    prune(center_hist, now, ANALYSIS_WINDOW)

                    if ok_pt(NOSE):
                        head_rel = (kp[NOSE][:2] - center) / torso
                        head_hist.append((now, head_rel[0], head_rel[1]))
                    prune(head_hist, now, ANALYSIS_WINDOW)

                    for idx in (L_WR, R_WR):
                        if sh is not None and ok_pt(idx):
                            rel = (kp[idx][:2] - sh) / torso
                            wrist_hist[idx].append((now, rel[0], rel[1]))
                        prune(wrist_hist[idx], now, ANALYSIS_WINDOW)

                    if sh is not None:
                        sh_center = sh / torso
                        shoulder_hist.append((now, sh_center[0], sh_center[1]))
                    prune(shoulder_hist, now, ANALYSIS_WINDOW)

                    torso_rel = center / torso
                    torso_hist.append((now, torso_rel[0], torso_rel[1]))
                    prune(torso_hist, now, ANALYSIS_WINDOW)

                    leg_specs = ((0, L_HIP, 13, 15), (1, R_HIP, 14, 16))
                    for leg_id, hip_i, knee_i, ankle_i in leg_specs:
                        pts = []
                        for idx in (hip_i, knee_i, ankle_i):
                            if idx < len(kp) and ok_pt(idx):
                                pts.append(kp[idx][:2])
                        if len(pts) >= 2:
                            leg_center = np.mean(np.array(pts), axis=0)
                            leg_rel = (leg_center - center) / torso
                            leg_hist[leg_id].append((now, leg_rel[0], leg_rel[1]))
                        prune(leg_hist[leg_id], now, ANALYSIS_WINDOW)

                    def region_motion(hist, threshold):
                        if len(hist) < MOVEMENT_MIN_POINTS:
                            return False
                        arr = np.array([[p[1], p[2]] for p in hist], dtype=float)
                        times = np.array([p[0] for p in hist], dtype=float)
                        target = times[-1] - MOVEMENT_LOOKBACK
                        past_i = int(np.argmin(np.abs(times - target)))
                        if times[-1] - times[past_i] < MOVEMENT_LOOKBACK * 0.65:
                            return False
                        recent = arr[times >= times[-1] - 0.75]
                        if len(recent) < 4:
                            return False
                        displacement = float(np.linalg.norm(arr[-1] - arr[past_i]))
                        span = float(np.linalg.norm(np.ptp(recent, axis=0)))
                        return displacement >= threshold and span >= REGION_SPAN_THRESHOLD

                    head_active = region_motion(head_hist, HEAD_THRESHOLD)
                    hand_active = (
                        region_motion(wrist_hist[L_WR], HAND_THRESHOLD)
                        or region_motion(wrist_hist[R_WR], HAND_THRESHOLD)
                    )
                    shoulder_active = region_motion(shoulder_hist, SHOULDER_THRESHOLD)
                    torso_active = region_motion(torso_hist, TORSO_THRESHOLD)
                    leg_active = (
                        region_motion(leg_hist[0], LEG_THRESHOLD)
                        or region_motion(leg_hist[1], LEG_THRESHOLD)
                    )

                    # IMPORTANT: only these FOUR regions can participate in
                    # abnormal combinations. TORSO is deliberately excluded.
                    region_flags = {
                        "HEAD": head_active,
                        "HANDS": hand_active,
                        "SHOULDERS": shoulder_active,
                        "LEGS": leg_active,
                    }
                    active_names = [name for name, active in region_flags.items() if active]
                    active_regions = len(active_names)
                    any_movement = active_regions >= 1
                    two_regions = active_regions >= 2

                    if two_regions:
                        if abnormal_since is None:
                            abnormal_since = now
                        movement_duration = now - abnormal_since
                        last_movement_time = now

                        if movement_duration >= ABNORMAL_SECONDS:
                            status, alert = "ABNORMAL MOVEMENT", True
                        else:
                            status, alert = " + ".join(active_names) + " MOVEMENT", False
                    else:
                        abnormal_since = None
                        if any_movement:
                            last_movement_time = now
                            had_short_movement = True
                            status, alert = f"{active_names[0]} MOVEMENT", False
                        elif had_short_movement and last_movement_time is not None:
                            idle_for = now - last_movement_time
                            if idle_for <= REST_IDLE_SECONDS:
                                status, alert = "SAFE", False
                            else:
                                had_short_movement = False
                                status, alert = "REST", False
                        else:
                            status, alert = "REST", False

                    for a, b in SKELETON:
                        if a < len(kp) and b < len(kp) and kp[a][2] >= KP_CONF and kp[b][2] >= KP_CONF:
                            cv2.line(frame, tuple(kp[a][:2].astype(int)),
                                     tuple(kp[b][:2].astype(int)), (0, 255, 255), 2)
                    for p in kp:
                        if p[2] >= KP_CONF:
                            cv2.circle(frame, (int(p[0]), int(p[1])), 3, (0, 255, 0), -1)

            # ---------------- detection -> hardware ----------------
            if status == "PERSON FELL DOWN":
                code = "F"
            elif status == "ABNORMAL MOVEMENT":
                code = "H"
            elif status == "PERSON LEFT":
                code = "L"
            elif status == "PERSON ENTER":
                code = "E"
            else:
                code = "0"
            hw.send(code, now)
            hw.poll(now)

            if alert and now - last_log >= LOG_COOLDOWN:
                log_alert(frame, status)
                last_log = now

            # ---------------- on-screen display ----------------
            if alert:
                if now - last_toggle >= BLINK_INTERVAL:
                    blink_on, last_toggle = not blink_on, now
            else:
                blink_on, last_toggle = True, now

            x, y, w, h = roi
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 200, 0), 2)
            if alert and blink_on:
                cv2.rectangle(frame, (0, 0),
                              (frame.shape[1] - 1, frame.shape[0] - 1),
                              (0, 0, 255), 12)
            color = (0, 0, 255) if alert else (0, 200, 0)
            if alert and not blink_on:
                color = (0, 0, 120)
            cv2.putText(frame, status, (20, 45), cv2.FONT_HERSHEY_SIMPLEX,
                        1.2, color, 3)
            if person is not None:
                cv2.putText(
                    frame,
                    f"HEAD:{int(head_active)} HANDS:{int(hand_active)} "
                    f"SHOULDERS:{int(shoulder_active)} LEGS:{int(leg_active)} "
                    f"TORSO:{int(torso_active)} (not abnormal)",
                    (20, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
                    (255, 255, 255), 2
                )
                if 'active_names' in locals() and active_names:
                    cv2.putText(
                        frame,
                        "Active: " + " + ".join(active_names),
                        (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                        (255, 255, 255), 2
                    )
                if 'two_regions' in locals() and two_regions and abnormal_since is not None:
                    cv2.putText(
                        frame,
                        f"2-region timer: {max(0.0, now - abnormal_since):.1f}/{ABNORMAL_SECONDS:.1f}s",
                        (20, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                        (255, 255, 255), 2
                    )

            if use_hw:
                link = hw.connected(now)
                cv2.putText(frame,
                            "ESP32: CONNECTED" if link else "ESP32: NOT CONNECTED",
                            (20, frame.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 200, 0) if link else (0, 0, 255), 2)
                cv2.putText(frame,
                            f"LED:{'ON' if code in ('F', 'L') else 'OFF'}  "
                             f"BUZZER:{'ON' if code in ('F', 'H') else 'OFF'}",
                            (frame.shape[1] - 260, frame.shape[0] - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

            cv2.imshow("Patient Monitor", frame)
            k = cv2.waitKey(1) & 0xFF
            if k == ord("q"):
                break
            if k == ord("p"):
                paused = True
            if k == ord("r"):
                roi = select_region(cap)
                last_seen = time.time()
    finally:
        hw.close()               # sends '0' so LED/buzzer are switched off
        cap.release()
        cv2.destroyAllWindows()


def main():
    ap = argparse.ArgumentParser(description="Patient monitor (YOLOv8-Pose + ESP32)")
    ap.add_argument("--port", default=None, help="serial port, e.g. COM5")
    ap.add_argument("--camera", type=int, default=1, help="USB camera index (usually 1 when the laptop built-in camera is 0)")
    ap.add_argument("--list-ports", action="store_true")
    ap.add_argument("--test-hardware", action="store_true")
    ap.add_argument("--export-sketch", action="store_true")
    ap.add_argument("--no-hardware", action="store_true")
    a = ap.parse_args()

    if a.list_ports:
        show_ports()
    elif a.export_sketch:
        export_sketch()
    elif a.test_hardware:
        test_hardware(a.port)
    else:
        run(a.port, a.camera, not a.no_hardware)


if __name__ == "__main__":
    main()

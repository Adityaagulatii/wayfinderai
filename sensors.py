"""
tools/sensors.py — Accelerometer + Gyroscope + Pedometer for WayfinderAI
-------------------------------------------------------------------------
Reads live sensor data from your phone over WiFi using the
"Sensor Server" app (Android, free on Play Store).

Setup:
  1. Install "Sensor Server" on your Android phone
  2. Open app → tap Start → note the IP shown (e.g. 192.168.1.5:8080)
  3. Pass that IP to SensorHub(host="192.168.1.5")

Install:
  pip install websocket-client

Usage:
  from tools.sensors import SensorHub
  hub = SensorHub(host="192.168.1.5")
  hub.start()

  hub.is_stable()          # True if phone is steady (safe for OCR)
  hub.detected_turn()      # "left" | "right" | "none"
  hub.step_count           # total steps walked
  hub.distance_m           # estimated metres travelled
  hub.heading_deg          # cumulative yaw in degrees
  hub.accel                # {"x":..., "y":..., "z":...}
  hub.gyro                 # {"x":..., "y":..., "z":...}
  hub.connected            # True when receiving live data
  hub.snapshot()           # full dict — used by /sensors API endpoint
"""

import json
import math
import threading
import time
from collections import deque

# ── Tunable constants ─────────────────────────────────────────────────────────
STABILITY_THRESHOLD  = 0.10    # rad/s  — gyro magnitude below this = phone steady
TURN_THRESHOLD       = 0.55    # rad/s  — Z-axis above this = turning
TURN_CONFIRM_SECS    = 0.4     # seconds gyro must exceed threshold to confirm turn
STEP_THRESHOLD       = 1.2     # m/s²   — linear-accel spike above this = one step
STEP_COOLDOWN        = 0.35    # seconds between steps (prevents double-count)
STRIDE_LENGTH        = 0.75    # metres per step (average adult)
GRAVITY              = 9.81    # m/s²
HISTORY_SIZE         = 60      # rolling window per sensor


class SensorHub:
    """
    Manages accelerometer + gyroscope WebSocket streams from a phone.
    Derives pedometer from accelerometer peak-detection.
    All I/O runs in background daemon threads — never blocks the main app.
    Falls back gracefully when phone is not connected.
    """

    def __init__(self, host: str = "192.168.1.5", port: int = 8080):
        self.host = host
        self.port = port

        # Latest readings
        self.accel: dict = {"x": 0.0, "y": 0.0, "z": GRAVITY}
        self.gyro:  dict = {"x": 0.0, "y": 0.0, "z": 0.0}

        # Pedometer state
        self.step_count:   int   = 0
        self.distance_m:   float = 0.0
        self._last_step_t: float = 0.0
        self._prev_mag:    float = 0.0
        self._gravity_est: float = GRAVITY

        # Heading / turn state
        self.heading_deg:  float = 0.0
        self._last_turn:   str   = "none"
        self._turn_start:  float | None = None
        self._last_gyro_t: float = 0.0

        # Rolling histories
        self._accel_hist: deque = deque(maxlen=HISTORY_SIZE)
        self._gyro_hist:  deque = deque(maxlen=HISTORY_SIZE)

        self._lock    = threading.Lock()
        self._running = False

        try:
            import websocket as _ws
            self._ws    = _ws
            self._ws_ok = True
        except ImportError:
            print("[Sensors] websocket-client not installed — run: pip install websocket-client")
            self._ws_ok = False

    # ── Control ───────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start both sensor streams in background threads."""
        if not self._ws_ok:
            print("[Sensors] Cannot start — websocket-client missing.")
            return
        self._running = True
        threading.Thread(
            target=self._stream,
            args=("android.sensor.accelerometer", self._on_accel),
            daemon=True, name="accel-thread"
        ).start()
        threading.Thread(
            target=self._stream,
            args=("android.sensor.gyroscope", self._on_gyro),
            daemon=True, name="gyro-thread"
        ).start()
        print(f"[Sensors] Connecting to {self.host}:{self.port} ...")

    def stop(self) -> None:
        self._running = False

    # ── Public queries ────────────────────────────────────────────────────────

    def is_stable(self) -> bool:
        """True when phone is steady enough for reliable OCR."""
        with self._lock:
            g = self.gyro
        mag = math.sqrt(g["x"]**2 + g["y"]**2 + g["z"]**2)
        return mag < STABILITY_THRESHOLD

    def stability_score(self) -> float:
        """0.0 (very shaky) to 1.0 (perfectly steady)."""
        with self._lock:
            g = self.gyro
        mag = math.sqrt(g["x"]**2 + g["y"]**2 + g["z"]**2)
        return round(max(0.0, 1.0 - mag / (STABILITY_THRESHOLD * 8)), 2)

    def detected_turn(self) -> str:
        """
        Returns "left", "right", or "none".
        Resets after each read — each confirmed turn is reported exactly once.
        """
        with self._lock:
            turn = self._last_turn
            self._last_turn = "none"
        return turn

    def peek_turn(self) -> str:
        """Read current turn without resetting it."""
        with self._lock:
            return self._last_turn

    def heading_delta(self, seconds: float = 2.0) -> float:
        """Total yaw rotation in degrees over the last N seconds."""
        cutoff = time.time() - seconds
        with self._lock:
            recent = [r for r in self._gyro_hist if r["t"] > cutoff]
        if len(recent) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(recent)):
            dt    = recent[i]["t"] - recent[i - 1]["t"]
            avg_z = (recent[i]["z"] + recent[i - 1]["z"]) / 2
            total += math.degrees(avg_z * dt)
        return round(total, 1)

    def is_walking(self) -> bool:
        """True if a step was detected in the last 2 seconds."""
        return time.time() - self._last_step_t < 2.0

    @property
    def connected(self) -> bool:
        with self._lock:
            hist = list(self._accel_hist)
        return bool(hist) and (time.time() - hist[-1]["t"] < 2.0)

    def snapshot(self) -> dict:
        """Full sensor snapshot — used by the /sensors API endpoint."""
        with self._lock:
            a       = dict(self.accel)
            g       = dict(self.gyro)
            steps   = self.step_count
            dist    = round(self.distance_m, 2)
            heading = round(self.heading_deg, 1)
            turn    = self._last_turn
        return {
            "connected":       self.connected,
            "accelerometer":   a,
            "gyroscope":       g,
            "stable":          self.is_stable(),
            "stability_score": self.stability_score(),
            "walking":         self.is_walking(),
            "steps":           steps,
            "distance_m":      dist,
            "heading_deg":     heading,
            "turn":            turn,
        }

    # ── WebSocket stream worker ───────────────────────────────────────────────

    def _stream(self, sensor_type: str, on_msg) -> None:
        url = (f"ws://{self.host}:{self.port}"
               f"/sensor/connect?type={sensor_type}")
        label = sensor_type.split(".")[-1]
        while self._running:
            try:
                ws = self._ws.WebSocketApp(
                    url,
                    on_message=lambda ws, msg: on_msg(msg),
                    on_open=lambda ws: print(f"[Sensors] {label} stream connected"),
                    on_error=lambda ws, e: None,
                    on_close=lambda ws, *a: None,
                )
                ws.run_forever(ping_interval=10)
            except Exception:
                pass
            if self._running:
                time.sleep(3)

    # ── Accelerometer → pedometer ─────────────────────────────────────────────

    def _on_accel(self, raw: str) -> None:
        try:
            vals = json.loads(raw).get("values", [0, 0, GRAVITY])
            now  = time.time()
            r    = {"x": vals[0], "y": vals[1], "z": vals[2], "t": now}
            with self._lock:
                self.accel = r
                self._accel_hist.append(r)
            self._detect_step(r, now)
        except Exception:
            pass

    def _detect_step(self, r: dict, now: float) -> None:
        """
        Peak-detection pedometer:
          1. Low-pass filter estimates gravity
          2. High-pass remainder = body motion
          3. Magnitude spike + cooldown = one step
        """
        alpha             = 0.8
        self._gravity_est = alpha * self._gravity_est + (1 - alpha) * r["z"]
        la_x = r["x"]
        la_y = r["y"]
        la_z = r["z"] - self._gravity_est
        mag  = math.sqrt(la_x**2 + la_y**2 + la_z**2)

        if (self._prev_mag < STEP_THRESHOLD <= mag
                and now - self._last_step_t > STEP_COOLDOWN):
            with self._lock:
                self.step_count  += 1
                self.distance_m  += STRIDE_LENGTH
                self._last_step_t = now
        self._prev_mag = mag

    # ── Gyroscope → turn detection + heading ─────────────────────────────────

    def _on_gyro(self, raw: str) -> None:
        try:
            vals = json.loads(raw).get("values", [0, 0, 0])
            now  = time.time()
            r    = {"x": vals[0], "y": vals[1], "z": vals[2], "t": now}
            with self._lock:
                self.gyro = r
                self._gyro_hist.append(r)
            if self._last_gyro_t > 0:
                dt = now - self._last_gyro_t
                with self._lock:
                    self.heading_deg += math.degrees(vals[2] * dt)
            self._last_gyro_t = now
            self._detect_turn(vals[2], now)
        except Exception:
            pass

    def _detect_turn(self, z: float, now: float) -> None:
        """Confirm a turn only when Z-axis exceeds threshold for TURN_CONFIRM_SECS."""
        if abs(z) > TURN_THRESHOLD:
            if self._turn_start is None:
                self._turn_start = now
            elif now - self._turn_start >= TURN_CONFIRM_SECS:
                direction = "left" if z > 0 else "right"
                with self._lock:
                    self._last_turn = direction
        else:
            self._turn_start = None

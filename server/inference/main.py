import ast, asyncio, json, logging, mmap, os, requests, socket, sqlite3, struct, subprocess, sys, threading, time
from pathlib import Path
from urllib.request import urlretrieve
import cv2, serial, uvicorn
import numpy as np
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from serial import SerialException
from ultralytics import YOLO

def _load_env() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        eq = line.find("=")
        if eq == -1:
            continue
        key = line[:eq].strip()
        if not key:
            continue
        value = line[eq + 1:].strip().strip("\"'")
        if key not in os.environ:
            os.environ[key] = value


_load_env()

SEG_MODEL_NAME = "yolo11n-seg.pt"
FIRE_WEIGHTS_URL = "firedetect-11s.pt"
WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
FIRE_WEIGHTS_PATH = WEIGHTS_DIR / "firedetect-11s.pt"
FINE_TUNED_OPENVINO_DIR = WEIGHTS_DIR / "fine-tuned_openvino_model"
FINE_TUNED_PT = WEIGHTS_DIR / "fine-tuned.pt"
LAST_PT = WEIGHTS_DIR / "last.pt"
PERSON_CLASS_ID = 0
FIRE_CLASS_ID_SINGLE = 80
FALLEN_ASPECT_RATIO = 1.2
SEG_CONF = 0.35
FIRE_CONF = 0.35
WEBCAM_INDEX = int(os.environ.get("WEBCAM_INDEX", "0"))
DISPLAY_WIDTH = int(os.environ.get("DISPLAY_WIDTH", "1920"))
DISPLAY_HEIGHT = int(os.environ.get("DISPLAY_HEIGHT", "1080"))
EDGE_IMGSZ = int(os.environ.get("EDGE_IMGSZ", "320"))
WINDOW_TITLE = "server-2 hazard detection (q to quit)"
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "9001"))
YOLO_RETRY_DELAY = float(os.environ.get("YOLO_RETRY_DELAY", "3"))
OPENVINO_DEVICE = os.environ.get("OPENVINO_DEVICE", "CPU")
ARDUINO_HOST = os.environ.get("ARDUINO_HOST", "127.0.0.1")
ARDUINO_PORT = int(os.environ.get("ARDUINO_PORT", "9100"))
ARDUINO_TIMEOUT = float(os.environ.get("ARDUINO_TIMEOUT", "2.0"))
SENSOR_PORT = os.environ.get("SENSOR_PORT", "COM12")
CONTROL_PORT = os.environ.get("CONTROL_PORT", "COM3")
SERIAL_BAUD = int(os.environ.get("SERIAL_BAUD", "9600"))
SERIAL_TIMEOUT = float(os.environ.get("SERIAL_TIMEOUT", "1.0"))
SERIAL_RETRY_DELAY = float(os.environ.get("SERIAL_RETRY_DELAY", "3"))

CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
CF_AUTH_TOKEN = os.environ.get("CF_AUTH_TOKEN", "")
CF_MODEL = os.environ.get("CF_MODEL", "@cf/meta/llama-3.1-8b-instruct")
LLM_INTERVAL_SEC = int(os.environ.get("LLM_INTERVAL_SEC", "30"))

DB_PATH = Path(__file__).resolve().parent / "sensor_data.db"
TEMP_SENSOR_FIELDS = ["front_temp", "left_temp", "right_temp", "rear_temp", "top_temp"]
TEMP_HISTORY_SEC = 3600
TEMP_STEP_SEC = 120

SHM_NAME = "yolo_frame_shm"
SHM_MAX_W = 1920
SHM_MAX_H = 1080
SHM_HEADER_SIZE = 16
SHM_DATA_SIZE = SHM_MAX_W * SHM_MAX_H * 4
SHM_TOTAL_SIZE = SHM_HEADER_SIZE + SHM_DATA_SIZE

_shm: mmap.mmap | None = None
_shm_seq: int = 0


def init_shm() -> None:
    global _shm
    try:
        _shm = mmap.mmap(-1, SHM_TOTAL_SIZE, tagname=SHM_NAME, access=mmap.ACCESS_WRITE)
        _shm[0:SHM_HEADER_SIZE] = b"\x00" * SHM_HEADER_SIZE
        log.info("shared memory created: %s (%d bytes)", SHM_NAME, SHM_TOTAL_SIZE)
    except Exception as exc:
        log.error("failed to create shared memory: %s", exc)


def write_frame_shm(frame_bgr: np.ndarray) -> None:
    global _shm, _shm_seq
    if _shm is None:
        return
    rgba = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGBA)
    h, w = rgba.shape[:2]
    if w > SHM_MAX_W or h > SHM_MAX_H:
        rgba = cv2.resize(rgba, (SHM_MAX_W, SHM_MAX_H))
        h, w = SHM_MAX_H, SHM_MAX_W
    stride = w * 4
    if not rgba.flags["C_CONTIGUOUS"]:
        rgba = np.ascontiguousarray(rgba)
    pixel_bytes = rgba.tobytes()
    _shm_seq = (_shm_seq + 1) & 0xFFFFFFFF
    _shm[SHM_HEADER_SIZE : SHM_HEADER_SIZE + len(pixel_bytes)] = pixel_bytes
    _shm[0:SHM_HEADER_SIZE] = struct.pack("<IIII", _shm_seq, w, h, stride)


def init_db() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS temp_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            sensor_id INTEGER NOT NULL,
            value REAL NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON temp_readings(ts)")
    conn.commit()
    conn.close()


def save_temp_to_db(data: dict, ts: float) -> None:
    rows = []
    for i, field in enumerate(TEMP_SENSOR_FIELDS):
        val = data.get(field)
        if val is not None:
            try:
                rows.append((ts, i, float(val)))
            except (TypeError, ValueError):
                pass
    if not rows:
        return
    conn = sqlite3.connect(str(DB_PATH))
    conn.executemany(
        "INSERT INTO temp_readings(ts, sensor_id, value) VALUES (?, ?, ?)", rows
    )
    conn.execute("DELETE FROM temp_readings WHERE ts < ?", (ts - TEMP_HISTORY_SEC,))
    conn.commit()
    conn.close()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
log = logging.getLogger("server-2")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_sensors_lock = threading.Lock()
_sensors_state: dict = {"data": None, "received_at": None, "raw": None}

_yolo_lock = threading.Lock()
_yolo_state: dict = {"detections": [], "updated_at": None}

_serial_conn: "serial.Serial | None" = None
_serial_write_lock = threading.Lock()

_llm_lock = threading.Lock()
_llm_state: dict = {"response": None, "updated_at": None}

# model_prompt for claude code (claude -p)
_SYSTEM_PROMPT = (
    "당신은 화재 현장 로봇의 실시간 상황 분석 AI입니다. "
    "센서 데이터와 YOLO 탐지 결과를 바탕으로 간결하고 명확한 상황 분석을 제공합니다. "
    "응답 형식:\n(인식) [감지 내용]\n(분석) [상황 판단]\n(조언) [권장 행동]"
)

_streaming_proc: subprocess.Popen | None = None

KEY_TO_CMD: dict[str, bytes] = {
    "w": b"f",
    "a": b"l",
    "s": b"b",
    "d": b"r",
    "x": b"s",
    "1": b"1",
    "2": b"2",
    "3": b"3",
    "4": b"4",
}


def send_serial_cmd(cmd: bytes) -> bool:
    for attempt in range(3):
        with _serial_write_lock:
            if _serial_conn is None or not _serial_conn.is_open:
                return False
            try:
                pending = _serial_conn.in_waiting
                if pending:
                    incoming = _serial_conn.read(pending)
                    log.info(
                        "arduino readback: %s",
                        incoming.decode("utf-8", errors="replace").strip(),
                    )
                _serial_conn.write(cmd)
                return True
            except serial.SerialException:
                if attempt == 2:
                    raise
    return False


def build_context() -> str:
    with _yolo_lock:
        detections = list(_yolo_state.get("detections", []))
    with _sensors_lock:
        sensor_data = dict(_sensors_state.get("data") or {})
    det_str = ", ".join(f"{d['label']}({d['conf']:.2f})" for d in detections) or "없음"
    sensor_str = ", ".join(
        f"{k}: {v}" for k, v in sensor_data.items() if isinstance(v, (int, float))
    )
    return f"탐지: {det_str}\n센서: {sensor_str or '없음'}"


# def call_workers_ai(messages: list) -> str:
#     if not CF_ACCOUNT_ID or not CF_AUTH_TOKEN:
#         return "(설정 오류) CF_ACCOUNT_ID 또는 CF_AUTH_TOKEN이 설정되지 않았습니다."
#     url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{CF_MODEL}"
#     try:
#         resp = requests.post(
#             url,
#             headers={"Authorization": f"Bearer {CF_AUTH_TOKEN}"},
#             json={"messages": messages},
#             timeout=20,
#         )
#         resp.raise_for_status()
#         return resp.json().get("result", {}).get("response", "")
#     except Exception as exc:
#         log.error("workers ai call failed: %s", exc)
#         return ""


def llm_loop() -> None:
    while True:
        context = build_context()
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"현재 상황:\n{context}"},
        ]
        response = call_workers_ai(messages)
        if response:
            with _llm_lock:
                _llm_state["response"] = response
                _llm_state["updated_at"] = time.time()
        time.sleep(LLM_INTERVAL_SEC)


def extract_key(text: str):
    stripped = text.strip()
    if not stripped:
        return ""
    try:
        data = json.loads(stripped)
    except Exception:
        return stripped
    if isinstance(data, dict):
        for k in ("key", "Key", "k", "code", "keyCode", "type"):
            if k in data:
                return data[k]
        return data
    return data


CONTROL_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "text/plain": {
                "schema": {"type": "string", "example": "w"},
            },
            "application/json": {
                "schema": {
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"],
                    "example": {"key": "w"},
                },
            },
        },
    },
    "responses": {
        "200": {
            "description": "Key received",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "ok": {"type": "boolean"},
                            "key": {},
                        },
                    },
                    "example": {"ok": True, "key": "w"},
                }
            },
        }
    },
}


@app.post(
    "/api/control",
    summary="Receive a control key press",
    openapi_extra=CONTROL_OPENAPI,
)
async def control(request: Request):
    raw = await request.body()
    text = raw.decode("utf-8", errors="replace")
    key = extract_key(text)
    log.info("control key=%r body=%r", key, text)
    cmd = KEY_TO_CMD.get(str(key).lower())
    sent = False
    if cmd:
        loop = asyncio.get_running_loop()
        sent = await loop.run_in_executor(None, send_serial_cmd, cmd)
        if sent:
            log.info("serial cmd=%r sent for key=%r", cmd, key)
        else:
            log.warning("serial not available, cmd=%r dropped", cmd)
    return {"ok": True, "key": key, "sent": sent}


@app.websocket("/ws/control")
async def ws_control(websocket: WebSocket):
    await websocket.accept()
    log.info("ws control connected")
    loop = asyncio.get_running_loop()
    try:
        while True:
            text = await websocket.receive_text()
            key = extract_key(text)
            cmd = KEY_TO_CMD.get(str(key).lower())
            if not cmd:
                continue
            try:
                sent = await loop.run_in_executor(None, send_serial_cmd, cmd)
            except Exception as exc:
                log.warning("ws serial send failed: %s", exc)
                continue
            if not sent:
                log.warning("ws serial not available, cmd=%r dropped", cmd)
    except WebSocketDisconnect:
        log.info("ws control disconnected")


def query_arduino(metric: str, sensor_id: int) -> float:
    cmd = f"{metric}{sensor_id}\n".encode("ascii")
    with socket.create_connection(
        (ARDUINO_HOST, ARDUINO_PORT), timeout=ARDUINO_TIMEOUT
    ) as s:
        s.settimeout(ARDUINO_TIMEOUT)
        s.sendall(cmd)
        buf = bytearray()
        while not buf.endswith(b"\n") and len(buf) < 64:
            chunk = s.recv(64)
            if not chunk:
                break
            buf.extend(chunk)
    text = buf.decode("ascii", errors="replace").strip()
    return float(text)


async def read_metric(metric: str, sensor_id: int) -> float:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, query_arduino, metric, sensor_id)


@app.get(
    "/api/temp/{sensor_id}/temp",
    summary="Read DHT11 temperature from Arduino sensor",
)
async def get_temp(sensor_id: int):
    try:
        value = await read_metric("T", sensor_id)
    except Exception as exc:
        log.warning("temp query failed sensor=%s: %s", sensor_id, exc)
        raise HTTPException(status_code=502, detail=f"arduino error: {exc}")
    log.info("temp sensor=%s value=%s", sensor_id, value)
    return {"sensor_id": sensor_id, "metric": "temp", "unit": "C", "value": value}


@app.get(
    "/api/temp/{sensor_id}/humidity",
    summary="Read DHT11 humidity from Arduino sensor",
)
async def get_humidity(sensor_id: int):
    try:
        value = await read_metric("H", sensor_id)
    except Exception as exc:
        log.warning("humidity query failed sensor=%s: %s", sensor_id, exc)
        raise HTTPException(status_code=502, detail=f"arduino error: {exc}")
    log.info("humidity sensor=%s value=%s", sensor_id, value)
    return {
        "sensor_id": sensor_id,
        "metric": "humidity",
        "unit": "%",
        "value": value,
    }


@app.get("/api/temp/export", summary="Export all temperature readings from DB")
async def export_temp():
    def query():
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(
            "SELECT ts, sensor_id, value FROM temp_readings ORDER BY ts, sensor_id"
        ).fetchall()
        conn.close()
        return rows

    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(None, query)
    return {"rows": [{"ts": r[0], "sensor_id": r[1], "value": r[2]} for r in rows]}


@app.get("/api/temp/history", summary="Temperature history from SQLite (last 60 min)")
async def get_temp_history():
    now = time.time()
    start = now - TEMP_HISTORY_SEC
    n = TEMP_HISTORY_SEC // TEMP_STEP_SEC

    def query():
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(
            "SELECT ts, sensor_id, value FROM temp_readings WHERE ts >= ? ORDER BY ts",
            (start,),
        ).fetchall()
        conn.close()
        return rows

    loop = asyncio.get_running_loop()
    rows = await loop.run_in_executor(None, query)

    n_sensors = len(TEMP_SENSOR_FIELDS)
    sums = [[0.0] * n for _ in range(n_sensors)]
    counts = [[0] * n for _ in range(n_sensors)]
    for ts, sensor_id, value in rows:
        idx = int((ts - start) / TEMP_STEP_SEC)
        if 0 <= idx < n and 0 <= sensor_id < n_sensors:
            sums[sensor_id][idx] += value
            counts[sensor_id][idx] += 1

    readings = [
        [
            round(sums[si][mi] / counts[si][mi], 1) if counts[si][mi] > 0 else 0.0
            for mi in range(n)
        ]
        for si in range(n_sensors)
    ]
    minutes = [i * (TEMP_STEP_SEC // 60) for i in range(n)]
    return {"readings": readings, "minutes": minutes}


@app.get(
    "/api/sensors",
    summary="Latest sensor snapshot from Arduino serial",
)
async def get_sensors():
    with _sensors_lock:
        data = _sensors_state["data"]
    if data is None:
        raise HTTPException(status_code=503, detail="no sensor data yet")
    return data


@app.get("/api/yolos", summary="Latest YOLO detection results")
async def get_yolos():
    with _yolo_lock:
        state = dict(_yolo_state)
    if state["updated_at"] is None:
        raise HTTPException(status_code=503, detail="no yolo data yet")
    return state


@app.get("/api/llm", summary="Latest LLM situational analysis")
async def get_llm():
    with _llm_lock:
        state = dict(_llm_state)
    if state["response"] is None:
        raise HTTPException(status_code=503, detail="no llm data yet")
    return state


@app.post("/api/llm/ask", summary="Ask a question with current sensor context")
async def ask_llm(request: Request):
    body = await request.json()
    question = str(body.get("question", "")).strip()
    if not question:
        raise HTTPException(status_code=400, detail="question required")
    context = build_context()
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"현재 상황:\n{context}\n\n질문: {question}"},
    ]
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, call_workers_ai, messages)
    if not response:
        raise HTTPException(status_code=502, detail="llm call failed")
    return {"response": response}


def ensure_fire_weights() -> Path:
    if FIRE_WEIGHTS_PATH.exists():
        return FIRE_WEIGHTS_PATH
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading fire weights from {FIRE_WEIGHTS_URL}", flush=True)
    try:
        urlretrieve(FIRE_WEIGHTS_URL, FIRE_WEIGHTS_PATH)
    except Exception as exc:
        print(
            f"Failed to download fire weights: {exc}\n"
            f"Place a YOLO fire-detection .pt file at {FIRE_WEIGHTS_PATH} manually.",
            file=sys.stderr,
        )
        raise
    return FIRE_WEIGHTS_PATH


def class_name(names, idx: int) -> str:
    if isinstance(names, dict):
        return str(names.get(int(idx), idx))
    if isinstance(names, (list, tuple)) and 0 <= int(idx) < len(names):
        return str(names[int(idx)])
    return str(idx)


def is_fallen(box_xyxy: np.ndarray) -> bool:
    x1, y1, x2, y2 = box_xyxy
    h = y2 - y1
    if h <= 0:
        return False
    return ((x2 - x1) / h) > FALLEN_ASPECT_RATIO


def draw_label(img: np.ndarray, text: str, origin, color) -> None:
    x, y = origin
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    top = max(0, y - th - baseline - 4)
    cv2.rectangle(img, (x, top), (x + tw + 6, y), color, -1)
    cv2.putText(
        img,
        text,
        (x + 3, y - baseline - 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def annotate_dual(seg_result, fire_result) -> tuple[np.ndarray, list]:
    detections = []
    annotated = seg_result.plot()

    if seg_result.boxes is not None and len(seg_result.boxes) > 0:
        boxes = seg_result.boxes.xyxy.cpu().numpy()
        classes = seg_result.boxes.cls.cpu().numpy().astype(int)
        confs = seg_result.boxes.conf.cpu().numpy()
        for box, cls, conf in zip(boxes, classes, confs):
            cls_id = int(cls)
            x1, y1, x2, y2 = map(int, box)
            if cls_id == PERSON_CLASS_ID:
                fallen = is_fallen(box)
                if fallen:
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    draw_label(annotated, f"FALLEN {conf:.2f}", (x1, y1), (0, 0, 255))
                detections.append({
                    "label": "fallen" if fallen else "person",
                    "conf": round(float(conf), 3),
                })
            else:
                detections.append({
                    "label": class_name(seg_result.names, cls_id),
                    "conf": round(float(conf), 3),
                })

    if fire_result.boxes is not None and len(fire_result.boxes) > 0:
        boxes = fire_result.boxes.xyxy.cpu().numpy()
        classes = fire_result.boxes.cls.cpu().numpy().astype(int)
        confs = fire_result.boxes.conf.cpu().numpy()
        names = fire_result.names
        for box, cls, conf in zip(boxes, classes, confs):
            x1, y1, x2, y2 = map(int, box)
            name = class_name(names, cls)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 140, 255), 3)
            draw_label(annotated, f"{name.upper()} {conf:.2f}", (x1, y1), (0, 140, 255))
            detections.append({
                "label": name,
                "conf": round(float(conf), 3),
            })

    return annotated, detections


def annotate_single(result) -> tuple[np.ndarray, list]:
    detections = []
    if result.boxes is not None:
        for cls_id in result.boxes.cls.cpu().numpy().astype(int):
            if cls_id not in result.names:
                result.names[cls_id] = f"cls{cls_id}"
    annotated = result.plot()
    if result.boxes is None or len(result.boxes) == 0:
        return annotated, detections
    boxes = result.boxes.xyxy.cpu().numpy()
    classes = result.boxes.cls.cpu().numpy().astype(int)
    confs = result.boxes.conf.cpu().numpy()
    for box, cls, conf in zip(boxes, classes, confs):
        cls_id = int(cls)
        x1, y1, x2, y2 = map(int, box)
        if cls_id == PERSON_CLASS_ID:
            fallen = is_fallen(box)
            if fallen:
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 3)
                draw_label(annotated, f"FALLEN {conf:.2f}", (x1, y1), (0, 0, 255))
            detections.append({
                "label": "fallen" if fallen else "person",
                "conf": round(float(conf), 3),
            })
        elif cls_id == FIRE_CLASS_ID_SINGLE:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 140, 255), 3)
            draw_label(annotated, f"FIRE {conf:.2f}", (x1, y1), (0, 140, 255))
            detections.append({
                "label": "fire",
                "conf": round(float(conf), 3),
            })
        else:
            detections.append({
                "label": class_name(result.names, cls_id),
                "conf": round(float(conf), 3),
            })
    return annotated, detections


def resolve_single_weights() -> Path | None:
    if LAST_PT.exists():
        return LAST_PT
    if FINE_TUNED_OPENVINO_DIR.exists() and FINE_TUNED_OPENVINO_DIR.is_dir():
        return FINE_TUNED_OPENVINO_DIR
    if FINE_TUNED_PT.exists():
        return FINE_TUNED_PT
    return None


def run_yolo() -> int:
    if FINE_TUNED_PT.exists() and LAST_PT.exists():
        print(f"[dual-custom] {FINE_TUNED_PT.name} + {LAST_PT.name} (imgsz={EDGE_IMGSZ})")
        unified_model = None
        single_mode = False
        seg_model = YOLO(str(FINE_TUNED_PT))
        fire_model = YOLO(str(LAST_PT))
    else:
        single_weights = resolve_single_weights()
        single_mode = single_weights is not None
        if single_mode:
            kind = "OpenVINO" if single_weights.is_dir() else "PyTorch"
            print(f"[single-model/{kind}] {single_weights} (imgsz={EDGE_IMGSZ})")
            unified_model = YOLO(str(single_weights))
            seg_model = None
            fire_model = None
        else:
            print(
                f"[dual-model] {SEG_MODEL_NAME} + firedetect-11s "
                f"(place {FINE_TUNED_OPENVINO_DIR.name}/ or {FINE_TUNED_PT.name} "
                f"in {WEIGHTS_DIR} to switch to single-model mode)"
            )
            unified_model = None
            seg_model = YOLO(SEG_MODEL_NAME)
            fire_model = YOLO(str(ensure_fire_weights()))

    cap = cv2.VideoCapture(WEBCAM_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(WEBCAM_INDEX)
    if not cap.isOpened():
        print(f"Failed to open webcam index {WEBCAM_INDEX}", file=sys.stderr)
        return 1

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, DISPLAY_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, DISPLAY_HEIGHT)

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                print("Failed to read frame from webcam", file=sys.stderr)
                break
            if single_mode:
                result = unified_model.predict(
                    frame, conf=SEG_CONF, imgsz=EDGE_IMGSZ, verbose=False, device=OPENVINO_DEVICE
                )[0]
                annotated, detections = annotate_single(result)
            else:
                seg_result = seg_model.predict(
                    frame, conf=SEG_CONF, imgsz=EDGE_IMGSZ, verbose=False
                )[0]
                fire_result = fire_model.predict(
                    frame, conf=FIRE_CONF, imgsz=EDGE_IMGSZ, verbose=False
                )[0]
                annotated, detections = annotate_dual(seg_result, fire_result)
            with _yolo_lock:
                _yolo_state["detections"] = detections
                _yolo_state["updated_at"] = time.time()
            write_frame_shm(annotated)
    finally:
        cap.release()
    return 0


def yolo_supervisor() -> None:
    while True:
        try:
            run_yolo()
        except Exception as exc:
            log.exception("yolo crashed: %s", exc)
        log.info("yolo not running; retrying in %ss", YOLO_RETRY_DELAY)
        time.sleep(YOLO_RETRY_DELAY)


def parse_serial_line(text: str):
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        try:
            return json.loads(text)
        except Exception:
            return None


def serial_reader_loop() -> None:
    while True:
        try:
            ser = serial.Serial(SENSOR_PORT, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
            log.info("sensor serial opened %s @ %s", SENSOR_PORT, SERIAL_BAUD)
            try:
                while True:
                    raw = ser.readline()
                    if not raw:
                        continue
                    text = raw.decode("utf-8", errors="replace").strip()
                    if not text:
                        continue
                    data = parse_serial_line(text)
                    now = time.time()
                    with _sensors_lock:
                        _sensors_state["data"] = data if isinstance(data, dict) else None
                        _sensors_state["raw"] = text
                        _sensors_state["received_at"] = now
                    if isinstance(data, dict):
                        save_temp_to_db(data, now)
            finally:
                ser.close()
        except SerialException as exc:
            log.warning("sensor serial error on %s: %s", SENSOR_PORT, exc)
        except Exception as exc:
            log.exception("sensor serial crashed: %s", exc)
        log.info("retrying sensor serial in %ss", SERIAL_RETRY_DELAY)
        time.sleep(SERIAL_RETRY_DELAY)


def control_serial_loop() -> None:
    global _serial_conn
    while True:
        try:
            ser = serial.Serial(CONTROL_PORT, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
            with _serial_write_lock:
                _serial_conn = ser
            log.info("control serial opened %s @ %s", CONTROL_PORT, SERIAL_BAUD)
            try:
                while ser.is_open:
                    time.sleep(0.1)
            finally:
                with _serial_write_lock:
                    _serial_conn = None
                ser.close()
        except SerialException as exc:
            log.warning("control serial error on %s: %s", CONTROL_PORT, exc)
        except Exception as exc:
            log.exception("control serial crashed: %s", exc)
        log.info("retrying control serial in %ss", SERIAL_RETRY_DELAY)
        time.sleep(SERIAL_RETRY_DELAY)


def _streaming_launcher(bin_path: Path, cwd: Path) -> None:
    global _streaming_proc
    while True:
        if _shm_seq > 0:
            break
        time.sleep(0.5)
    _streaming_proc = subprocess.Popen([str(bin_path)], cwd=str(cwd))
    log.info("streaming started (pid=%d)", _streaming_proc.pid)


def main() -> int:
    init_db()
    init_shm()
    if FINE_TUNED_PT.exists() and LAST_PT.exists():
        log.info("model: dual-custom (%s + %s)", FINE_TUNED_PT.name, LAST_PT.name)
    else:
        single_weights = resolve_single_weights()
        if single_weights is not None:
            kind = "OpenVINO" if single_weights.is_dir() else "PyTorch"
            log.info("model: single-model/%s → %s", kind, single_weights)
        else:
            log.info("model: dual-model (%s + firedetect-11s)", SEG_MODEL_NAME)
    threading.Thread(target=yolo_supervisor, name="yolo", daemon=True).start()
    threading.Thread(target=serial_reader_loop, name="sensor-serial", daemon=True).start()
    threading.Thread(target=control_serial_loop, name="control-serial", daemon=True).start()
    threading.Thread(target=llm_loop, name="llm", daemon=True).start()
    _streaming_root = Path(__file__).resolve().parent.parent / "streaming"
    _streaming_bin = next(
        (
            p
            for p in [
                _streaming_root / "target" / "release" / "streaming.exe",
                _streaming_root / "target" / "debug" / "streaming.exe",
            ]
            if p.exists()
        ),
        None,
    )
    if _streaming_bin:
        threading.Thread(
            target=_streaming_launcher,
            args=(_streaming_bin, _streaming_root),
            name="streaming-launcher",
            daemon=True,
        ).start()
    else:
        log.warning("streaming binary not found, skipping")
    try:
        log.info("FastAPI listening on http://%s:%s", API_HOST, API_PORT)
        uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="info")
    finally:
        if _streaming_proc:
            _streaming_proc.terminate()
            try:
                _streaming_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _streaming_proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import time
import threading
import sys
import os
import queue
import requests
from flask import Flask, Response, jsonify, request
import cv2
import numpy as np
import tensorflow as tf
from decouple import config

API_KEY = config("API_KEY")


DEBUG = 1
# ---------------- GPIO/SPI IMPORTS -----------------
try:
    import RPi.GPIO as GPIO
except Exception:
    GPIO = None

try:
    import spidev
except Exception:
    spidev = None

# ---------------- MODEL -----------------
MODEL_PATH = "model.tflite"
LABELS_PATH = "labels.txt"
IMG_SIZE = 224

# Minimal model load (fail fast)
interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()
_input = interpreter.get_input_details()[0]['index']
_output = interpreter.get_output_details()[0]['index']

with open(LABELS_PATH, 'r') as f:
    labels = [l.strip() for l in f.readlines()]

# ---------------- DJANGO SERVER CONFIG -----------------
DJANGO_SERVER_URL = "https://zabravih.org"  # Your server
CONFIDENCE_THRESHOLD = 60.0  # Only send if confidence > 60%

# ---------------- GLOBALS -----------------
app = Flask(__name__)
current_frame = None
frame_lock = threading.Lock()
latest_result = {"category": "unknown", "confidence": 0.0, "timestamp": ""}
nfc_last_tag = {"uid": "", "text": "", "timestamp": "", "sent": False}

# add a global cam variable so endpoints can optionally change capture properties
cam = None

# Inference queue + interpreter lock
inference_queue = queue.Queue(maxsize=1)   # hold latest frame for inference (drop older)
interpreter_lock = threading.Lock()        # ensure single-threaded access to TFLite interpreter

# ---------------- THREADS / STREAMING CONFIG -----------------
# replace the static STREAM_W/STREAM_H with a mutable config + lock
STREAM_W, STREAM_H = 640, 480     # current target stream size (0 means native / no limit)
JPEG_Q = 40
CLASSIFY_INTERVAL = 5.0   # seconds — run classifier every 5 seconds

# Lock for updating stream resolution safely from API
config_lock = threading.Lock()
# If True, encoder will resize to STREAM_W x STREAM_H (unless width or height == 0)
limit_enabled = True

# ---------------- NFC CONFIG -----------------
NFC_ENABLED = str(os.environ.get("NFC_ENABLED", "1")).lower() not in ("0", "false", "no", "off")
NFC_SPI_BUS = int(os.environ.get("NFC_SPI_BUS", "0"))      # SPI bus 0
NFC_SPI_DEVICE = int(os.environ.get("NFC_SPI_DEVICE", "0"))  # CS on CE0 (GPIO 8)
NFC_RST_PIN = int(os.environ.get("NFC_RST_PIN", "22"))        # GPIO 22 for reset

# NFC reader instance
nfc_reader = None

def camera_init():
    """Initialize camera in background (non-blocking)."""
    global cam
    try:
        print("📹 Connecting to camera...")
        temp_cam = cv2.VideoCapture("rtsp://10.224.136.178:8080/h264.sdp")
        temp_cam.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000)
        if temp_cam.isOpened():
            temp_cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            temp_cam.set(cv2.CAP_PROP_FRAME_WIDTH, STREAM_W)
            temp_cam.set(cv2.CAP_PROP_FRAME_HEIGHT, STREAM_H)
            cam = temp_cam
            print("✅ Camera connected")
        else:
            print("⚠️ Camera connection failed", file=sys.stderr)
    except Exception as e:
        print(f"⚠️ Camera error: {e}", file=sys.stderr)

def frame_grabber(cam):
    """Continuously grab latest frame into current_frame."""
    global current_frame
    while True:
        if cam is None:
            time.sleep(0.1)
            continue
        ok, f = cam.read()
        if not ok or f is None:
            time.sleep(0.05)
            continue
        with frame_lock:
            current_frame = f

def classify_frame_local(frame):
    """Run TFLite inference on frame and update latest_result (protected by interpreter_lock)."""
    try:
        img = cv2.resize(frame, (IMG_SIZE, IMG_SIZE))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        inp = np.expand_dims(img, 0)
        # Ensure only one thread uses the interpreter at a time
        with interpreter_lock:
            interpreter.set_tensor(_input, inp)
            interpreter.invoke()
            preds = interpreter.get_tensor(_output)[0]
        idx = int(np.argmax(preds))
        label = labels[idx] if idx < len(labels) else "unknown"
        conf = float(preds[idx] * 100.0)
        latest_result.update({
            "category": label,
            "confidence": conf,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "all_predictions": {lab: float(p*100) for lab, p in zip(labels, preds)}
        })
    except Exception as e:
        # keep last result if inference fails
        print("Classification error:", e, file=sys.stderr)

def send_to_django(nfc_uid, category, confidence):
    """Send classification result to Django with API key authentication"""
    try:
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
        
        # Send NFC UID directly, not a hash!
        data = {
            'nfc_uid': str(nfc_uid),  # ← Send actual UID
            'category': category,
            'confidence': confidence
        }
        
        response = requests.post(
            f"{DJANGO_SERVER_URL}/api/update/",
            json=data,
            headers=headers,
            timeout=10,
            verify=True
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Sent to Django successfully!")
            print(f"   Bin ID: {result.get('trashcan_id', 'unknown')}")
            print(f"   NFC UID: {result.get('nfc_uid', 'unknown')}")
            print(f"   Device: {result.get('device', 'unknown')}")
            print(f"   Message: {result.get('message', 'OK')}")
            return True
        elif response.status_code == 401:
            print("❌ Authentication failed: Missing API key", file=sys.stderr)
            return False
        elif response.status_code == 403:
            print("❌ Access denied: Invalid or inactive API key", file=sys.stderr)
            return False
        elif response.status_code == 404:
            error_data = response.json()
            print(f"❌ {error_data.get('error', 'Bin not found')}", file=sys.stderr)
            print(f"   Hint: {error_data.get('hint', 'Register this NFC tag first')}", file=sys.stderr)
            return False
        else:
            print(f"❌ Server error: {response.status_code}", file=sys.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Failed to send: {e}", file=sys.stderr)
        return False

def classifier_loop():
    """Enqueue a snapshot for inference every CLASSIFY_INTERVAL seconds (non-blocking)."""
    next_run = time.time()
    while True:
        now = time.time()
        sleep_for = next_run - now
        if sleep_for > 0:
            time.sleep(sleep_for)

        # snapshot current frame
        with frame_lock:
            f = None if current_frame is None else current_frame.copy()

        if f is not None:
            # Try to put the frame into queue; if queue full, drop previous and replace with latest
            try:
                inference_queue.put_nowait(f)
            except queue.Full:
                try:
                    _ = inference_queue.get_nowait()  # drop older
                except Exception:
                    pass
                try:
                    inference_queue.put_nowait(f)
                except Exception:
                    # if still can't enqueue, skip this interval
                    pass

        # schedule next run (avoid drift)
        next_run += CLASSIFY_INTERVAL
        if next_run < time.time():
            next_run = time.time() + CLASSIFY_INTERVAL

def inference_worker():
    # try to lower process/thread priority so TF doesn't starve encoder/stream
    try:
        os.nice(10)
    except Exception:
        pass

    while True:
        try:
            frame = inference_queue.get()  # blocking
            if frame is None:
                inference_queue.task_done()
                continue
            classify_frame_local(frame)
            inference_queue.task_done()
        except Exception as e:
            # avoid worker dying silently
            print("Inference worker error:", e, file=sys.stderr)
            time.sleep(1)

def _handle_simulated_tag(uid, text):
    """Update nfc_last_tag and attempt server send using current AI classification."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    nfc_last_tag.update({"uid": str(uid), "text": str(text), "timestamp": timestamp, "sent": False})

    # Use current AI classification snapshot
    category = latest_result.get("category", "unknown")
    confidence = latest_result.get("confidence", 0.0)

    # Only attempt send if confidence high enough
    if confidence >= CONFIDENCE_THRESHOLD:
        try:
            # Send actual UID, not hash
            success = send_to_django(str(uid), category, confidence)  # ← Fixed!
        except Exception:
            success = False
        nfc_last_tag["sent"] = bool(success)
    else:
        nfc_last_tag["sent"] = False

    return nfc_last_tag

@app.route('/api/simulate_nfc', methods=['POST'])
def api_simulate_nfc():
    """
    Simulate an NFC tag scan:
    POST JSON or form: { "uid": "SIM-1", "text": "42" }
    """
    try:
        data = request.get_json(silent=True) or request.form or {}
        uid = data.get('uid') or data.get('UID') or "SIM-1"
        text = data.get('text') or data.get('tag_text') or ""
        result = _handle_simulated_tag(uid, text)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ---------------- WEB / STREAM -----------------
latest_jpeg = None
jpeg_lock = threading.Lock()
jpeg_condition = threading.Condition(jpeg_lock)

def encoder_loop():
    """Continuously encode the latest grabbed frame to JPEG and notify consumers."""
    global latest_jpeg
    while True:
        with frame_lock:
            f = None if current_frame is None else current_frame.copy()
        if f is None:
            time.sleep(0.03)
            continue

        # read current config under lock
        with config_lock:
            w, h, enabled = STREAM_W, STREAM_H, limit_enabled

        # apply optional resizing only if enabled and width/height > 0
        try:
            if enabled and w > 0 and h > 0 and (f.shape[1], f.shape[0]) != (w, h):
                f = cv2.resize(f, (w, h))
        except Exception:
            pass

        enc = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_Q]
        ok, buf = cv2.imencode('.jpg', f, enc)
        if not ok:
            time.sleep(0.01)
            continue

        jpeg_bytes = buf.tobytes()
        with jpeg_condition:
            latest_jpeg = jpeg_bytes
            jpeg_condition.notify_all()

        # small sleep to avoid starving CPU (tweak if needed)
        time.sleep(0.01)

def gen_frames():
    """Yield MJPEG frames using the latest pre-encoded JPEG produced by encoder_loop."""
    last = None
    while True:
        with jpeg_condition:
            if latest_jpeg is None:
                # wait until first JPEG available
                jpeg_condition.wait(timeout=1.0)
            # wait for a new jpeg if nothing changed
            while latest_jpeg is not None and latest_jpeg == last:
                jpeg_condition.wait(timeout=1.0)
            data = latest_jpeg
            last = data

        if data is None:
            # nothing ready yet
            time.sleep(0.02)
            continue

        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + data + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    # Enhanced HTML with NFC status
    return """
    <html><head><title>Trash Bin Classifier</title>
    <style>
        body{font-family:Arial;margin:20px;background:#f0f0f0} 
        .container{max-width:800px;margin:0 auto;background:#fff;padding:20px;border-radius:10px} 
        .controls{margin-top:10px}
        .nfc-status{background:#e3f2fd;padding:15px;margin:20px 0;border-radius:5px;border-left:4px solid #2196f3}
        .status-good{background:#e8f5e9;border-left-color:#4caf50}
        .status-warning{background:#fff3e0;border-left-color:#ff9800}
        .nfc-text{font-family:monospace;background:#f5f5f5;padding:5px;border-radius:3px;display:inline-block;margin-top:5px}
    </style>
    </head><body><div class="container">
    <h1>🗑️ Trash Bin Classifier</h1>
    <p><strong>Server:</strong> """ + DJANGO_SERVER_URL + """</p>
    <img src="/video_feed" style="width:100%;border-radius:5px">
    
    <div style="background:#e8f5e9;padding:15px;margin:20px 0;border-radius:5px">
      <p><strong>AI Status:</strong> <span id="category">Loading...</span></p>
      <p><strong>Confidence:</strong> <span id="confidence">-</span></p>
      <p><strong>Last Update:</strong> <span id="timestamp">-</span></p>
    </div>

    <div id="nfcStatus" class="nfc-status">
      <p><strong>🏷️ NFC Status:</strong> <span id="nfcText">Waiting for tag...</span></p>
      <p><strong>Tag UID:</strong> <span id="nfcUid">-</span></p>
      <p><strong>Tag Text:</strong> <span id="nfcTagText" class="nfc-text">-</span></p>
      <p><strong>Sent to Server:</strong> <span id="nfcSent">-</span></p>
    </div>

    <div class="controls">
      <label>Stream resolution:
        <select id="resSelect">
          <option value="0x0">Native (no limit)</option>
          <option value="1280x720">1280×720</option>
          <option value="640x480" selected>640×480</option>
          <option value="320x240">320×240</option>
          <option value="160x120">160×120</option>
        </select>
      </label>
      <label style="margin-left:12px"><input type="checkbox" id="limitToggle" checked> Limit resolution</label>
      <button onclick="applyRes()" style="margin-left:8px">Apply</button>
      <span id="resStatus" style="margin-left:12px"></span>
    </div>

    </div>
    <script>
      setInterval(()=>fetch('/api/status').then(r=>r.json()).then(d=>{
        document.getElementById('category').innerText=d.category;
        document.getElementById('confidence').innerText=(d.confidence||0).toFixed(1)+'%';
        document.getElementById('timestamp').innerText=d.timestamp||'-';
      }),1000);

      setInterval(()=>fetch('/api/nfc_status').then(r=>r.json()).then(d=>{
        const nfcDiv = document.getElementById('nfcStatus');
        if(d.uid && d.uid !== '') {
          document.getElementById('nfcUid').innerText = d.uid;
          document.getElementById('nfcTagText').innerText = d.text || '(empty)';
          document.getElementById('nfcSent').innerText = d.sent ? '✅ Yes' : '❌ No';
          if(d.sent) {
            nfcDiv.className = 'nfc-status status-good';
            document.getElementById('nfcText').innerText = 'Tag scanned & data sent! (' + d.timestamp + ')';
          } else {
            nfcDiv.className = 'nfc-status status-warning';
            document.getElementById('nfcText').innerText = 'Tag scanned (low confidence or error) - ' + d.timestamp;
          }
        } else {
          nfcDiv.className = 'nfc-status';
          document.getElementById('nfcText').innerText = 'Waiting for tag...';
          document.getElementById('nfcUid').innerText = '-';
          document.getElementById('nfcTagText').innerText = '-';
          document.getElementById('nfcSent').innerText = '-';
        }
      }),1000);

      function applyRes(){
        const sel = document.getElementById('resSelect').value;
        const toggle = document.getElementById('limitToggle').checked;
        let [w,h] = sel.split('x').map(s=>parseInt(s)||0);
        if (sel === '0x0') { w = 0; h = 0; }
        fetch('/api/set_resolution?width='+w+'&height='+h+'&limit_enabled='+toggle)
          .then(r=>r.json()).then(j=>{
            document.getElementById('resStatus').innerText = 'Applied: ' + j.width + 'x' + j.height + ' (limit ' + j.limit_enabled + ')';
          }).catch(e=>{
            document.getElementById('resStatus').innerText = 'Error';
          });
      }

      fetch('/api/get_resolution').then(r=>r.json()).then(j=>{
        document.getElementById('resStatus').innerText = j.width+'x'+j.height+' (limit '+j.limit_enabled+')';
        const sel = j.width && j.height ? (j.width+'x'+j.height) : '0x0';
        const select = document.getElementById('resSelect');
        for(let i=0;i<select.options.length;i++){
          if (select.options[i].value === sel) select.selectedIndex = i;
        }
        document.getElementById('limitToggle').checked = j.limit_enabled;
      });
    </script></body></html>
    """

@app.route('/api/status')
def api_status():
    return jsonify(latest_result)

@app.route('/api/nfc_status')
def api_nfc_status():
    """Return current NFC tag status"""
    return jsonify(nfc_last_tag)

@app.route('/api/classify')
def api_classify():
    with frame_lock:
        f = None if current_frame is None else current_frame.copy()
    if f is None:
        return jsonify({"error": "no frame"}), 500
    classify_frame_local(f)
    return jsonify(latest_result)

@app.route('/api/get_resolution')
def api_get_resolution():
    """Return current resolution config"""
    with config_lock:
        return jsonify({
            "width": STREAM_W,
            "height": STREAM_H,
            "limit_enabled": limit_enabled
        })

@app.route('/api/set_resolution', methods=['GET', 'POST'])
def api_set_resolution():
    global STREAM_W, STREAM_H, limit_enabled, cam
    try:
        with config_lock:
            cur_w, cur_h, cur_enabled = STREAM_W, STREAM_H, limit_enabled

        if request.method == 'POST':
            data = request.form or request.get_json() or {}
            w = int(data.get('width', request.args.get('width', cur_w)))
            h = int(data.get('height', request.args.get('height', cur_h)))
            enabled = data.get('limit_enabled', request.args.get('limit_enabled', None))
        else:
            w = int(request.args.get('width', cur_w))
            h = int(request.args.get('height', cur_h))
            enabled = request.args.get('limit_enabled', None)

        if enabled is None:
            new_enabled = bool(cur_enabled)
        else:
            new_enabled = str(enabled).lower() in ("1", "true", "yes", "on")

        with config_lock:
            STREAM_W = int(w)
            STREAM_H = int(h)
            limit_enabled = bool(new_enabled)
            try:
                if cam is not None and cam.isOpened():
                    if STREAM_W > 0:
                        cam.set(cv2.CAP_PROP_FRAME_WIDTH, STREAM_W)
                    if STREAM_H > 0:
                        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, STREAM_H)
            except Exception:
                pass

        return jsonify({"width": STREAM_W, "height": STREAM_H, "limit_enabled": limit_enabled})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ---------------- NFC USING MFRC522 LIBRARY -----------------
def init_nfc_reader():
    """Initialize the MFRC522 NFC reader."""
    global nfc_reader
    
    if not NFC_ENABLED:
        print("⚠️  NFC disabled via NFC_ENABLED")
        return None
        
    if not spidev:
        print("⚠️  spidev not available - NFC disabled")
        return None
        
    try:
        # Import the MFRC522 library you provided
        from MFRC522 import MFRC522
        print(f"✅ Initializing MFRC522 NFC reader (SPI bus {NFC_SPI_BUS}, device {NFC_SPI_DEVICE})")
        reader = MFRC522(bus=NFC_SPI_BUS, dev=NFC_SPI_DEVICE)
        print("✅ MFRC522 NFC reader initialized successfully")
        return reader
    except Exception as e:
        print(f"❌ Failed to initialize MFRC522 NFC reader: {e}")
        return None

def uid_to_string(uid):
    """Convert UID list to hex string."""
    return ''.join([format(byte, '02X') for byte in uid])

def nfc_reading_loop():
    """Main NFC reading loop using the MFRC522 library."""
    global nfc_reader
    
    if nfc_reader is None:
        print("❌ NFC reader not available - NFC loop exiting")
        return
        
    print("🔍 Starting NFC reading loop...")
    last_uid = None
    last_scan_time = 0
    
    while True:
        try:
            # Scan for cards
            (status, tag_type) = nfc_reader.MFRC522_Request(nfc_reader.PICC_REQIDL)
            
            if status == nfc_reader.MI_OK:
                # Card detected, get the UID
                (status, uid) = nfc_reader.MFRC522_SelectTagSN()
                
                if status == nfc_reader.MI_OK and uid:
                    uid_str = uid_to_string(uid)
                    
                    # Debounce - avoid reading the same card repeatedly
                    current_time = time.time()
                    if uid_str != last_uid or (current_time - last_scan_time) > 1.5:
                        last_uid = uid_str
                        last_scan_time = current_time
                        
                        print(f"🏷️  NFC Tag detected: {uid_str}")
                        # nfc_last_tag.update({"uid": uid_str, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")})
                        
                        # Try to read data from the tag (blocks 8, 9, 10)
                        tag_text = read_tag_data(nfc_reader, uid)
                        
                        # Process the tag
                        _handle_simulated_tag(uid_str, tag_text)
                    
                    # Halt the card to prepare for next read
                    nfc_reader.MFRC522_Request(nfc_reader.PICC_HALT)
            
            # Small delay to avoid excessive CPU usage
            time.sleep(0.1)
            
        except KeyboardInterrupt:
            print("🛑 NFC loop stopped by KeyboardInterrupt")
            break
        except Exception as e:
            print(f"⚠️  NFC reading error: {e}")
            time.sleep(0.5)

def read_tag_data(reader, uid):
    """Read text data from NFC tag blocks 8, 9, 10."""
    tag_text = ""
    try:
        # Default key for Mifare Classic (often 0xFFFFFFFFFFFF)
        key = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]
        
        # Blocks to read (8, 9, 10 - commonly used for data storage)
        blocks_to_read = [8, 9, 10]
        
        text_bytes = []
        
        for block_addr in blocks_to_read:
            # Authenticate with the block
            auth_status = reader.MFRC522_Auth(reader.PICC_AUTHENT1A, block_addr, key, uid)
            
            if auth_status == reader.MI_OK:
                # Read the block
                reader.MFRC522_Read(block_addr)
                # Note: The MFRC522_Read method in your library prints the data but doesn't return it
                # We'll need to modify this if we want to actually capture the data
                
                # For now, we'll just indicate that data was read but not capture it
                # since the library's Read method doesn't return the data
                pass
            else:
                if DEBUG:
                    print(f"  Authentication failed for block {block_addr}")
        
        # Stop crypto session
        reader.MFRC522_StopCrypto1()
        
        # Since we can't easily get the data from the Read method in this version,
        # we'll return an empty string for now
        # You could modify the MFRC522 library to return the read data
        
        return "Data read (see console for details)" if text_bytes else ""
        
    except Exception as e:
        if DEBUG:
            print(f"  Error reading tag data: {e}")
        return ""

# ---------------- MAIN -----------------
if __name__ == "__main__":
    print("=" * 70)
    print("🗑️  Trash Bin Classifier System Starting...")
    print("=" * 70)
    print(f"📡 Django Server: {DJANGO_SERVER_URL}")
    print(f"🎯 Confidence Threshold: {CONFIDENCE_THRESHOLD}%")
    
    # Initialize NFC reader
    nfc_reader = init_nfc_reader()
    nfc_status = "✅ Available" if nfc_reader else "❌ Not Available (use /api/simulate_nfc)"
    print(f"🏷️  NFC Reader: {nfc_status}")
    print("=" * 70)
    print()
    
    # assign to the module-level cam (with timeout to prevent hang)
    print("📹 Camera will be initialized in background...")
    cam = None  # Start with no camera, initialize in thread

    camera_init()  # Synchronous init for simplicity; can be threaded if needed

    # start threads
    # threading.Thread(target=camera_init, daemon=True).start()  # Initialize camera in background
    threading.Thread(target=frame_grabber, args=(cam,), daemon=True).start()
    threading.Thread(target=classifier_loop, daemon=True).start()
    threading.Thread(target=inference_worker, daemon=True).start()
    threading.Thread(target=encoder_loop, daemon=True).start()
    
    # Start NFC background thread if reader was initialized
    if nfc_reader is not None:
        print("✅ Starting NFC reading loop...")
        nfc_thread = threading.Thread(target=nfc_reading_loop, daemon=True)
        nfc_thread.start()

    print("🌐 Starting web server on http://0.0.0.0:5000")
    print("=" * 70)
    print()
    
    app.run(host="0.0.0.0", port=5000, threaded=True)
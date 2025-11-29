from flask import Flask, Response, jsonify
import cv2
import threading
import sys
import time
import numpy as np
import tensorflow as tf

# ---------------- NFC -----------------
# Safe import for RPi modules so the app doesn't crash on non-RPi environments
try:
    import RPi.GPIO as GPIO
    from MFRC522 import MFRC522
    reader = MFRC522()
except Exception:
    GPIO = None
    reader = None

def nfc_reader_loop():
    if reader is None:
        print("NFC reader not available on this system.")
        return
    print("NFC reader started. Waiting for tags...")
    while True:
        (status, TagType) = reader.MFRC522_Request(reader.PICC_REQIDL)
        if status == reader.MI_OK:
            print("Tag detected")

        (status, uid) = reader.MFRC522_Anticoll(1)
        if status == reader.MI_OK:
            tag_id = "".join("{:02X}".format(x) for x in uid)
            print("NFC Tag ID:", tag_id)
            time.sleep(1)

# ---------------- AI MODEL -----------------
MODEL_PATH = "model.tflite"
LABELS_PATH = "labels.txt"
IMG_SIZE = 224

print("📦 Loading TFLite model...")
interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

with open(LABELS_PATH, 'r') as f:
    labels = [line.strip() for line in f.readlines()]

print(f"✅ Model loaded! Categories: {labels}\n")

# Global variables for latest classification
latest_result = {
    "category": "unknown",
    "confidence": 0,
    "timestamp": "",
    "all_predictions": {}
}

def classify_frame(frame):
    """Classify a single frame"""
    try:
        # Resize to model input size
        image_resized = cv2.resize(frame, (IMG_SIZE, IMG_SIZE))
        
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image_resized, cv2.COLOR_BGR2RGB)
        
        # Normalize pixel values to 0-1
        image_normalized = image_rgb.astype(np.float32) / 255.0
        
        # Add batch dimension
        input_data = np.expand_dims(image_normalized, axis=0)
        
        # Run inference
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()
        
        # Get predictions
        predictions = interpreter.get_tensor(output_details[0]['index'])[0]
        
        # Get category with highest confidence
        predicted_idx = np.argmax(predictions)
        predicted_label = labels[predicted_idx]
        confidence = float(predictions[predicted_idx] * 100)
        
        # Store results
        global latest_result
        latest_result = {
            "category": predicted_label,
            "confidence": confidence,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "all_predictions": {label: float(prob*100) for label, prob in zip(labels, predictions)}
        }
        
        return predicted_label, confidence, predictions
        
    except Exception as e:
        print(f"❌ Classification error: {e}")
        return "error", 0, []

# ---------------- CAMERA + WEB -----------------
app = Flask(__name__)

# Global shared frame and lock
current_frame = None
frame_lock = threading.Lock()

# Streaming / performance settings
STREAM_WIDTH = 640       # set lower if you need less bandwidth (e.g. 480 or 360)
STREAM_HEIGHT = 480
JPEG_QUALITY = 70       # 0-100, lower => smaller images, faster
CLASSIFY_FPS = 10        # how often to run classification (times per second)

def frame_grabber_loop(cam):
    """Continuously read frames from cam and store the latest one."""
    global current_frame
    while True:
        if cam is None:
            time.sleep(0.1)
            continue
        success, frame = cam.read()
        if not success or frame is None:
            # slight backoff to avoid tight busy loop when camera fails
            time.sleep(0.1)
            continue
        with frame_lock:
            current_frame = frame.copy()

def gen_frames():
    """Generate frames for MJPEG stream (no per-frame classification)."""
    while True:
        with frame_lock:
            frame = None if current_frame is None else current_frame.copy()
        if frame is None:
            # no frame yet, wait a bit
            time.sleep(0.05)
            continue

        # Optionally downscale for faster encoding / lower bandwidth
        try:
            if (frame.shape[1], frame.shape[0]) != (STREAM_WIDTH, STREAM_HEIGHT):
                stream_frame = cv2.resize(frame, (STREAM_WIDTH, STREAM_HEIGHT))
            else:
                stream_frame = frame
        except Exception:
            stream_frame = frame

        # Encode with lower JPEG quality to speed up encoding and reduce size
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
        ret, buffer = cv2.imencode('.jpg', stream_frame, encode_params)
        if not ret:
            time.sleep(0.01)
            continue
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    return """
    <html>
    <head>
        <title>Trash Bin Classifier</title>
        <style>
            body { font-family: Arial; margin: 20px; background: #f0f0f0; }
            h1 { color: #333; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; }
            img { width: 100%; border-radius: 5px; }
            .result { background: #e8f5e9; padding: 15px; margin: 20px 0; border-radius: 5px; }
            .category { font-size: 24px; font-weight: bold; color: #2e7d32; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🗑️ Trash Bin Classifier</h1>
            <img src='/video_feed'>
            <div class="result">
                <p>Current Status: <span class="category" id="category">Loading...</span></p>
                <p>Confidence: <span id="confidence">-</span></p>
                <p>Last Update: <span id="timestamp">-</span></p>
            </div>
        </div>
        <script>
            setInterval(() => {
                fetch('/api/status')
                    .then(r => r.json())
                    .then(data => {
                        document.getElementById('category').innerText = data.category;
                        document.getElementById('confidence').innerText = data.confidence.toFixed(1) + '%';
                        document.getElementById('timestamp').innerText = data.timestamp;
                    });
            }, 1000);
        </script>
    </body>
    </html>
    """

@app.route('/api/status')
def api_status():
    """API endpoint to get latest classification"""
    return jsonify(latest_result)

@app.route('/api/classify')
def api_classify():
    """API endpoint to get single classification using latest grabbed frame snapshot"""
    # Use latest grabbed frame to avoid interfering with camera driver
    with frame_lock:
        frame = None if current_frame is None else current_frame.copy()
    if frame is None:
        return jsonify({"error": "No frame available yet"}), 500

    category, confidence, predictions = classify_frame(frame)

    # Save image
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"capture_{category}_{timestamp}.jpg"
    cv2.imwrite(filename, frame)

    return jsonify({
        "category": category,
        "confidence": confidence,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "image_saved": filename,
        "all_predictions": {label: float(prob*100) for label, prob in zip(labels, predictions)}
    })

# New: classifier thread that runs at CLASSIFY_FPS and updates latest_result
def classifier_loop(interval_sec):
    """Periodically classify the latest frame (runs in background)."""
    while True:
        with frame_lock:
            frame = None if current_frame is None else current_frame.copy()
        if frame is not None:
            try:
                classify_frame(frame)
            except Exception as e:
                print(f"Classifier loop error: {e}")
        time.sleep(interval_sec)

# ---------------- MAIN -----------------
if __name__ == "__main__":
    # Initialize camera here so we can check if it opened
    camera = cv2.VideoCapture("rtsp://10.134.123.154:8080/h264.sdp")
    if not camera.isOpened():
        print("❌ Camera failed to open. Check RTSP URL / network / camera.")
    else:
        # Set camera resolution if opened
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Start NFC reader in separate thread (if available)
    if reader is not None:
        t1 = threading.Thread(target=nfc_reader_loop, daemon=True)
        t1.start()

    # Start single frame grabber thread that fills current_frame
    t2 = threading.Thread(target=frame_grabber_loop, args=(camera,), daemon=True)
    t2.start()

    # Start classifier thread (reduced frequency)
    classify_interval = 1.0 / max(0.1, CLASSIFY_FPS)  # avoid division by zero
    t3 = threading.Thread(target=classifier_loop, args=(classify_interval,), daemon=True)
    t3.start()

    # Start web camera stream with classification
    print("🚀 Starting server at http://0.0.0.0:5000")
    print("   - Live stream: http://0.0.0.0:5000/")
    print("   - API status: http://0.0.0.0:5000/api/status")
    print("   - API classify: http://0.0.0.0:5000/api/classify\n")
    
    try:
        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        if 'camera' in globals() and camera is not None:
            camera.release()
        if GPIO is not None:
            GPIO.cleanup()
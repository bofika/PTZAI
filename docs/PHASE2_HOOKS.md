# Phase 2 Hooks: AI Tracking & Automation

IntelliTrack-Local is designed to be modular. Phase 2 (AI Tracking) can be added without rewriting the core.

## Architecture Integration

### 1. Frame Interception
Currently, `StreamManager` (in `backend/stream/manager.py`) uses FFmpeg to copy the RTSP stream to HLS.
To add object detection:
- **Option A (Sidecar)**: Launch a second generic Python process that consumes the RTSP stream using `opencv` (cv2.VideoCapture).
  - Perform detection on frames.
  - Calculate required PTZ movement.
  - Call the `CameraManager` or REST API to move the camera.
- **Option B (FFmpeg Filter)**: Use FFmpeg to output frames to a pipe/socket that a Python script reads.

### 2. Control Loop
The core control logic is in `backend/ptz/provider.py`.
- **Auto-Tracking**: Create a `TrackingService` class.
  - Input: Camera ID, Target Bounding Box (x, y, w, h).
  - Logic: PID Controller to center the bounding box.
  - Output: Calls `camera_provider.move(pan, tilt, zoom, speed)`.

### 3. API Extensions
- Add `POST /api/cameras/{id}/tracking/start`
- Add `POST /api/cameras/{id}/tracking/stop`
- Add settings for tracking sensitivity/ROI.

### Example Tracking Loop Code
```python
# Pseudo-code for Phase 2
import cv2
from backend.camera_manager import CameraManager

def track_camera(cam_id):
    cam = CameraManager().get_camera(cam_id)
    cap = cv2.VideoCapture(cam.rtsp_url)
    
    while True:
        ret, frame = cap.read()
        # ... AI Detection ...
        # error_x = target_x - center_x
        # pan_speed = pid_controller(error_x)
        
        cam.move(pan_speed, 0, 0, 1.0)
```

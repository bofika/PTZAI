# IntelliTrack-Local (Phase 1.5 - NDI Refactor)

A local-only Multi-Camera PTZ Control & Monitoring Web App.
**Primary Video Source**: NDI (Network Device Interface) -> MJPEG Preview.
**Fallback Source**: RTSP -> HLS.

## 🚀 Features
- **Video Grid**: 2x2 Low-Latency MJPEG Preview (NDI) or HLS (RTSP).
- **PTZ Control**: ONVIF Pan/Tilt/Zoom + Presets.
- **Source Discovery**: Auto-discover NDI sources on LAN.
- **Local Only**: No cloud dependencies.

## 📋 Prerequisites
1. **Python 3.9+**
2. **FFmpeg** (For RTSP fallback)
3. **NDI SDK**
   - You **MUST** have the NDI Runtime/SDK installed on your host machine.
   - [Download NDI SDK](https://ndi.video/tools/ndi-sdk/) (Free).

## 🛠️ Setup & Running

1. **Clone & Install Dependencies**
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
   *Note: `ndi-python` will fail to load if NDI Runtime is not installed on the OS.*

2. **Run the Application**
   ```bash
   # From project root
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Server: `http://localhost:8000`

3. **Access the UI**
   Open `http://localhost:8000`.

## 📸 Adding Cameras
1. Click **Add Camera**.
2. **NDI**: Select Source Type "NDI", then click "Scan". Select your camera.
3. **RTSP**: Select Source Type "RTSP", enter URL (e.g. `rtsp://...`).
4. **Control**: Enter ONVIF IP/Port/User/Pass to enable PTZ.

## ❓ Troubleshooting
- **NDI List Empty**: Ensure NDI Runtime is installed and you are on the same VLAN / mDNS works.
- **ImportError (ndi)**: `pip install ndi-python` and check OS libraries.
- **Video Loading forever**: 
  - NDI: Check if camera is sending.
  - RTSP: Check FFmpeg installation.

## 🔮 Phase 2 / Developer
- New `VideoSource` abstraction allows accessing raw frames:
  - `source.get_frame()` returns numpy array (BGR).
  - Perfect for OpenCV/AI Object Detection.

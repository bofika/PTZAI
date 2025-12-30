import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Initialize app
app = FastAPI(title="IntelliTrack-Local Backend")

# CORS (Allow all for local LAN MVP)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve paths relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HLS_DIR = os.path.join(BASE_DIR, "hls")
FRONTEND_DIR = os.path.join(BASE_DIR, "../frontend")

# Ensure HLS directory exists and mount it
os.makedirs(HLS_DIR, exist_ok=True)
app.mount("/hls", StaticFiles(directory=HLS_DIR), name="hls")

from .logger import logger
from .routers import cameras
from .camera_manager import CameraManager
from .video.preview_manager import PreviewManager
from fastapi.responses import StreamingResponse

# Include routers
app.include_router(cameras.router, prefix="/api")

@app.on_event("startup")
def startup_event():
    # Lazy load: Don't start streams here.
    logger.log("INFO", "Backend started (Lazy Preview Loading enabled)", "system", "startup")
    pass

@app.on_event("shutdown")
def shutdown_event():
    PreviewManager().stop_all()

@app.get("/api/video/{cam_id}/mjpeg")
def video_mjpeg(cam_id: str):
    """Serve MJPEG stream for a camera."""
    # Diagnostic
    if "<" in cam_id or "%3C" in cam_id:
        return {"error": "Invalid Camera ID"}, 400

    pm = PreviewManager()
    
    # Lazy Load Logic
    provider = pm.get_provider(cam_id)
    if not provider:
        # Try to find config and start it
        cm = CameraManager()
        conf = cm.config_manager.get_camera(cam_id)
        if conf:
            # Create (or get existing if race condition handled by PM guards)
            print(f"Lazy loading preview for {cam_id}")
            provider = pm.create_provider(conf)
        else:
            return {"error": "Camera config not found"}, 404

    if not provider or not hasattr(provider, 'generate_mjpeg'):
         return {"error": "Source not found or not MJPEG compatible"}, 404
    
    def frame_wrapper():
        # Pass through frames and update activity
        for chunk in provider.generate_mjpeg():
            # Update state (activity=True)
            pm.update_state(cam_id, activity=True)
            yield chunk

    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return StreamingResponse(frame_wrapper(), media_type="multipart/x-mixed-replace; boundary=frame", headers=headers)

@app.get("/api/healthz")
def health_check_simple():
    return {"status": "ok", "service": "IntelliTrack-Local"}

# Serve Frontend (Static) - Mount LAST
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

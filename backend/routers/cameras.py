from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from ..camera_manager import CameraManager
from ..video.preview_manager import PreviewManager
from ..config import CameraConfig, PreviewConfig

router = APIRouter()
camera_manager = CameraManager()
preview_manager = PreviewManager()

# --- Models ---
class PTZRequest(BaseModel):
    action: str
    pan: float = 0.0
    tilt: float = 0.0
    zoom: float = 0.0
    speed: float = 0.5

# --- Routes ---

@router.get("/ndi/sources")
def get_ndi_sources():
    """List available NDI sources."""
    return preview_manager.scan_ndi_sources()

@router.get("/cameras")
def get_cameras():
    # Return list of video sources
    cams = camera_manager.config_manager.get_cameras()
    result = []
    for c in cams:
        provider = preview_manager.get_provider(c["id"])
        c_out = c.copy()
        if provider:
             c_out["stream_url"] = provider.get_stream_url()
        else:
             c_out["stream_url"] = "" # Offline
        
        # Security: Remove password
        if "password" in c_out:
            del c_out["password"]
            
        result.append(c_out)
    return result

@router.post("/cameras")
def add_camera(config: CameraConfig):
    new_cam = config.dict()
    camera_manager.add_camera(new_cam)
    # Start preview provider
    preview_manager.create_provider(new_cam)
    return {"status": "added", "id": new_cam["id"]}

@router.delete("/cameras/{cam_id}")
def delete_camera(cam_id: str):
    preview_manager.remove_provider(cam_id)
    camera_manager.remove_camera(cam_id)
    return {"status": "removed"}

@router.post("/cameras/{cam_id}/ptz")
def ptz_control(cam_id: str, req: PTZRequest):
    provider = camera_manager.get_camera(cam_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Camera not found or not connected")

    success = False
    if req.action == "move":
        success = provider.move(req.pan, req.tilt, req.zoom, req.speed)
    elif req.action == "zoom":
         success = provider.move(0, 0, req.zoom, req.speed)
    elif req.action == "stop":
        success = provider.stop()
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    if not success:
        raise HTTPException(status_code=500, detail="PTZ command failed")
    
    return {"status": "ok"}

@router.get("/cameras/{cam_id}/presets")
def get_presets(cam_id: str):
    provider = camera_manager.get_camera(cam_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Camera not found")
    return provider.get_presets()

@router.post("/cameras/{cam_id}/presets/{preset_id}/goto")
def goto_preset(cam_id: str, preset_id: str):
    provider = camera_manager.get_camera(cam_id)
    if not provider:
         raise HTTPException(status_code=404, detail="Camera not found")
    if not provider.goto_preset(preset_id):
        raise HTTPException(status_code=500, detail="Failed to go to preset")
    return {"status": "ok"}

@router.post("/cameras/{cam_id}/presets/{preset_id}/set")
def set_preset(cam_id: str, preset_id: str):
    provider = camera_manager.get_camera(cam_id)
    if not provider:
         raise HTTPException(status_code=404, detail="Camera not found")
    if not provider.set_preset(preset_id):
        raise HTTPException(status_code=500, detail="Failed to set preset")
    return {"status": "ok"}

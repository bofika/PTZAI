from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import uuid
from ..camera_manager import CameraManager
from ..video.manager import SourceManager
from ..config import CameraConfig

router = APIRouter()
camera_manager = CameraManager()
source_manager = SourceManager()

# --- Models ---
class PTZRequest(BaseModel):
    action: str  # move, stop, zoom
    pan: float = 0.0
    tilt: float = 0.0
    zoom: float = 0.0
    speed: float = 0.5

class PresetRequest(BaseModel):
    name: str

# --- Routes ---

@router.get("/discovery/ndi")
def discover_ndi():
    """List available NDI sources"""
    return source_manager.scan_ndi()

@router.get("/cameras")
def get_cameras():
    # Return list of video sources
    cams = camera_manager.config_manager.get_cameras()
    result = []
    for c in cams:
        source = source_manager.get_source(c["id"])
        c_out = c.copy()
        if source:
             c_out["stream_url"] = source.get_stream_url()
        else:
             c_out["stream_url"] = "" # Offline
        del c_out["password"] # Security
        result.append(c_out)
    return result

@router.post("/cameras")
def add_camera(config: CameraConfig):
    new_cam = config.dict()
    camera_manager.add_camera(new_cam)
    # Start source
    source_manager.create_source(new_cam)
    return {"status": "added", "id": new_cam["id"]}

@router.delete("/cameras/{cam_id}")
def delete_camera(cam_id: str):
    source_manager.remove_source(cam_id)
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
         # treat as move with only zoom
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
def set_preset(cam_id: str, preset_id: str): # preset_id here is actually name for set
    # The API design in prompt said POST /api/cameras/{id}/presets/{preset_id}/set
    # Usually we POST to collection to create, but let's follow requirement.
    # If preset_id is the name we want to set:
    provider = camera_manager.get_camera(cam_id)
    if not provider:
         raise HTTPException(status_code=404, detail="Camera not found")
    if not provider.set_preset(preset_id):
        raise HTTPException(status_code=500, detail="Failed to set preset")
    return {"status": "ok"}

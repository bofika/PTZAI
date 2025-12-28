from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from ..camera_manager import CameraManager
from ..video.preview_manager import PreviewManager
from ..config import CameraConfig, PreviewConfig
from datetime import datetime

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

from ..logger import logger

@router.get("/logs")
def get_system_logs(limit: int = 50, camera_id: Optional[str] = None):
    return logger.get_logs(limit, camera_id)

@router.get("/health")
def health_check():
    cams = camera_manager.config_manager.get_cameras()
    total = len(cams)
    p_ok = 0
    p_err = 0
    c_ok = 0
    c_err = 0
    
    for c in cams:
        cid = c["id"]
        # Preview
        p_status = preview_manager.check_health(cid)
        if p_status == "ok": p_ok += 1
        else: p_err += 1
        
        # Control
        state = camera_manager.get_state(cid)
        c_status = state.get("control_status", "offline")
        if c_status == "ok": c_ok += 1
        else: c_err += 1

    status = "ok"
    if p_err > 0 or c_err > 0:
        status = "degraded"
        
    return {
        "status": status,
        "camera_count": total,
        "preview_ok": p_ok,
        "preview_error": p_err,
        "control_ok": c_ok,
        "control_error": c_err,
        "ts": datetime.now().isoformat()
    }

@router.get("/cameras")
def get_cameras():
    cams = camera_manager.config_manager.get_cameras()
    result = []
    for c in cams:
        cam_id = c["id"]
        
        # 1. Preview Status
        preview_status = preview_manager.check_health(cam_id)
        preview = preview_manager.get_provider(cam_id)
        stream_url = preview.get_stream_url() if preview else ""
        
        # 2. Control Status & Runtime State
        state = camera_manager.get_state(cam_id)
        control_status = state.get("control_status", "offline")
        last_seen = state.get("last_seen")
        last_error = state.get("last_error")

        # 3. Capabilities
        # (Assuming capabilities are static for now, or cached in the provider)
        caps = {}
        ptz_provider = camera_manager.get_camera(cam_id)
        if ptz_provider and hasattr(ptz_provider, "get_capabilities"):
            caps = ptz_provider.get_capabilities()
            
        # 4. Active Source
        active_source = "Unknown"
        p_cfg = c.get("preview", {})
        if p_cfg.get("type") == "ndi":
            active_source = p_cfg.get("ndi_source", "None")
        else:
            rtsp = p_cfg.get("rtsp_url", "")
            if "@" in rtsp:
                try:
                    parts = rtsp.split("@")
                    active_source = "rtsp://*****@" + parts[1]
                except: active_source = "rtsp://sanitized"
            else:
                active_source = rtsp

        # Build Object
        c_safe = c.copy()
        if "password" in c_safe: del c_safe["password"]
        
        c_safe.update({
            "control_status": control_status,
            "preview_status": preview_status,
            "stream_url": stream_url,
            "capabilities": caps,
            "active_preview_source": active_source,
            "last_error": last_error,
            "last_seen_ts": last_seen,
            "preview_type": p_cfg.get("type", "rtsp")
        })
        
        result.append(c_safe)
    return result

@router.post("/cameras/{cam_id}/preview/restart")
def restart_preview(cam_id: str):
    # Fetch config
    conf = camera_manager.config_manager.get_camera(cam_id) # Wait, config_manager.get_camera returns provider? No. 
    # ConfigManager doesn't have get_camera returning dict? let's check.
    # It has get_camera(id) returning DICT in config.py? No, wait. 
    # CameraManager has get_camera returning PROVIDER. 
    # ConfigManager has get_camera returning DICT in previous steps? 
    # Let's peek ConfigManager in config.py or just iterate.
    cams = camera_manager.config_manager.get_cameras()
    target_conf = next((c for c in cams if c["id"] == cam_id), None)
    
    if not target_conf:
        raise HTTPException(status_code=404, detail="Camera not found")
        
    preview_manager.restart_provider(cam_id, target_conf)
    return {"status": "restarted"}

@router.post("/cameras")
def add_camera(config: CameraConfig):
    new_cam = config.dict()
    camera_manager.add_camera(new_cam)
    # Start preview provider
    preview_manager.create_provider(new_cam)
    
    logger.log("INFO", f"Camera added: {new_cam['name']}", new_cam["id"], "camera.add")
    return {"status": "added", "id": new_cam["id"]}

@router.delete("/cameras/{cam_id}")
def delete_camera(cam_id: str):
    preview_manager.remove_provider(cam_id)
    camera_manager.remove_camera(cam_id)
    
    logger.log("INFO", "Camera deleted", cam_id, "camera.delete")
    return {"status": "removed"}

@router.put("/cameras/{cam_id}")
def update_camera(cam_id: str, config: CameraConfig):
    # Update config
    if config.id != cam_id:
         raise HTTPException(status_code=400, detail="ID mismatch")
    
    # Check if exists
    if not camera_manager.config_manager.get_camera(cam_id):
         raise HTTPException(status_code=404, detail="Camera not found")

    # Update storage
    camera_manager.config_manager.update_camera(cam_id, config.dict())
    
    # Restart preview (Stop old, Start new)
    preview_manager.remove_provider(cam_id)
    preview_manager.create_provider(config.dict())
    
    return {"status": "updated", "id": cam_id}

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

@router.post("/cameras/{cam_id}/presets/refresh")
def refresh_presets(cam_id: str):
    provider = camera_manager.get_camera(cam_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Camera not found")
        
    if hasattr(provider, 'force_refresh_presets'):
        return provider.force_refresh_presets()
    else:
        # Fallback if provider doesn't support forcing
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

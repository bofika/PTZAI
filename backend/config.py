import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

CONFIG_FILE = "config.json"

class PreviewConfig(BaseModel):
    type: str = "rtsp" # ndi | rtsp
    ndi_source: Optional[str] = None
    rtsp_url: Optional[str] = None 

class CameraConfig(BaseModel):
    id: str
    name: str
    ip: str
    onvif_port: int
    username: str
    password: str
    control_protocol: str = "onvif" # onvif | visca
    visca_port: Optional[int] = None
    preview: PreviewConfig = PreviewConfig()

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            # Try to load example if exists
            example_file = "backend/config.example.json"
            if os.path.exists(example_file):
                 try:
                    with open(example_file, "r") as f:
                        data = json.load(f)
                        self.config = self._validate_and_filter(data)
                 except:
                    self.config = {"cameras": []}
            else:
                self.config = {"cameras": []}
        else:
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.config = self._validate_and_filter(data)
            except (json.JSONDecodeError, OSError):
                print("Error loading config.json, using empty default.")
                self.config = {"cameras": []}

    def _validate_and_filter(self, data: Dict) -> Dict:
        """Filter out cameras with invalid IDs."""
        valid_cams = []
        for cam in data.get("cameras", []):
            cid = cam.get("id", "")
            # Check for invalid chars or placeholders
            if not cid or "<" in cid or ">" in cid or "%3C" in cid or "%3E" in cid or cid == "<cam_id>":
                print(f"WARNING: Skipping invalid camera ID from config: {cid}")
                continue
            
            # Migration logic (keep existing)
            if "preview" not in cam:
                src_type = cam.get("video_source_type", "rtsp")
                rtsp_url = cam.get("rtsp_url")
                ndi_src = cam.get("ndi_source_name")
                cam["preview"] = {
                    "type": src_type,
                    "rtsp_url": rtsp_url,
                    "ndi_source": ndi_src
                }
            
            valid_cams.append(cam)
        
        data["cameras"] = valid_cams
        return data

    def sanitize_persistence(self):
        """Force clean config.json by saving the currently loaded (filtered) config."""
        print("Sanitizing persistence layer...")
        self.save_config()
        return len(self.config.get("cameras", []))

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)

    def get_cameras(self) -> List[Dict[str, Any]]:
        return self.config.get("cameras", [])

    def add_camera(self, camera: Dict[str, Any]):
        self.config["cameras"].append(camera)
        self.save_config()

    def update_camera(self, camera_id: str, updates: Dict[str, Any]):
        for i, cam in enumerate(self.config["cameras"]):
            if cam["id"] == camera_id:
                # Merge updates
                self.config["cameras"][i].update(updates)
                self.save_config()
                return True
        return False

    def remove_camera(self, camera_id: str):
        self.config["cameras"] = [c for c in self.config["cameras"] if c["id"] != camera_id]
        self.save_config()

    def get_camera(self, camera_id: str) -> Optional[Dict[str, Any]]:
        for cam in self.config["cameras"]:
            if cam["id"] == camera_id:
                return cam
        return None

import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

CONFIG_FILE = "config.json"

class CameraConfig(BaseModel):
    id: str
    name: str
    ip: str
    onvif_port: int
    username: str
    password: str
    rtsp_url: Optional[str] = None # Optional now as NDI cameras might not have one
    control_protocol: str = "onvif"  # onvif | visca
    visca_port: Optional[int] = None
    video_source_type: str = "rtsp" # rtsp | ndi
    ndi_source_name: Optional[str] = None

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.load_config()
        return cls._instance

    def load_config(self):
        if not os.path.exists(CONFIG_FILE):
            self.config = {"cameras": []}
            self.save_config()
        else:
            try:
                with open(CONFIG_FILE, "r") as f:
                    self.config = json.load(f)
            except json.JSONDecodeError:
                self.config = {"cameras": []}

    def save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=4)

    def get_cameras(self) -> List[Dict[str, Any]]:
        return self.config.get("cameras", [])

    def add_camera(self, camera: Dict[str, Any]):
        self.config["cameras"].append(camera)
        self.save_config()

    def remove_camera(self, camera_id: str):
        self.config["cameras"] = [c for c in self.config["cameras"] if c["id"] != camera_id]
        self.save_config()

    def get_camera(self, camera_id: str) -> Optional[Dict[str, Any]]:
        for cam in self.config["cameras"]:
            if cam["id"] == camera_id:
                return cam
        return None

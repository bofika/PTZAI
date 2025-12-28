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
            self.config = {"cameras": []}
            self.save_config()
        else:
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    # Simple migration: ensure 'preview' exists
                    for cam in data.get("cameras", []):
                        if "preview" not in cam:
                            # Migrate old flat fields
                            src_type = cam.get("video_source_type", "rtsp")
                            rtsp_url = cam.get("rtsp_url")
                            ndi_src = cam.get("ndi_source_name")
                            cam["preview"] = {
                                "type": src_type,
                                "rtsp_url": rtsp_url,
                                "ndi_source": ndi_src
                            }
                    self.config = data
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

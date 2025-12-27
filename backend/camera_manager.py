from typing import Dict, Optional
from .config import ConfigManager
from .ptz.provider import PTZProvider
from .ptz.onvif import OnvifProvider  # We will create this next
# from .ptz.visca import ViscaProvider # Placeholder for phase 2

class CameraManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CameraManager, cls).__new__(cls)
            cls._instance.cameras: Dict[str, PTZProvider] = {}
            cls._instance.config_manager = ConfigManager()
            cls._instance.load_cameras()
        return cls._instance

    def load_cameras(self):
        """Initialize providers for all configured cameras."""
        configs = self.config_manager.get_cameras()
        for cam_config in configs:
            self._init_camera_provider(cam_config)

    def _init_camera_provider(self, cam_config: Dict):
        cam_id = cam_config["id"]
        protocol = cam_config.get("control_protocol", "onvif")
        
        provider = None
        if protocol == "onvif":
            provider = OnvifProvider(
                ip=cam_config["ip"],
                port=cam_config["onvif_port"],
                username=cam_config["username"],
                password=cam_config["password"]
            )
        # elif protocol == "visca":
        #    provider = ViscaProvider(...)
        
        if provider:
            # We treat the provider as the runtime interface for the camera
            self.cameras[cam_id] = provider
            # connect lazily or actively? Actively is better to catch errors early, 
            # but for robustness we might want to just store it and connect on first use or background.
            # For MVP, let's try to connect but not block hard.
            try:
                provider.connect()
            except Exception as e:
                print(f"Failed to connect to camera {cam_id}: {e}")

    def get_camera(self, cam_id: str) -> Optional[PTZProvider]:
        return self.cameras.get(cam_id)

    def add_camera(self, cam_config: Dict):
        """Add to config and initialize provider."""
        self.config_manager.add_camera(cam_config)
        self._init_camera_provider(cam_config)

    def remove_camera(self, cam_id: str):
        self.config_manager.remove_camera(cam_id)
        if cam_id in self.cameras:
            del self.cameras[cam_id]

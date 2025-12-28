from typing import Dict, Optional
from .config import ConfigManager
from .ptz.provider import PTZProvider
from .ptz.onvif import OnvifProvider  # We will create this next
# from .ptz.visca import ViscaProvider # Placeholder for phase 2

from datetime import datetime

class CameraManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CameraManager, cls).__new__(cls)
            cls._instance.cameras: Dict[str, PTZProvider] = {}
            cls._instance.states: Dict[str, Dict] = {} # Runtime State
            cls._instance.config_manager = ConfigManager()
            cls._instance.load_cameras()
        return cls._instance

    def load_cameras(self):
        """Initialize providers for all configured cameras."""
        configs = self.config_manager.get_cameras()
        for cam_config in configs:
            self._init_state(cam_config["id"])
            self._init_camera_provider(cam_config)

    def _init_state(self, cam_id: str):
        if cam_id not in self.states:
            self.states[cam_id] = {
                "last_seen": None,
                "last_error": None,
                "consecutive_failures": 0,
                "control_status": "offline" 
            }

    def update_status(self, cam_id: str, success: bool, error_msg: Optional[str] = None):
        if cam_id not in self.states:
            self._init_state(cam_id)
            
        state = self.states[cam_id]
        if success:
            state["last_seen"] = datetime.now().isoformat()
            state["last_error"] = None
            state["consecutive_failures"] = 0
            state["control_status"] = "ok"
        else:
            state["consecutive_failures"] += 1
            if error_msg:
                state["last_error"] = error_msg
            
            # Simple Debounce: 2 failures = offline/error
            if state["consecutive_failures"] >= 2:
                state["control_status"] = "error"

    def get_state(self, cam_id: str) -> Dict:
        return self.states.get(cam_id, {})

    def _init_camera_provider(self, cam_config: Dict):
        cam_id = cam_config["id"]
        protocol = cam_config.get("control_protocol", "onvif")
        
        provider = None
        if protocol == "onvif":
            try:
                provider = OnvifProvider(
                    ip=cam_config["ip"],
                    port=cam_config["onvif_port"],
                    username=cam_config["username"],
                    password=cam_config["password"]
                )
            except Exception as e:
                print(f"Failed to create ONVIF provider for {cam_id}: {e}")
                self.update_status(cam_id, False, str(e))
                return

        if provider:
            self.cameras[cam_id] = provider
            
            # Connect in background to avoid blocking startup
            import threading
            def _connect_bg():
                try:
                    # Log attempt?
                    pass 
                    if provider.connect():
                        self.update_status(cam_id, True)
                        # Also start preview? No, preview is handled by PreviewManager in main.py
                    else:
                         self.update_status(cam_id, False, "Connect failed")
                except Exception as e:
                    print(f"Failed to connect to camera {cam_id}: {e}")
                    self.update_status(cam_id, False, f"Connect failed: {e}")
            
            threading.Thread(target=_connect_bg, daemon=True).start()

    def get_camera(self, cam_id: str) -> Optional[PTZProvider]:
        return self.cameras.get(cam_id)

    def add_camera(self, cam_config: Dict):
        """Add to config and initialize provider."""
        self.config_manager.add_camera(cam_config)
        self._init_state(cam_config["id"])
        self._init_camera_provider(cam_config)

    def remove_camera(self, cam_id: str):
        self.config_manager.remove_camera(cam_id)
        if cam_id in self.cameras:
            del self.cameras[cam_id]
        if cam_id in self.states:
            del self.states[cam_id]

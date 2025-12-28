import time
from datetime import datetime, timedelta
from typing import List, Dict, Any
from .provider import PTZProvider
from onvif import ONVIFCamera

class OnvifProvider(PTZProvider):
    def __init__(self, ip, port, username, password):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.camera = None
        self.ptz = None
        self.media = None
        self.profile_token = None
        self.capabilities = {
            "continuous_move": True, 
            "absolute_move": False,
            "relative_move": True,
            "presets": True
        }
        
        # Debounce / Cache
        self.last_move = 0
        self.move_debounce_interval = 0.1 # 100ms
        self.presets_cache = []
        self.presets_cache_ts = 0
        self.presets_ttl = 30 # seconds

    def get_capabilities(self):
        return self.capabilities

    def connect(self) -> bool:
        try:
            # ... (existing connect logic)
            self.camera = ONVIFCamera(
                self.ip, self.port, self.username, self.password
            )
            # Create services
            self.media = self.camera.create_media_service()
            self.ptz = self.camera.create_ptz_service()

            # Get target profile
            profiles = self.media.GetProfiles()
            if not profiles:
                print(f"No profiles found for {self.ip}")
                return False
            
            self.profile_token = profiles[0].token
            return True
        except Exception as e:
            print(f"Error connecting to ONVIF camera {self.ip}: {e}")
            return False

    def move(self, pan: float, tilt: float, zoom: float, speed: float) -> bool:
        if not self.ptz or not self.profile_token:
            return False
            
        # Debounce
        now = time.time()
        if (now - self.last_move) < self.move_debounce_interval:
            # Skip rapid moves
            return True 
        self.last_move = now

        try:
            status = self.ptz.GetStatus({'ProfileToken': self.profile_token})
            
            request = self.ptz.create_type('ContinuousMove')
            request.ProfileToken = self.profile_token
            
            if request.Velocity is None:
                request.Velocity = self.ptz.create_type('PTZSpeed')
                
            # PanTilt
            if pan != 0 or tilt != 0:
                request.Velocity.PanTilt = self.ptz.create_type('Vector2D')
                request.Velocity.PanTilt.x = pan * speed
                request.Velocity.PanTilt.y = tilt * speed
                request.Velocity.PanTilt.space = 'http://www.onvif.org/ver10/tptz/PanTiltSpaces/VelocityGenericSpace'
            
            # Zoom
            if zoom != 0:
                request.Velocity.Zoom = self.ptz.create_type('Vector1D')
                request.Velocity.Zoom.x = zoom * speed
                request.Velocity.Zoom.space = 'http://www.onvif.org/ver10/tptz/ZoomSpaces/VelocityGenericSpace'

            self.ptz.ContinuousMove(request)
            return True
        except Exception as e:
            print(f"Move error {self.ip}: {e}")
            return False

    def stop(self) -> bool:
        if not self.ptz or not self.profile_token:
            return False
        # STOP always bypasses debounce
        try:
            self.ptz.Stop({'ProfileToken': self.profile_token, 'PanTilt': True, 'Zoom': True})
            return True
        except Exception as e:
            print(f"Stop error {self.ip}: {e}")
            return False

    def get_presets(self) -> List[Dict[str, Any]]:
        if not self.ptz or not self.profile_token:
            return []
            
        # Check cache
        now = time.time()
        if self.presets_cache and (now - self.presets_cache_ts) < self.presets_ttl:
            return self.presets_cache

        try:
            presets = self.ptz.GetPresets({'ProfileToken': self.profile_token})
            self.presets_cache = [{'id': p.token, 'name': p.Name} for p in presets]
            self.presets_cache_ts = now
            return self.presets_cache
        except Exception as e:
            print(f"GetPresets error {self.ip}: {e}")
            return []

    def force_refresh_presets(self):
        self.presets_cache = []
        return self.get_presets()

    def goto_preset(self, preset_token: str) -> bool:
        if not self.ptz or not self.profile_token:
            return False
        try:
            self.ptz.GotoPreset({'ProfileToken': self.profile_token, 'PresetToken': preset_token, 'Speed': {'PanTilt': {'x': 1, 'y': 1}, 'Zoom': {'x':1}}})
            return True
        except Exception as e:
            print(f"GotoPreset error {self.ip}: {e}")
            return False

    def set_preset(self, preset_name: str) -> bool:
        if not self.ptz or not self.profile_token:
            return False
        try:
            self.ptz.SetPreset({'ProfileToken': self.profile_token, 'PresetName': preset_name})
            return True
        except Exception as e:
            print(f"SetPreset error {self.ip}: {e}")
            return False

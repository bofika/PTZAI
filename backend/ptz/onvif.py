from onvif import ONVIFCamera
from .provider import PTZProvider
from typing import List, Dict, Any
import os

# Suppress zeep huge logs if needed, or in main.

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
            "continuous_move": True, # Assume true for connect
            "absolute_move": False,
            "relative_move": True,
            "presets": True
        }

    def get_capabilities(self):
        return self.capabilities

    def connect(self) -> bool:
        try:
            # We assume wsdl is available or standard path. 
            # Ideally we point to a local wsdl folder if we have it, but generic connect usually works if camera supports it.
            # However, onvif-zeep often requires a wsdl path if not default. 
            # We'll try default first.
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
            
            # Just take the first profile for now (MVP)
            self.profile_token = profiles[0].token
            return True
        except Exception as e:
            print(f"Error connecting to ONVIF camera {self.ip}: {e}")
            return False

    def move(self, pan: float, tilt: float, zoom: float, speed: float) -> bool:
        if not self.ptz or not self.profile_token:
            return False
            
        try:
            status = self.ptz.GetStatus({'ProfileToken': self.profile_token})
            
            # Construct move request
            # Note: Speed scaling depends on the camera capabilities. 
            # Typically 0.0-1.0 is standard for ContinuousMove.
            
            request = self.ptz.create_type('ContinuousMove')
            request.ProfileToken = self.profile_token
            
            if request.Velocity is None:
                request.Velocity = self.ptz.create_type('PTZSpeed')
                
            # PanTilt
            if pan != 0 or tilt != 0:
                request.Velocity.PanTilt = self.ptz.create_type('Vector2D')
                request.Velocity.PanTilt.x = pan * speed
                request.Velocity.PanTilt.y = tilt * speed
                request.Velocity.PanTilt.space = 'http://www.onvif.org/ver10/tptz/PanTiltSpaces/VelocityGenericSpace' # standard
            
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
        try:
            self.ptz.Stop({'ProfileToken': self.profile_token, 'PanTilt': True, 'Zoom': True})
            return True
        except Exception as e:
            print(f"Stop error {self.ip}: {e}")
            return False

    def get_presets(self) -> List[Dict[str, Any]]:
        if not self.ptz or not self.profile_token:
            return []
        try:
            presets = self.ptz.GetPresets({'ProfileToken': self.profile_token})
            return [{'id': p.token, 'name': p.Name} for p in presets]
        except Exception as e:
            print(f"GetPresets error {self.ip}: {e}")
            return []

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

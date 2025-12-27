from abc import ABC, abstractmethod
from typing import List, Dict, Any

class PTZProvider(ABC):
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the camera."""
        pass

    @abstractmethod
    def move(self, pan: float, tilt: float, zoom: float, speed: float) -> bool:
        """
        Continuous move.
        pan: -1.0 (left) to 1.0 (right)
        tilt: -1.0 (down) to 1.0 (up)
        zoom: -1.0 (out) to 1.0 (in)
        speed: 0.0 to 1.0
        """
        pass

    @abstractmethod
    def stop(self) -> bool:
        """Stop all movement."""
        pass

    @abstractmethod
    def get_presets(self) -> List[Dict[str, Any]]:
        """Return list of presets."""
        pass

    @abstractmethod
    def goto_preset(self, preset_token: str) -> bool:
        """Go to a specific preset."""
        pass

    @abstractmethod
    def set_preset(self, preset_name: str) -> bool:
        """Save current position as a preset."""
        pass

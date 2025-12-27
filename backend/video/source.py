from abc import ABC, abstractmethod
from typing import Optional
import numpy as np

class VideoSource(ABC):
    @abstractmethod
    def start(self):
        """Start capturing/streaming."""
        pass

    @abstractmethod
    def stop(self):
        """Stop capturing/streaming."""
        pass

    @abstractmethod
    def get_frame(self) -> Optional[np.ndarray]:
        """Return the latest frame as a numpy array (BGR). For Phase 2 CV."""
        pass

    @abstractmethod
    def get_stream_url(self) -> str:
        """Return the URL that the frontend should use to play this stream."""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Check if source is active."""
        pass

from .source import VideoSource
from typing import Optional
import numpy as np
from ..stream.manager import StreamManager

class RTSPSource(VideoSource):
    def __init__(self, rtsp_url: str, id: str):
        self.rtsp_url = rtsp_url
        self.id = id
        self.stream_manager = StreamManager()
        self.running = False

    def start(self):
        if not self.running:
            self.stream_manager.start_stream(self.id, self.rtsp_url)
            self.running = True

    def stop(self):
        if self.running:
            self.stream_manager.stop_stream(self.id)
            self.running = False

    def get_frame(self) -> Optional[np.ndarray]:
        # Phase 2: Add OpenCV capture for RTSP if needed for tracking
        # For now, just None or implement sidecar opencv cap
        return None 

    def get_stream_url(self) -> str:
        return f"/hls/{self.id}/stream.m3u8"

    def is_running(self) -> bool:
        return self.running

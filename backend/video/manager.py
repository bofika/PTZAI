from typing import Dict, Optional
from .source import VideoSource
from .ndi import NDISource
from .rtsp import RTSPSource
from .discovery import NDIDiscovery
from ..config import CameraConfig

class SourceManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SourceManager, cls).__new__(cls)
            cls._instance.sources: Dict[str, VideoSource] = {}
            cls._instance.discovery = NDIDiscovery()
        return cls._instance

    def get_source(self, cam_id: str) -> Optional[VideoSource]:
        return self.sources.get(cam_id)

    def create_source(self, config: Dict) -> VideoSource:
        cam_id = config.get("id")
        type = config.get("video_source_type", "rtsp")
        
        # Stop existing if any
        if cam_id in self.sources:
            self.sources[cam_id].stop()

        source = None
        if type == "ndi":
            name = config.get("ndi_source_name")
            if name:
                source = NDISource(name, cam_id)
        else: # RTSP default
            url = config.get("rtsp_url")
            if url:
                source = RTSPSource(url, cam_id)
        
        if source:
            self.sources[cam_id] = source
            source.start()
            
        return source

    def remove_source(self, cam_id: str):
        if cam_id in self.sources:
            self.sources[cam_id].stop()
            del self.sources[cam_id]

    def stop_all(self):
        for s in self.sources.values():
            s.stop()

    def scan_ndi(self):
        return self.discovery.scan()

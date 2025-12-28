from typing import Dict, Optional
from .preview import PreviewProvider
from .ndi import NDIProvider
from .rtsp import RTSPProvider
from .discovery import NDIDiscovery

class PreviewManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PreviewManager, cls).__new__(cls)
            cls._instance.providers: Dict[str, PreviewProvider] = {}
            cls._instance.discovery = NDIDiscovery()
        return cls._instance

    def get_provider(self, cam_id: str) -> Optional[PreviewProvider]:
        return self.providers.get(cam_id)

    def create_provider(self, config: Dict) -> Optional[PreviewProvider]:
        """
        Creates a provider based on the 'preview' config block.
        Expected Config: 
        {
          "id": "...",
          "preview": { 
             "type": "ndi"|"rtsp", 
             "ndi_source": "...", 
             "rtsp_url": "..." 
          }
        }
        """
        cam_id = config.get("id")
        preview_cfg = config.get("preview", {})
        p_type = preview_cfg.get("type", "rtsp")
        
        # Stop existing
        if cam_id in self.providers:
            self.providers[cam_id].stop()

        provider = None
        if p_type == "ndi":
            source_name = preview_cfg.get("ndi_source")
            if source_name:
                provider = NDIProvider(source_name, cam_id)
        else:
            url = preview_cfg.get("rtsp_url")
            if url:
                provider = RTSPProvider(url, cam_id)
        
        if provider:
            self.providers[cam_id] = provider
            provider.start()
            
        return provider

    def remove_provider(self, cam_id: str):
        if cam_id in self.providers:
            self.providers[cam_id].stop()
            del self.providers[cam_id]

    def stop_all(self):
        for p in self.providers.values():
            p.stop()

    def scan_ndi_sources(self):
        return self.discovery.scan()

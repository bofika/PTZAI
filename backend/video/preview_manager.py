from typing import Dict, Optional
from .preview import PreviewProvider
from .ndi import NDIProvider
from .rtsp import RTSPProvider
from .discovery import NDIDiscovery

import threading

class PreviewManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PreviewManager, cls).__new__(cls)
            cls._instance.providers: Dict[str, PreviewProvider] = {}
            cls._instance.discovery = NDIDiscovery()
        return cls._instance

    def get_provider(self, cam_id: str) -> Optional[PreviewProvider]:
        with self._lock:
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
        
        with self._lock:
            # Stop existing - CLEANUP
            if cam_id in self.providers:
                print(f"Stopping existing preview for {cam_id}")
                try:
                    self.providers[cam_id].stop()
                except Exception as e:
                    print(f"Error stopping provider {cam_id}: {e}")
                del self.providers[cam_id]

            provider = None
            print(f"Creating {p_type} provider for {cam_id}")
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
                # Start outside lock? No, keep it safe.
                try:
                    provider.start()
                except Exception as e:
                    print(f"Error starting provider {cam_id}: {e}")
                    # Don't store broken provider
                    return None
            
            return provider

    def check_health(self, cam_id: str) -> str:
        """Returns: ok | error | offline"""
        with self._lock:
            provider = self.providers.get(cam_id)
            if not provider:
                return "offline"
            # In Phase 1.2 we assume if provider exists it's "ok" or "starting"
            # A real check would ask the provider if its thread is alive.
            # Let's add a basic is_running check if possible, else "ok"
            if hasattr(provider, "is_running") and not provider.is_running():
                 return "error"
            return "ok"

    def remove_provider(self, cam_id: str):
        with self._lock:
            if cam_id in self.providers:
                try:
                    self.providers[cam_id].stop()
                except Exception as e:
                    print(f"Error stopping provider {cam_id}: {e}")
                del self.providers[cam_id]

    def stop_all(self):
        with self._lock:
            print("Stopping all preview providers...")
            for pid, p in self.providers.items():
                try:
                    p.stop()
                except Exception as e:
                     print(f"Error stopping {pid}: {e}")
            self.providers.clear()

    def scan_ndi_sources(self):
        return self.discovery.scan()

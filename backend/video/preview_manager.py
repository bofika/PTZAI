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
            cls._instance.states: Dict[str, Dict] = {} # cam_id -> {status, last_seen, last_error}
            cls._instance.discovery = NDIDiscovery()
        return cls._instance

    def _init_state(self, cam_id):
        if cam_id not in self.states:
            self.states[cam_id] = {
                "status": "offline",
                "last_seen": None,
                "last_error": None
            }

    def update_state(self, cam_id, status=None, error=None, activity=False):
        """
        Thread-safe state update.
        activity=True updates last_seen to now.
        status: starting | ok | restarting | offline | error
        """
        from datetime import datetime
        with self._lock:
            if cam_id not in self.states:
                self._init_state(cam_id)
            
            s = self.states[cam_id]
            if status:
                s["status"] = status
            if error:
                s["last_error"] = error
            if activity:
                s["last_seen"] = datetime.now().isoformat()
                # If we see activity, implied status is OK if distinct from starting
                if s["status"] not in ["starting", "restarting"]:
                     s["status"] = "ok"

    def get_state(self, cam_id):
         with self._lock:
             return self.states.get(cam_id, {
                "status": "offline",
                "last_seen": None,
                "last_error": None
             }).copy()

    def get_provider(self, cam_id: str) -> Optional[PreviewProvider]:
        with self._lock:
            return self.providers.get(cam_id)

    def create_provider(self, config: Dict) -> Optional[PreviewProvider]:
        cam_id = config.get("id")
        preview_cfg = config.get("preview", {})
        p_type = preview_cfg.get("type", "rtsp")
        
        # Guard: If running, don't duplicate
        with self._lock:
            if cam_id in self.providers:
                p = self.providers[cam_id]
                if p.is_running():
                    # print(f"Preview already running for {cam_id}") # verbose
                    return p
                else:
                    # Cleanup dead provider
                    try: p.stop()
                    except: pass
                    del self.providers[cam_id]

        self.update_state(cam_id, status="starting")
        
        provider = None
        try:
            # Define callback for provider to report status/activity
            def _status_cb(status=None, error=None, activity=False):
                self.update_state(cam_id, status=status, error=error, activity=activity)

            if p_type == "ndi":
                source_name = preview_cfg.get("ndi_source")
                if source_name:
                    # Pass callback to NDI Provider
                    provider = NDIProvider(source_name, cam_id, status_callback=_status_cb)
            else:
                url = preview_cfg.get("rtsp_url")
                if url:
                    provider = RTSPProvider(url, cam_id)
            
            if provider:
                with self._lock:
                   self.providers[cam_id] = provider
                
                # Start in background to avoid blocking startup
                import threading
                def _start_bg():
                    try:
                        print(f"Starting Preview Provider: {cam_id} ({p_type})")
                        provider.start()
                        self.update_state(cam_id, status="ok") 
                    except Exception as e:
                        print(f"Error starting provider {cam_id}: {e}")
                        self.update_state(cam_id, status="error", error=str(e))
                
                threading.Thread(target=_start_bg, daemon=True).start()
            
            return provider
            
        except Exception as e:
            self.update_state(cam_id, status="error", error=str(e))
            return None

    def check_health(self, cam_id: str) -> str:
        """Returns: ok | error | offline | starting | restarting"""
        s = self.get_state(cam_id)
        # Check timeout? If last_seen is too old (>10s) and status is OK, might be bad.
        # For now, just return explicit status.
        return s["status"]

    def restart_provider(self, cam_id: str, new_config: Dict = None) -> bool:
        from ..logger import logger
        self.update_state(cam_id, status="restarting")
        
        with self._lock:
            if cam_id in self.providers:
                try:
                    self.providers[cam_id].stop()
                    logger.log("INFO", "Preview stopped for restart", cam_id, "preview.restart")
                except Exception as e:
                    logger.log("ERROR", f"Error stopping for restart: {e}", cam_id, "preview.error")
                del self.providers[cam_id]
        
        # Create new
        if new_config:
            self.create_provider(new_config)
            logger.log("INFO", "Preview restarted", cam_id, "preview.restart")
            return True
        
        self.update_state(cam_id, status="error", error="Restart failed (no config)")
        return False

    def remove_provider(self, cam_id: str):
        self.update_state(cam_id, status="offline")
        with self._lock:
            if cam_id in self.providers:
                try:
                    self.providers[cam_id].stop()
                except Exception: pass
                del self.providers[cam_id]

    def stop_all(self):
        with self._lock:
            print("Stopping all preview providers...")
            for pid, p in self.providers.items():
                try: p.stop()
                except: pass
            self.providers.clear()
            self.states.clear() # Reset states? Or mark offline?
            # Mark offline
            # self.states = {} # Simple clear for shutdown

    def scan_ndi_sources(self):
        return self.discovery.scan()

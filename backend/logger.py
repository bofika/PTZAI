from datetime import datetime
from threading import Lock
from typing import List, Dict, Optional
import logging

class SystemLogger:
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SystemLogger, cls).__new__(cls)
            cls._instance.logs: List[Dict] = []
            cls._instance.max_logs = 200
        return cls._instance

    def log(self, level: str, message: str, camera_id: Optional[str] = None, event_type: str = "system"):
        """
        Add a log entry.
        Level: INFO, WARN, ERROR
        Event Type: camera.*, preview.*, control.*, etc.
        """
        entry = {
            "ts": datetime.now().isoformat(),
            "level": level.upper(),
            "message": message,
            "camera_id": camera_id,
            "event_type": event_type
        }
        
        with self._lock:
            self.logs.insert(0, entry) # Newest first
            if len(self.logs) > self.max_logs:
                self.logs.pop()
        
        # Also print to stdout for dev
        print(f"[{level.upper()}] {message} ({camera_id or 'System'})")

    def get_logs(self, limit: int = 50, camera_id: Optional[str] = None) -> List[Dict]:
        with self._lock:
            if camera_id:
                filtered = [l for l in self.logs if l["camera_id"] == camera_id]
                return filtered[:limit]
            return self.logs[:limit]

# Global helper
logger = SystemLogger()

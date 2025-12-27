import cv2
import time
import threading
import logging
import numpy as np
from typing import Optional, Generator
from .source import VideoSource

class NDISource(VideoSource):
    def __init__(self, source_name: str, id: str):
        self.source_name = source_name
        self.id = id
        self.recv = None
        self.running = False
        self.thread = None
        self.latest_frame: Optional[np.ndarray] = None
        self.lock = threading.Lock()

    def start(self):
        if self.running:
            return
        
        try:
            import NDIlib as ndi
            if not ndi.initialize():
                logging.error("Could not initialize NDIlib")
                return

            self.recv = ndi.recv_create_v3()
            if self.recv is None:
                logging.error("Could not create NDI receiver")
                return

            self.running = True
            
            # Connect to source
            source_t = ndi.Source()
            source_t.ndi_name = self.source_name
            ndi.recv_connect(self.recv, source_t)
            
            # Start capture loop
            self.thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.thread.start()
            logging.info(f"Started NDI Source: {self.source_name}")

        except ImportError:
            logging.error("NDIlib not found")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        
        if self.recv:
            import NDIlib as ndi
            ndi.recv_destroy(self.recv)
            self.recv = None

    def _capture_loop(self):
        import NDIlib as ndi
        while self.running:
            try:
                t, v, a, m = ndi.recv_capture_v2(self.recv, 1000)
                if t == ndi.FRAME_TYPE_VIDEO:
                    # Convert to numpy
                    frame = np.copy(v.data)
                    # NDI gives BGRA or UYVY usually, need to check pixel format. 
                    # Assuming standard defaults (usually UYVY or BGRA)
                    # For simplicity in Python wrapper, it often returns straight buffer.
                    # This part is tricky without testing specific camera format.
                    # If assume BGRA (common in ndi-python examples):
                    frame = frame.reshape((v.yres, v.xres, 4))
                    
                    # Store latest
                    with self.lock:
                        # Convert to BGR for OpenCV standard usage and smaller MJPEG
                        self.latest_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    
                    ndi.recv_free_video_v2(self.recv, v)
                elif t == ndi.FRAME_TYPE_AUDIO:
                    ndi.recv_free_audio_v2(self.recv, a)
                elif t == ndi.FRAME_TYPE_METADATA:
                    ndi.recv_free_metadata(self.recv, m)
                elif t == ndi.FRAME_TYPE_STATUS_CHANGE:
                    pass
            except Exception as e:
                logging.error(f"NDI Capture Error: {e}")
                time.sleep(1)

    def get_frame(self) -> Optional[np.ndarray]:
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
        return None

    def get_stream_url(self) -> str:
        # MJPEG endpoint
        return f"/api/video/{self.id}/mjpeg"

    def is_running(self) -> bool:
        return self.running

    def generate_mjpeg(self) -> Generator[bytes, None, None]:
        """Yields MJPEG frames for streaming response."""
        while self.running:
            with self.lock:
                frame = self.latest_frame
            
            if frame is not None:
                # Encode as JPEG
                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            
            # Cap FPS to avoid saturating network/CPU? 
            # Or just sleep tiny amount. 30fps = ~0.033
            time.sleep(0.033)

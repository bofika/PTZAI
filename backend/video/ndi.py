import cv2
import time
import threading
import logging
import numpy as np
from typing import Optional, Generator
from .preview import PreviewProvider

class NDIProvider(PreviewProvider):
    def __init__(self, source_name: str, id: str, status_callback=None):
        self.source_name = source_name
        self.id = id
        self.recv = None
        self.running = False
        self.thread = None
        self.latest_frame: Optional[np.ndarray] = None
        self.lock = threading.Lock()
        self.status_callback = status_callback

    def start(self):
        if self.running:
            return
        
        try:
            import NDIlib as ndi
            if not ndi.initialize():
                logging.error("Could not initialize NDIlib")
                if self.status_callback: self.status_callback(status="error", error="NDI init failed")
                return

            self.recv = ndi.recv_create_v3()
            if self.recv is None:
                logging.error("Could not create NDI receiver")
                if self.status_callback: self.status_callback(status="error", error="NDI recv create failed")
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
            if self.status_callback: self.status_callback(status="error", error="NDIlib not found")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        
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
                    frame_ok = False
                    
                    try:
                        expected_rgba = v.xres * v.yres * 4
                        expected_uyvy = v.xres * v.yres * 2
                        
                        processed_frame = None
                        
                        if frame.size == expected_uyvy:
                            # UYVY (16bpp)
                            frame = frame.reshape((v.yres, v.xres, 2))
                            processed_frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_UYVY)
                        elif frame.size == expected_rgba:
                            # BGRA (32bpp)
                            frame = frame.reshape((v.yres, v.xres, 4))
                            processed_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                        else:
                            logging.warning(f"NDI: Unknown frame size {frame.size} for {v.xres}x{v.yres}")
                            
                        if processed_frame is not None:
                            with self.lock:
                                self.latest_frame = processed_frame
                            frame_ok = True
                            
                    except Exception as e:
                        logging.error(f"NDI Decode Error: {e}")
                        if self.status_callback: self.status_callback(status="error", error=f"Decode: {e}")

                    ndi.recv_free_video_v2(self.recv, v)
                    
                    if frame_ok and self.status_callback:
                        self.status_callback(status="ok", activity=True)
                        
                elif t == ndi.FRAME_TYPE_AUDIO:
                    ndi.recv_free_audio_v2(self.recv, a)
                elif t == ndi.FRAME_TYPE_METADATA:
                    ndi.recv_free_metadata(self.recv, m)
                else:
                    pass
            except Exception as e:
                logging.error(f"NDI Capture Error: {e}")
                if self.status_callback: self.status_callback(status="error", error=f"Capture: {e}")
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
            
            time.sleep(0.033)

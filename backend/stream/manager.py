import subprocess
import os
import signal
import time
from typing import Dict

class StreamManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StreamManager, cls).__new__(cls)
            cls._instance.processes: Dict[str, subprocess.Popen] = {}
        return cls._instance

    def start_stream(self, cam_id: str, rtsp_url: str):
        if cam_id in self.processes:
            # Check if running
            if self.processes[cam_id].poll() is None:
                return  # Already running
            else:
                # Zombie/Crashed, cleanup
                del self.processes[cam_id]

        hls_dir = os.path.join(os.getcwd(), "hls", cam_id)
        os.makedirs(hls_dir, exist_ok=True)
        playlist_path = os.path.join(hls_dir, "stream.m3u8")

        # FFmpeg command for Low Latency HLS
        # -fflags nobuffer: reduce latency
        # -hls_time 1: 1 second segments
        # -hls_list_size 3: keep only 3 segments in playlist
        # -hls_flags delete_segments: clean up old segments
        cmd = [
            "ffmpeg",
            "-y",
            "-fflags", "nobuffer",
            "-rtsp_transport", "tcp", # More reliable than udp usually
            "-i", rtsp_url,
            "-c:v", "copy", # Copy video stream if possible (fastest) - failing that, re-encode might be needed for browser support if not H264
            # If codec is not h264, browsers won't play it. For MVP assume H264. 
            # If we need re-encode: "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency"
            "-c:a", "aac", # Audio
            "-f", "hls",
            "-hls_time", "1",
            "-hls_list_size", "3",
            "-hls_flags", "delete_segments+split_by_time",
            "-hls_allow_cache", "0",
            playlist_path
        ]
        
        # Start process
        print(f"Starting stream for {cam_id}: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL # Log to file if needed for debugging
        )
        self.processes[cam_id] = proc

    def stop_stream(self, cam_id: str):
        if cam_id in self.processes:
            proc = self.processes[cam_id]
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            del self.processes[cam_id]

    def stop_all(self):
        for cam_id in list(self.processes.keys()):
            self.stop_stream(cam_id)

"""
Thorlabs Camera Class for USB and Ethernet Webcam Streaming

This module provides a class to handle webcam streaming via USB (local) or Ethernet from one laptop to another.
The camera class supports:
- Capturing video from a local USB webcam or camera device
- Local USB mode for direct camera viewing
- Streaming video frames over Ethernet to a remote client (server mode)
- Receiving video streams from a remote server (client mode)
- Integration with motor control systems for automated positioning

The implementation uses OpenCV for video capture and socket communication for network streaming.
This is designed to work with Thorlabs cameras and can be extended to support other camera types.

Purpose:
    Enable local and remote monitoring and control of experimental setups by streaming camera feeds
    via USB or Ethernet, allowing motor control systems to reference live video feeds.
"""

from __future__ import annotations

import cv2
import socket
import struct
import threading
import time
from typing import Optional, Tuple, Callable
import numpy as np


class ThorlabsCamera:
    """
    Thorlabs Camera class for USB and Ethernet webcam streaming.
    
    Supports three modes:
    1. USB mode: Capture from local USB camera for direct viewing
    2. Server mode: Capture from local camera and stream to remote client
    3. Client mode: Connect to remote server and receive stream
    
    Usage:
        # USB mode (local camera)
        camera = ThorlabsCamera(mode='usb', camera_index=0)
        frame = camera.get_frame()
        
        # Server mode (streaming laptop)
        camera = ThorlabsCamera(mode='server', camera_index=0, port=8485)
        camera.start_streaming()
        
        # Client mode (receiving laptop)
        camera = ThorlabsCamera(mode='client', server_ip='192.168.1.100', port=8485)
        camera.connect()
        frame = camera.get_frame()
    """
    
    def __init__(
        self,
        mode: str = 'server',
        camera_index: int = 0,
        server_ip: Optional[str] = None,
        port: int = 8485,
        resolution: Tuple[int, int] = (640, 480),
        fps: int = 30,
        quality: int = 95
    ):
        """
        Initialize the Thorlabs Camera.
        
        Args:
            mode: 'usb' for local camera, 'server' to stream video, 'client' to receive video
            camera_index: Camera device index (0 for default webcam)
            server_ip: IP address of server (required for client mode)
            port: Network port for streaming (default: 8485, not used in USB mode)
            resolution: Camera resolution as (width, height)
            fps: Frames per second target
            quality: JPEG compression quality (1-100, not used in USB mode)
        """
        self.mode = mode.lower()
        self.camera_index = camera_index
        self.server_ip = server_ip
        self.port = port
        self.resolution = resolution
        self.fps = fps
        self.quality = quality
        
        # State variables
        self.capture: Optional[cv2.VideoCapture] = None
        self.socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.client_address: Optional[Tuple[str, int]] = None
        self.streaming = False
        self.connected = False
        self._stream_thread: Optional[threading.Thread] = None
        self._receive_thread: Optional[threading.Thread] = None
        self._read_thread: Optional[threading.Thread] = None
        self._current_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._reading = False
        
        # Frame callback for processing (useful for motor control integration)
        self.frame_callback: Optional[Callable[[np.ndarray], None]] = None
        
        if self.mode == 'usb':
            self._init_usb()
        elif self.mode == 'server':
            self._init_server()
        elif self.mode == 'client':
            if not server_ip:
                raise ValueError("server_ip required for client mode")
            self._init_client()
        else:
            raise ValueError(f"Invalid mode: {mode}. Must be 'usb', 'server', or 'client'")
    
    def _init_usb(self) -> None:
        """Initialize camera capture for USB mode."""
        try:
            self.capture = cv2.VideoCapture(self.camera_index)
            if not self.capture.isOpened():
                raise RuntimeError(f"Failed to open camera {self.camera_index}")
            
            # Set camera properties
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.capture.set(cv2.CAP_PROP_FPS, self.fps)
            
            # Start reading frames in background thread
            self._reading = True
            self._read_thread = threading.Thread(target=self._read_frames, daemon=True)
            self._read_thread.start()
            
            print(f"USB Camera {self.camera_index} initialized")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize USB camera: {e}")
    
    def _read_frames(self) -> None:
        """Read frames continuously in USB mode."""
        frame_time = 1.0 / self.fps if self.fps > 0 else 0.033
        
        while self._reading and self.capture:
            try:
                ret, frame = self.capture.read()
                if not ret:
                    time.sleep(frame_time)
                    continue
                
                # Resize if needed
                if frame.shape[1] != self.resolution[0] or frame.shape[0] != self.resolution[1]:
                    frame = cv2.resize(frame, self.resolution)
                
                with self._frame_lock:
                    self._current_frame = frame.copy()
                
                # Call frame callback if set
                if self.frame_callback:
                    try:
                        self.frame_callback(frame)
                    except Exception as e:
                        print(f"Error in frame callback: {e}")
                
                time.sleep(frame_time)
                
            except Exception as e:
                print(f"Error reading frame: {e}")
                time.sleep(frame_time)
    
    def _init_server(self) -> None:
        """Initialize camera capture for server mode."""
        try:
            self.capture = cv2.VideoCapture(self.camera_index)
            if not self.capture.isOpened():
                raise RuntimeError(f"Failed to open camera {self.camera_index}")
            
            # Set camera properties
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.capture.set(cv2.CAP_PROP_FPS, self.fps)
            
            print(f"Camera {self.camera_index} initialized for streaming")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize camera: {e}")
    
    def _init_client(self) -> None:
        """Initialize client socket for receiving stream."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print(f"Client initialized for connection to {self.server_ip}:{self.port}")
    
    def start_streaming(self) -> bool:
        """
        Start streaming video (server mode only).
        
        Returns:
            bool: True if streaming started successfully
        """
        if self.mode != 'server':
            raise RuntimeError("start_streaming() only available in server mode")
        
        if self.streaming:
            return True
        
        # Create server socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.socket.bind(('0.0.0.0', self.port))
            self.socket.listen(1)
            print(f"Server listening on port {self.port}...")
            
            # Wait for client connection in a separate thread
            threading.Thread(target=self._accept_client, daemon=True).start()
            
            self.streaming = True
            return True
        except Exception as e:
            print(f"Failed to start streaming: {e}")
            return False
    
    def _accept_client(self) -> None:
        """Accept client connection and start streaming frames."""
        try:
            self.client_socket, self.client_address = self.socket.accept()
            print(f"Client connected from {self.client_address}")
            
            # Start streaming thread
            self._stream_thread = threading.Thread(target=self._stream_frames, daemon=True)
            self._stream_thread.start()
        except Exception as e:
            print(f"Error accepting client: {e}")
    
    def _stream_frames(self) -> None:
        """Stream frames to connected client."""
        frame_time = 1.0 / self.fps
        
        while self.streaming and self.client_socket:
            try:
                ret, frame = self.capture.read()
                if not ret:
                    print("Failed to read frame from camera")
                    time.sleep(frame_time)
                    continue
                
                # Resize if needed
                if frame.shape[1] != self.resolution[0] or frame.shape[0] != self.resolution[1]:
                    frame = cv2.resize(frame, self.resolution)
                
                # Encode frame as JPEG
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
                _, buffer = cv2.imencode('.jpg', frame, encode_param)
                
                # Send frame size and data
                data = buffer.tobytes()
                size = len(data)
                
                try:
                    self.client_socket.sendall(struct.pack('>L', size))
                    self.client_socket.sendall(data)
                except Exception as e:
                    print(f"Error sending frame: {e}")
                    break
                
                time.sleep(frame_time)
                
            except Exception as e:
                print(f"Error in stream loop: {e}")
                break
        
        print("Streaming stopped")
    
    def connect(self) -> bool:
        """
        Connect to remote server (client mode only).
        
        Returns:
            bool: True if connection successful
        """
        if self.mode != 'client':
            raise RuntimeError("connect() only available in client mode")
        
        if self.connected:
            return True
        
        try:
            self.socket.connect((self.server_ip, self.port))
            print(f"Connected to server {self.server_ip}:{self.port}")
            
            # Start receiving thread
            self._receive_thread = threading.Thread(target=self._receive_frames, daemon=True)
            self._receive_thread.start()
            
            self.connected = True
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    def _receive_frames(self) -> None:
        """Receive and decode frames from server."""
        payload_size = struct.calcsize('>L')
        data = b''
        
        while self.connected and self.socket:
            try:
                # Receive frame size
                while len(data) < payload_size:
                    chunk = self.socket.recv(4096)
                    if not chunk:
                        raise ConnectionError("Connection closed")
                    data += chunk
                
                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack('>L', packed_msg_size)[0]
                
                # Receive frame data
                while len(data) < msg_size:
                    chunk = self.socket.recv(4096)
                    if not chunk:
                        raise ConnectionError("Connection closed")
                    data += chunk
                
                frame_data = data[:msg_size]
                data = data[msg_size:]
                
                # Decode frame
                frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                
                if frame is not None:
                    with self._frame_lock:
                        self._current_frame = frame.copy()
                    
                    # Call frame callback if set
                    if self.frame_callback:
                        try:
                            self.frame_callback(frame)
                        except Exception as e:
                            print(f"Error in frame callback: {e}")
                
            except ConnectionError:
                print("Connection lost")
                break
            except Exception as e:
                print(f"Error receiving frame: {e}")
                break
        
        self.connected = False
        print("Frame receiving stopped")
    
    def get_frame(self) -> Optional[np.ndarray]:
        """
        Get the latest frame (USB or client mode).
        
        Returns:
            np.ndarray: Latest frame as numpy array, or None if no frame available
        """
        if self.mode not in ['usb', 'client']:
            raise RuntimeError("get_frame() only available in USB or client mode")
        
        with self._frame_lock:
            return self._current_frame.copy() if self._current_frame is not None else None
    
    def set_frame_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """
        Set a callback function to be called when a new frame is received (USB or client mode).
        Useful for motor control integration.
        
        Args:
            callback: Function that takes a frame (np.ndarray) as argument
        """
        self.frame_callback = callback
    
    def is_streaming(self) -> bool:
        """Check if streaming is active (server mode)."""
        return self.streaming
    
    def is_connected(self) -> bool:
        """Check if connected to server (client mode)."""
        return self.connected
    
    def get_camera_info(self) -> dict:
        """
        Get camera information.
        
        Returns:
            dict: Camera properties and status
        """
        info = {
            'mode': self.mode,
            'resolution': self.resolution,
            'fps': self.fps,
        }
        
        if self.mode == 'usb':
            info['camera_index'] = self.camera_index
            info['reading'] = self._reading
            if self.capture:
                info['camera_opened'] = self.capture.isOpened()
        elif self.mode == 'server':
            info['port'] = self.port
            info['streaming'] = self.streaming
            info['camera_index'] = self.camera_index
            if self.capture:
                info['camera_opened'] = self.capture.isOpened()
        else:  # client mode
            info['port'] = self.port
            info['connected'] = self.connected
            info['server_ip'] = self.server_ip
        
        return info
    
    def stop_streaming(self) -> None:
        """Stop streaming (server mode)."""
        if self.mode == 'server':
            self.streaming = False
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
                self.client_socket = None
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
            print("Streaming stopped")
    
    def disconnect(self) -> None:
        """Disconnect from server (client mode)."""
        if self.mode == 'client':
            self.connected = False
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
            print("Disconnected from server")
    
    def close(self) -> None:
        """Close camera and cleanup resources."""
        if self.mode == 'usb':
            self._reading = False
            if self.capture:
                self.capture.release()
                self.capture = None
        elif self.mode == 'server':
            self.stop_streaming()
            if self.capture:
                self.capture.release()
                self.capture = None
        else:  # client mode
            self.disconnect()
        
        print("Camera closed")


if __name__ == "__main__":
    """
    Simple test for the camera class.
    Run as server on one laptop and client on another.
    """
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  USB: python thorlabs_camera.py usb [camera_index]")
        print("  Server: python thorlabs_camera.py server [port] [camera_index]")
        print("  Client: python thorlabs_camera.py client <server_ip> [port]")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == 'usb':
        camera_index = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        
        camera = ThorlabsCamera(mode='usb', camera_index=camera_index)
        print("USB camera opened. Press 'q' to quit...")
        try:
            while True:
                frame = camera.get_frame()
                if frame is not None:
                    cv2.imshow('USB Camera', frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                time.sleep(0.01)
        except KeyboardInterrupt:
            pass
        finally:
            camera.close()
            cv2.destroyAllWindows()
    
    elif mode == 'server':
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8485
        camera_index = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        
        camera = ThorlabsCamera(mode='server', camera_index=camera_index, port=port)
        camera.start_streaming()
        
        print("Server running. Press Ctrl+C to stop...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            camera.close()
    
    elif mode == 'client':
        if len(sys.argv) < 3:
            print("Error: server_ip required for client mode")
            sys.exit(1)
        
        server_ip = sys.argv[2]
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 8485
        
        camera = ThorlabsCamera(mode='client', server_ip=server_ip, port=port)
        if camera.connect():
            print("Client connected. Press Ctrl+C to stop...")
            try:
                while True:
                    frame = camera.get_frame()
                    if frame is not None:
                        # Display frame (requires OpenCV GUI support)
                        cv2.imshow('Remote Camera', frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
                    time.sleep(0.01)
            except KeyboardInterrupt:
                pass
            finally:
                camera.close()
                cv2.destroyAllWindows()
        else:
            print("Failed to connect to server")
    
    else:
        print(f"Invalid mode: {mode}")
        sys.exit(1)


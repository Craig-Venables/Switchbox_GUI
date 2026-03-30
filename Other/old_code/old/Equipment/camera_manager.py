"""
Camera Manager for unified camera interface

This module provides a manager class to initialize and unify different camera types
behind a common API. Currently supports Thorlabs cameras for Ethernet streaming.

The manager follows the Equipment module pattern, allowing easy extension to support
additional camera types in the future.

Purpose:
    Provide a stable interface for camera operations across different camera models,
    enabling easy integration with motor control systems and other equipment.
"""

from __future__ import annotations

from typing import Dict, Any, Optional

try:
    from Equipment.Camera.thorlabs_camera import ThorlabsCamera
except ModuleNotFoundError:
    # Allow running this file directly by adding project root to sys.path
    import os
    import sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from Equipment.Camera.thorlabs_camera import ThorlabsCamera


class CameraManager:
    """
    Manager to initialize and unify different camera drivers behind a common API.
    
    Primary goals:
      - Provide a stable, minimal surface area for GUIs/motor control integration
      - Make it easy to add new camera types (extend SUPPORTED and implement same API)
    
    Minimal unified interface:
      - connect() / close()
      - is_connected() -> bool
      - start_streaming() (server mode)
      - get_frame() (USB/client mode)
      - set_frame_callback(callback)
      - get_camera_info() -> dict
    
    Configuration keys (for from_config):
      - camera_type: Camera type (default: 'Thorlabs')
      - mode: 'usb' for local, 'server' to stream, 'client' to receive
      - camera_index: Camera device index (USB/server mode, default: 0)
      - server_ip: Server IP address (client mode, required)
      - port: Network port (default: 8485, not used in USB mode)
      - resolution: Tuple (width, height) or list [width, height]
      - fps: Frames per second target (default: 30)
    
    Usage:
        # USB mode (local camera)
        mgr = CameraManager.from_config({
            'camera_type': 'Thorlabs',
            'mode': 'usb',
            'camera_index': 0
        })
        frame = mgr.get_frame()
        
        # Server mode (streaming laptop)
        mgr = CameraManager.from_config({
            'camera_type': 'Thorlabs',
            'mode': 'server',
            'camera_index': 0,
            'port': 8485
        })
        mgr.start_streaming()
        
        # Client mode (receiving laptop)
        mgr = CameraManager.from_config({
            'camera_type': 'Thorlabs',
            'mode': 'client',
            'server_ip': '192.168.1.100',
            'port': 8485
        })
        mgr.connect()
        frame = mgr.get_frame()
    """
    
    SUPPORTED: Dict[str, Any] = {
        'Thorlabs': {
            'class': ThorlabsCamera,
            'config_keys': {
                'mode': 'mode',
                'camera_index': 'camera_index',
                'server_ip': 'server_ip',
                'port': 'port',
                'resolution': 'resolution',
                'fps': 'fps',
                'quality': 'quality',
            },
        },
    }
    
    def __init__(
        self,
        camera_type: str = 'Thorlabs',
        mode: str = 'usb',
        camera_index: Optional[int] = None,
        server_ip: Optional[str] = None,
        port: int = 8485,
        resolution: Optional[tuple] = None,
        fps: int = 30,
        quality: int = 95,
        auto_connect: bool = False
    ) -> None:
        """
        Initialize the camera manager.
        
        Args:
            camera_type: Type of camera (default: 'Thorlabs')
            mode: 'usb' for local, 'server' to stream, 'client' to receive
            camera_index: Camera device index (USB/server mode, default: 0)
            server_ip: Server IP address (client mode, required if mode='client')
            port: Network port (default: 8485, not used in USB mode)
            resolution: Camera resolution as (width, height), default (640, 480)
            fps: Frames per second target (default: 30)
            quality: JPEG compression quality 1-100 (default: 95, not used in USB mode)
            auto_connect: If True, automatically connect/start streaming
        """
        # Normalize camera type
        self.camera_type = self._normalize_type(camera_type)
        
        # Get camera metadata
        meta = self.SUPPORTED.get(self.camera_type)
        if not meta:
            raise ValueError(f"Unsupported camera type: {camera_type}")
        
        # Resolve parameters with defaults
        resolution = resolution if resolution else (640, 480)
        camera_index = camera_index if camera_index is not None else 0
        
        # Initialize camera instance
        camera_class = meta['class']
        self.instrument = camera_class(
            mode=mode,
            camera_index=camera_index,
            server_ip=server_ip,
            port=port,
            resolution=resolution,
            fps=fps,
            quality=quality
        )
        
        self.mode = mode
        self.port = port
        
        if auto_connect:
            if mode == 'server':
                try:
                    self.start_streaming()
                except Exception:
                    pass
            elif mode == 'client':
                try:
                    self.connect()
                except Exception:
                    pass
            # USB mode doesn't need explicit connection, just ready to read
    
    @classmethod
    def from_config(
        cls,
        config: Dict[str, Any],
        default_type: str = 'Thorlabs',
        auto_connect: bool = False
    ) -> 'CameraManager':
        """
        Create camera manager from configuration dictionary.
        
        Args:
            config: Configuration dictionary with camera parameters
            default_type: Default camera type if not specified
            auto_connect: If True, automatically connect/start streaming
        
        Returns:
            CameraManager: Initialized camera manager instance
        """
        camera_type = config.get('camera_type', default_type)
        mode = config.get('mode', 'server')
        
        # Get camera metadata
        meta = cls.SUPPORTED.get(cls._normalize_type(camera_type))
        if not meta:
            raise ValueError(f"Unsupported camera type: {camera_type}")
        
        # Extract parameters from config
        config_keys = meta.get('config_keys', {})
        
        # Build kwargs for camera initialization
        kwargs = {
            'camera_type': camera_type,
            'mode': mode,
        }
        
        # Map config keys to camera parameters
        if 'camera_index' in config:
            kwargs['camera_index'] = config['camera_index']
        if 'server_ip' in config:
            kwargs['server_ip'] = config['server_ip']
        if 'port' in config:
            kwargs['port'] = config['port']
        if 'resolution' in config:
            res = config['resolution']
            if isinstance(res, (list, tuple)) and len(res) == 2:
                kwargs['resolution'] = tuple(res)
        if 'fps' in config:
            kwargs['fps'] = config['fps']
        if 'quality' in config:
            kwargs['quality'] = config['quality']
        
        kwargs['auto_connect'] = auto_connect
        
        return cls(**kwargs)
    
    @classmethod
    def _normalize_type(cls, camera_type: str) -> str:
        """Normalize camera type string."""
        key = (camera_type or '').strip().lower().replace(' ', '')
        aliases = {
            'thorlabs': 'Thorlabs',
        }
        return aliases.get(key, camera_type)
    
    # ----- Connection management -----
    def connect(self) -> bool:
        """
        Connect to remote server (client mode only).
        
        Returns:
            bool: True if connection successful
        """
        if not self.instrument:
            raise RuntimeError("Camera not initialized")
        return self.instrument.connect()
    
    def start_streaming(self) -> bool:
        """
        Start streaming video (server mode only).
        
        Returns:
            bool: True if streaming started successfully
        """
        if not self.instrument:
            raise RuntimeError("Camera not initialized")
        return self.instrument.start_streaming()
    
    def stop_streaming(self) -> None:
        """Stop streaming (server mode)."""
        if self.instrument and hasattr(self.instrument, 'stop_streaming'):
            self.instrument.stop_streaming()
    
    def disconnect(self) -> None:
        """Disconnect from server (client mode)."""
        if self.instrument and hasattr(self.instrument, 'disconnect'):
            self.instrument.disconnect()
    
    def close(self) -> None:
        """Close camera and cleanup resources."""
        if self.instrument:
            try:
                self.instrument.close()
            except Exception:
                pass
    
    # ----- Status helpers -----
    def is_connected(self) -> bool:
        """Check if connected (USB/client mode) or streaming (server mode)."""
        if not self.instrument:
            return False
        
        if self.mode == 'usb':
            # USB mode is always "connected" if camera is opened
            return hasattr(self.instrument, 'capture') and self.instrument.capture is not None and self.instrument.capture.isOpened()
        elif self.mode == 'client':
            return self.instrument.is_connected() if hasattr(self.instrument, 'is_connected') else False
        else:  # server mode
            return self.instrument.is_streaming() if hasattr(self.instrument, 'is_streaming') else False
    
    def is_streaming(self) -> bool:
        """Check if streaming is active (server mode)."""
        if not self.instrument or self.mode != 'server':
            return False
        return self.instrument.is_streaming() if hasattr(self.instrument, 'is_streaming') else False
    
    # ----- Frame access -----
    def get_frame(self):
        """
        Get the latest frame (USB or client mode).
        
        Returns:
            np.ndarray: Latest frame as numpy array, or None if no frame available
        """
        if not self.instrument:
            raise RuntimeError("Camera not initialized")
        return self.instrument.get_frame()
    
    def set_frame_callback(self, callback) -> None:
        """
        Set a callback function to be called when a new frame is received (USB or client mode).
        Useful for motor control integration.
        
        Args:
            callback: Function that takes a frame (np.ndarray) as argument
        """
        if not self.instrument:
            raise RuntimeError("Camera not initialized")
        if hasattr(self.instrument, 'set_frame_callback'):
            self.instrument.set_frame_callback(callback)
    
    # ----- Information -----
    def get_camera_info(self) -> Dict[str, Any]:
        """
        Get camera information.
        
        Returns:
            dict: Camera properties and status
        """
        if not self.instrument:
            return {'initialized': False}
        
        info = {'camera_type': self.camera_type, 'mode': self.mode}
        
        if hasattr(self.instrument, 'get_camera_info'):
            inst_info = self.instrument.get_camera_info()
            info.update(inst_info)
        
        return info
    
    # ----- Convenience constructors -----
    @classmethod
    def create_server(
        cls,
        camera_index: int = 0,
        port: int = 8485,
        resolution: tuple = (640, 480),
        fps: int = 30,
        auto_start: bool = True
    ) -> 'CameraManager':
        """
        Convenience method to create a server camera manager.
        
        Args:
            camera_index: Camera device index
            port: Network port
            resolution: Camera resolution
            fps: Frames per second
            auto_start: If True, automatically start streaming
        
        Returns:
            CameraManager: Server mode camera manager
        """
        return cls(
            camera_type='Thorlabs',
            mode='server',
            camera_index=camera_index,
            port=port,
            resolution=resolution,
            fps=fps,
            auto_connect=auto_start
        )
    
    @classmethod
    def create_client(
        cls,
        server_ip: str,
        port: int = 8485,
        auto_connect: bool = True
    ) -> 'CameraManager':
        """
        Convenience method to create a client camera manager.
        
        Args:
            server_ip: Server IP address
            port: Network port
            auto_connect: If True, automatically connect
        
        Returns:
            CameraManager: Client mode camera manager
        """
        return cls(
            camera_type='Thorlabs',
            mode='client',
            server_ip=server_ip,
            port=port,
            auto_connect=auto_connect
        )
    
    @classmethod
    def create_usb(
        cls,
        camera_index: int = 0,
        resolution: tuple = (640, 480),
        fps: int = 30
    ) -> 'CameraManager':
        """
        Convenience method to create a USB camera manager.
        
        Args:
            camera_index: Camera device index
            resolution: Camera resolution
            fps: Frames per second
        
        Returns:
            CameraManager: USB mode camera manager
        """
        return cls(
            camera_type='Thorlabs',
            mode='usb',
            camera_index=camera_index,
            resolution=resolution,
            fps=fps,
            auto_connect=True
        )


# Example usage
if __name__ == "__main__":
    """
    Simple test for the camera manager.
    """
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Server: python camera_manager.py server [port] [camera_index]")
        print("  Client: python camera_manager.py client <server_ip> [port]")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == 'server':
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8485
        camera_index = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        
        config = {
            'camera_type': 'Thorlabs',
            'mode': 'server',
            'camera_index': camera_index,
            'port': port,
        }
        
        mgr = CameraManager.from_config(config, auto_connect=True)
        print(f"Server running on port {port}. Press Ctrl+C to stop...")
        
        try:
            import time
            while True:
                info = mgr.get_camera_info()
                print(f"Status: {info}")
                time.sleep(5)
        except KeyboardInterrupt:
            pass
        finally:
            mgr.close()
    
    elif mode == 'client':
        if len(sys.argv) < 3:
            print("Error: server_ip required for client mode")
            sys.exit(1)
        
        server_ip = sys.argv[2]
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 8485
        
        config = {
            'camera_type': 'Thorlabs',
            'mode': 'client',
            'server_ip': server_ip,
            'port': port,
        }
        
        mgr = CameraManager.from_config(config, auto_connect=True)
        
        if mgr.is_connected():
            print(f"Client connected to {server_ip}:{port}. Press Ctrl+C to stop...")
            try:
                import time
                import cv2
                frame_count = 0
                while True:
                    frame = mgr.get_frame()
                    if frame is not None:
                        frame_count += 1
                        if frame_count % 30 == 0:
                            print(f"Received {frame_count} frames")
                        # Display frame
                        cv2.imshow('Remote Camera', frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
                    time.sleep(0.01)
            except KeyboardInterrupt:
                pass
            finally:
                mgr.close()
                try:
                    cv2.destroyAllWindows()
                except:
                    pass
        else:
            print("Failed to connect to server")
    
    else:
        print(f"Invalid mode: {mode}")
        sys.exit(1)


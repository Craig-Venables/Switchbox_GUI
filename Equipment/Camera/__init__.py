"""
Camera package for Equipment module

This package provides camera classes for Ethernet streaming and integration
with motor control systems. Currently supports Thorlabs cameras.
"""

from Equipment.Camera.thorlabs_camera import ThorlabsCamera

__all__ = ['ThorlabsCamera']




"""
Application Settings Manager

Handles persistent application settings using JSON.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


class Settings:
    """Application settings manager"""
    
    def __init__(self, settings_file: Optional[Path] = None):
        self.settings_file = settings_file or Path(__file__).parent.parent / "settings.json"
        self.settings: Dict[str, Any] = {}
        self.load()
    
    def load(self):
        """Load settings from file"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r') as f:
                    self.settings = json.load(f)
            except Exception as e:
                print(f"Error loading settings: {e}")
                self._create_defaults()
        else:
            self._create_defaults()
    
    def _create_defaults(self):
        """Create default settings"""
        self.settings = {
            'window': {
                'width': 1600,
                'height': 900,
                'maximized': False
            },
            'theme': {
                'style': 'Fusion',  # Qt style
                'color_scheme': 'light'  # 'light' or 'dark'
            },
            'recent_folders': [],
            'max_recent_folders': 10,
            'plot': {
                'default_layout': '1x1',  # '1x1', '2x1', '1x2', '2x2'
                'line_width': 2,
                'marker_size': 6,
                'grid': True,
                'legend': True,
                'dpi': 100
            },
            'export': {
                'default_dpi': 300,
                'default_format': 'png'
            }
        }
        self.save()
    
    def save(self):
        """Save settings to file"""
        try:
            # Ensure directory exists
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except RecursionError:
            print(f"Error: Recursion detected while saving settings")
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value using dot notation.
        Example: settings.get('window.width')
        """
        keys = key.split('.')
        value = self.settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        Set a setting value using dot notation.
        Example: settings.set('window.width', 1920)
        """
        keys = key.split('.')
        d = self.settings
        
        # Navigate to the parent dict
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        
        # Set the value
        d[keys[-1]] = value
        self.save()
    
    def add_recent_folder(self, folder_path: str):
        """Add a folder to recent folders list"""
        recent = self.get('recent_folders', [])
        
        # Remove if already exists
        if folder_path in recent:
            recent.remove(folder_path)
        
        # Add to front
        recent.insert(0, folder_path)
        
        # Limit size
        max_recent = self.get('max_recent_folders', 10)
        recent = recent[:max_recent]
        
        self.set('recent_folders', recent)
    
    def get_recent_folders(self) -> list:
        """Get list of recent folders"""
        return self.get('recent_folders', [])


# Global settings instance
_settings = None

def get_settings() -> Settings:
    """Get the global settings instance"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Module test
if __name__ == "__main__":
    print("Settings Manager - Module Test")
    print("=" * 60)
    
    settings = get_settings()
    
    print(f"\nSettings file: {settings.settings_file}")
    print(f"Window size: {settings.get('window.width')}x{settings.get('window.height')}")
    print(f"Theme: {settings.get('theme.style')}")
    print(f"Recent folders: {settings.get_recent_folders()}")
    
    # Test adding recent folder
    settings.add_recent_folder("/test/path/1")
    settings.add_recent_folder("/test/path/2")
    print(f"\nAfter adding folders: {settings.get_recent_folders()}")


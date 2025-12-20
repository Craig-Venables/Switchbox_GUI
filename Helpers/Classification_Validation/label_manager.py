"""
Label Manager - Store and manage ground truth labels for validation.
"""

import json
import os
from typing import Dict, Optional
from pathlib import Path


class LabelManager:
    """Manage ground truth labels for device classification validation."""
    
    def __init__(self, labels_file: Optional[str] = None):
        """
        Initialize label manager.
        
        Args:
            labels_file: Path to JSON file storing labels. If None, uses default location.
        """
        if labels_file is None:
            # Default to data/labels.json in this module's directory
            base_dir = Path(__file__).parent
            labels_file = str(base_dir / "data" / "labels.json")
        
        self.labels_file = labels_file
        self.labels: Dict[str, str] = {}
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(self.labels_file), exist_ok=True)
        
        # Load existing labels
        self.load()
    
    def load(self) -> None:
        """Load labels from file."""
        if os.path.exists(self.labels_file):
            try:
                with open(self.labels_file, 'r', encoding='utf-8') as f:
                    self.labels = json.load(f)
                print(f"[LABELS] Loaded {len(self.labels)} labels from {self.labels_file}")
            except Exception as e:
                print(f"[LABELS] Error loading labels: {e}")
                self.labels = {}
        else:
            self.labels = {}
    
    def save(self) -> None:
        """Save labels to file."""
        try:
            with open(self.labels_file, 'w', encoding='utf-8') as f:
                json.dump(self.labels, f, indent=2, ensure_ascii=False)
            print(f"[LABELS] Saved {len(self.labels)} labels to {self.labels_file}")
        except Exception as e:
            print(f"[LABELS] Error saving labels: {e}")
            raise
    
    def get_label(self, device_id: str) -> Optional[str]:
        """
        Get ground truth label for a device.
        
        Args:
            device_id: Device identifier (e.g., "test_sample_A_1")
            
        Returns:
            Label string (memristive/ohmic/capacitive/conductive) or None if not labeled
        """
        return self.labels.get(device_id)
    
    def set_label(self, device_id: str, label: str) -> None:
        """
        Set ground truth label for a device.
        
        Args:
            device_id: Device identifier
            label: Ground truth label (memristive/ohmic/capacitive/conductive)
        """
        valid_labels = ['memristive', 'ohmic', 'capacitive', 'conductive']
        if label.lower() not in valid_labels:
            raise ValueError(f"Invalid label '{label}'. Must be one of: {valid_labels}")
        
        self.labels[device_id] = label.lower()
    
    def remove_label(self, device_id: str) -> None:
        """Remove label for a device."""
        if device_id in self.labels:
            del self.labels[device_id]
    
    def get_all_labels(self) -> Dict[str, str]:
        """Get all labels."""
        return self.labels.copy()
    
    def has_label(self, device_id: str) -> bool:
        """Check if device has a label."""
        return device_id in self.labels
    
    def get_labeled_count(self) -> int:
        """Get count of labeled devices."""
        return len(self.labels)
    
    def clear(self) -> None:
        """Clear all labels."""
        self.labels = {}

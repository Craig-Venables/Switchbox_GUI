"""
Plot Annotation Tools

Tools for adding annotations (arrows, circles, text boxes) to plots.
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                              QLabel, QLineEdit, QColorDialog, QGroupBox,
                              QComboBox, QSpinBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from matplotlib.patches import FancyArrowPatch, Circle, Rectangle
from matplotlib.text import Text
from matplotlib.patches import FancyBboxPatch
import numpy as np


class AnnotationManager:
    """Manages plot annotations"""
    
    def __init__(self, ax):
        self.ax = ax
        self.annotations = []
        self.current_annotation_type = 'text'
        self.annotation_color = '#FFD700'  # Gold
        
    def add_text(self, x, y, text, color=None, fontsize=12, bbox=True):
        """Add text annotation with optional box"""
        color = color or self.annotation_color
        
        if bbox:
            text_obj = self.ax.text(x, y, text, fontsize=fontsize, color=color,
                                  bbox=dict(boxstyle='round,pad=0.5', 
                                          facecolor='white', 
                                          edgecolor=color,
                                          alpha=0.8))
        else:
            text_obj = self.ax.text(x, y, text, fontsize=fontsize, color=color)
        
        self.annotations.append(('text', text_obj))
        return text_obj
    
    def add_arrow(self, x1, y1, x2, y2, color=None, arrowstyle='->', lw=2):
        """Add arrow annotation"""
        color = color or self.annotation_color
        
        arrow = FancyArrowPatch((x1, y1), (x2, y2),
                               arrowstyle=arrowstyle,
                               color=color,
                               linewidth=lw,
                               mutation_scale=20)
        self.ax.add_patch(arrow)
        self.annotations.append(('arrow', arrow))
        return arrow
    
    def add_circle(self, x, y, radius, color=None, fill=False, lw=2):
        """Add circle annotation"""
        color = color or self.annotation_color
        
        circle = Circle((x, y), radius, 
                       color=color,
                       fill=fill,
                       linewidth=lw,
                       alpha=0.7 if fill else 1.0)
        self.ax.add_patch(circle)
        self.annotations.append(('circle', circle))
        return circle
    
    def add_rectangle(self, x, y, width, height, color=None, fill=False, lw=2):
        """Add rectangle annotation"""
        color = color or self.annotation_color
        
        rect = Rectangle((x, y), width, height,
                        color=color,
                        fill=fill,
                        linewidth=lw,
                        alpha=0.7 if fill else 1.0)
        self.ax.add_patch(rect)
        self.annotations.append(('rectangle', rect))
        return rect
    
    def clear_all(self):
        """Remove all annotations"""
        for ann_type, obj in self.annotations:
            if ann_type in ['arrow', 'circle', 'rectangle']:
                obj.remove()
            else:  # text
                obj.remove()
        self.annotations.clear()
    
    def remove_last(self):
        """Remove last added annotation"""
        if self.annotations:
            ann_type, obj = self.annotations.pop()
            obj.remove()
            return True
        return False


class AnnotationToolbar(QWidget):
    """Toolbar for adding annotations to plots"""
    
    annotation_added = pyqtSignal(str, dict)  # Signal when annotation is added
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_type = 'text'
        self.annotation_color = QColor(255, 215, 0)  # Gold
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the UI"""
        layout = QVBoxLayout(self)
        
        # Annotation type selector
        type_group = QGroupBox("Annotation Type")
        type_layout = QHBoxLayout()
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(['Text Box', 'Arrow', 'Circle', 'Rectangle'])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        type_layout.addWidget(QLabel("Type:"))
        type_layout.addWidget(self.type_combo, 1)
        
        # Color button
        self.color_btn = QPushButton("Color")
        self.color_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.annotation_color.name()};
                border: 1px solid #666;
                padding: 4px;
            }}
        """)
        self.color_btn.clicked.connect(self.change_color)
        type_layout.addWidget(self.color_btn)
        
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # Text-specific controls
        self.text_group = QGroupBox("Text Box")
        text_layout = QVBoxLayout()
        
        text_input_layout = QHBoxLayout()
        text_input_layout.addWidget(QLabel("Text:"))
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Enter annotation text...")
        text_input_layout.addWidget(self.text_input, 1)
        text_layout.addLayout(text_input_layout)
        
        font_size_layout = QHBoxLayout()
        font_size_layout.addWidget(QLabel("Font Size:"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        self.font_size_spin.setValue(12)
        font_size_layout.addWidget(self.font_size_spin)
        text_layout.addLayout(font_size_layout)
        
        self.text_bbox_check = QPushButton("With Box")  # Using button as toggle
        self.text_bbox_check.setCheckable(True)
        self.text_bbox_check.setChecked(True)
        text_layout.addWidget(self.text_bbox_check)
        
        self.text_group.setLayout(text_layout)
        layout.addWidget(self.text_group)
        
        # Arrow-specific controls
        self.arrow_group = QGroupBox("Arrow")
        arrow_layout = QVBoxLayout()
        
        arrow_style_layout = QHBoxLayout()
        arrow_style_layout.addWidget(QLabel("Style:"))
        self.arrow_style_combo = QComboBox()
        self.arrow_style_combo.addItems(['->', '-|>', '->', '-|>', '<->', '<|-|>'])
        arrow_style_layout.addWidget(self.arrow_style_combo, 1)
        arrow_layout.addLayout(arrow_style_layout)
        
        arrow_width_layout = QHBoxLayout()
        arrow_width_layout.addWidget(QLabel("Line Width:"))
        self.arrow_width_spin = QDoubleSpinBox()
        self.arrow_width_spin.setRange(0.5, 5.0)
        self.arrow_width_spin.setValue(2.0)
        arrow_width_layout.addWidget(self.arrow_width_spin)
        arrow_layout.addLayout(arrow_width_layout)
        
        self.arrow_group.setLayout(arrow_layout)
        layout.addWidget(self.arrow_group)
        self.arrow_group.hide()
        
        # Circle-specific controls
        self.circle_group = QGroupBox("Circle")
        circle_layout = QVBoxLayout()
        
        radius_layout = QHBoxLayout()
        radius_layout.addWidget(QLabel("Radius:"))
        self.circle_radius_spin = QDoubleSpinBox()
        self.circle_radius_spin.setRange(0.001, 1000)
        self.circle_radius_spin.setValue(0.1)
        self.circle_radius_spin.setDecimals(3)
        radius_layout.addWidget(self.circle_radius_spin, 1)
        circle_layout.addLayout(radius_layout)
        
        self.circle_fill_check = QPushButton("Filled")
        self.circle_fill_check.setCheckable(True)
        self.circle_fill_check.setChecked(False)
        circle_layout.addWidget(self.circle_fill_check)
        
        circle_width_layout = QHBoxLayout()
        circle_width_layout.addWidget(QLabel("Line Width:"))
        self.circle_width_spin = QDoubleSpinBox()
        self.circle_width_spin.setRange(0.5, 5.0)
        self.circle_width_spin.setValue(2.0)
        circle_width_layout.addWidget(self.circle_width_spin)
        circle_layout.addLayout(circle_width_layout)
        
        self.circle_group.setLayout(circle_layout)
        layout.addWidget(self.circle_group)
        self.circle_group.hide()
        
        # Rectangle-specific controls
        self.rect_group = QGroupBox("Rectangle")
        rect_layout = QVBoxLayout()
        
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Width:"))
        self.rect_width_spin = QDoubleSpinBox()
        self.rect_width_spin.setRange(0.001, 1000)
        self.rect_width_spin.setValue(0.2)
        size_layout.addWidget(self.rect_width_spin, 1)
        
        size_layout.addWidget(QLabel("Height:"))
        self.rect_height_spin = QDoubleSpinBox()
        self.rect_height_spin.setRange(0.001, 1000)
        self.rect_height_spin.setValue(0.1)
        size_layout.addWidget(self.rect_height_spin, 1)
        rect_layout.addLayout(size_layout)
        
        self.rect_fill_check = QPushButton("Filled")
        self.rect_fill_check.setCheckable(True)
        self.rect_fill_check.setChecked(False)
        rect_layout.addWidget(self.rect_fill_check)
        
        rect_width_layout = QHBoxLayout()
        rect_width_layout.addWidget(QLabel("Line Width:"))
        self.rect_line_width_spin = QDoubleSpinBox()
        self.rect_line_width_spin.setRange(0.5, 5.0)
        self.rect_line_width_spin.setValue(2.0)
        rect_width_layout.addWidget(self.rect_line_width_spin)
        rect_layout.addLayout(rect_width_layout)
        
        self.rect_group.setLayout(rect_layout)
        layout.addWidget(self.rect_group)
        self.rect_group.hide()
        
        # Position inputs (for manual placement)
        pos_group = QGroupBox("Position (Click on plot to place)")
        pos_layout = QVBoxLayout()
        
        xy_layout = QHBoxLayout()
        xy_layout.addWidget(QLabel("X:"))
        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(-1e12, 1e12)
        self.x_spin.setDecimals(4)
        xy_layout.addWidget(self.x_spin, 1)
        
        xy_layout.addWidget(QLabel("Y:"))
        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(-1e12, 1e12)
        self.y_spin.setDecimals(4)
        xy_layout.addWidget(self.y_spin, 1)
        pos_layout.addLayout(xy_layout)
        
        # For arrows, need end position
        self.arrow_end_group = QGroupBox("End Position (Arrow)")
        arrow_end_layout = QHBoxLayout()
        arrow_end_layout.addWidget(QLabel("X2:"))
        self.x2_spin = QDoubleSpinBox()
        self.x2_spin.setRange(-1e12, 1e12)
        self.x2_spin.setDecimals(4)
        arrow_end_layout.addWidget(self.x2_spin, 1)
        
        arrow_end_layout.addWidget(QLabel("Y2:"))
        self.y2_spin = QDoubleSpinBox()
        self.y2_spin.setRange(-1e12, 1e12)
        self.y2_spin.setDecimals(4)
        arrow_end_layout.addWidget(self.y2_spin, 1)
        self.arrow_end_group.setLayout(arrow_end_layout)
        pos_layout.addWidget(self.arrow_end_group)
        self.arrow_end_group.hide()
        
        pos_group.setLayout(pos_layout)
        layout.addWidget(pos_group)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ Add Annotation")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 6px;
            }
        """)
        self.add_btn.clicked.connect(self.add_annotation)
        action_layout.addWidget(self.add_btn)
        
        self.remove_last_btn = QPushButton("Remove Last")
        self.remove_last_btn.clicked.connect(self.remove_last_annotation)
        action_layout.addWidget(self.remove_last_btn)
        
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.clicked.connect(self.clear_all_annotations)
        action_layout.addWidget(self.clear_btn)
        
        layout.addLayout(action_layout)
        layout.addStretch()
    
    def on_type_changed(self, text):
        """Handle annotation type change"""
        self.current_type = text.lower().replace(' ', '_')
        
        # Show/hide relevant groups
        self.text_group.setVisible(text == 'Text Box')
        self.arrow_group.setVisible(text == 'Arrow')
        self.circle_group.setVisible(text == 'Circle')
        self.rect_group.setVisible(text == 'Rectangle')
        self.arrow_end_group.setVisible(text == 'Arrow')
    
    def change_color(self):
        """Change annotation color"""
        color = QColorDialog.getColor(self.annotation_color, self, "Select Annotation Color")
        if color.isValid():
            self.annotation_color = color
            self.color_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color.name()};
                    border: 1px solid #666;
                    padding: 4px;
                }}
            """)
    
    def add_annotation(self):
        """Emit signal to add annotation"""
        x = self.x_spin.value()
        y = self.y_spin.value()
        color = self.annotation_color.name()
        
        params = {
            'type': self.current_type,
            'x': x,
            'y': y,
            'color': color
        }
        
        if self.current_type == 'text_box':
            params['text'] = self.text_input.text() or "Annotation"
            params['fontsize'] = self.font_size_spin.value()
            params['bbox'] = self.text_bbox_check.isChecked()
        elif self.current_type == 'arrow':
            params['x2'] = self.x2_spin.value()
            params['y2'] = self.y2_spin.value()
            params['style'] = self.arrow_style_combo.currentText()
            params['linewidth'] = self.arrow_width_spin.value()
        elif self.current_type == 'circle':
            params['radius'] = self.circle_radius_spin.value()
            params['fill'] = self.circle_fill_check.isChecked()
            params['linewidth'] = self.circle_width_spin.value()
        elif self.current_type == 'rectangle':
            params['width'] = self.rect_width_spin.value()
            params['height'] = self.rect_height_spin.value()
            params['fill'] = self.rect_fill_check.isChecked()
            params['linewidth'] = self.rect_line_width_spin.value()
        
        self.annotation_added.emit(self.current_type, params)
    
    def remove_last_annotation(self):
        """Emit signal to remove last annotation"""
        # This will be handled by the plotting tab
        pass
    
    def clear_all_annotations(self):
        """Emit signal to clear all annotations"""
        # This will be handled by the plotting tab
        pass
    
    def set_position(self, x, y):
        """Update position spinboxes from plot click"""
        self.x_spin.setValue(x)
        self.y_spin.setValue(y)
    
    def set_arrow_end_position(self, x, y):
        """Update arrow end position"""
        self.x2_spin.setValue(x)
        self.y2_spin.setValue(y)



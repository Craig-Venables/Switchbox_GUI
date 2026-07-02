"""Tool adapters for Measurement GUI integration."""

from pathlib import Path

from gui.measurement_gui.tool_registry import SubprocessTool

_ROOT = Path(__file__).resolve().parents[3]

DisplayToolAdapter = SubprocessTool(
    tool_id="display",
    label="Display Control (ST7789)",
    description="Arduino TFT colour / flash / brightness control",
    module_path="tools/Display/main.py",
    cwd=_ROOT / "tools" / "Display",
)

LedTestingToolAdapter = SubprocessTool(
    tool_id="led_testing",
    label="LED Testing (Arduino)",
    description="Exclusive LED control and timed patterns",
    module_path="tools/LED_testing/main.py",
    cwd=_ROOT / "tools" / "LED_testing",
)

__all__ = ["DisplayToolAdapter", "LedTestingToolAdapter"]

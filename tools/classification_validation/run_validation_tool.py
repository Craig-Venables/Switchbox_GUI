#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from tools.classification_validation.gui.main_window import ValidationToolGUI

if __name__ == "__main__":
    app = ValidationToolGUI()
    app.run()


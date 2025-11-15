"""
HP4140B - Backward Compatibility Wrapper

This file provides backward compatibility by importing from the new
hp4140b package location.

All functionality is now provided by Equipment.SMU_AND_PMU.hp4140b.controller.

New code should use:
    from Equipment.SMU_AND_PMU.hp4140b import HP4140BController
"""

from __future__ import annotations

from Equipment.SMU_AND_PMU.hp4140b.controller import HP4140BController

__all__ = ['HP4140BController']

"""Keithley 4200-SCS — custom / setup-only profile (connect + checklist, no listed tests)."""

from .keithley4200_core import Keithley4200KXCICommon

_SETUP_NOTES = """Keithley 4200 (custom / setup)
- Pick profile: keithley4200_pmu for fast PMU pulses (µs); keithley4200_smu for SMU + optical bias-timed read.
- Cabling: follow Clarius / lab procedure for PMU vs SMU routing; laser is typically driven from PMU (CH2) for laser_and_read.
- Load required C modules / UL programs on the 4200 before timed pulse tests.
- Future: SMU + function-generator configurations will use an additional profile here."""


class Keithley4200CustomSystem(Keithley4200KXCICommon):
    """Same KXCI connection as other profiles; pulse GUI shows no tests (capabilities empty)."""

    def get_system_name(self) -> str:
        return "keithley4200_custom"

    def get_idn(self) -> str:
        base = super().get_idn()
        if base == "Not Connected":
            return base
        return f"{base}\n\n{_SETUP_NOTES}"

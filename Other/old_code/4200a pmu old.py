class Keithley4200A_PMUController:
    """Dedicated helper for PMU operation on 4200A using LPT.

    Construct with address like '192.168.0.10:8888|PMU1-CH1'.
    """

    def __init__(self, address: str) -> None:
        """Connect to the PMU on the given address.

        Address examples:
          - "192.168.0.10:8888"
          - "192.168.0.10"
          - "192.168.0.10:8888" (defaults to PMU1-CH1)
        """
        base = Keithley4200AController(address if "|" in address else address + "|PMU1-CH1")
        if not base._is_pmu:
            raise ValueError("PMUController requires a PMU address like '...|PMU1-CH1'")

        self._base = base
        self.lpt = base.lpt
        self.param = base.param
        self._card_id = base._instr_id
        # ensure channel is 1- or 2-based (never 0)
        self._chan = (base._pmu_channel + 1) if base._pmu_channel is not None else 1

        

        # # Set conservative safe defaults within 4200A PMU limits
        # self.configure_pulse(
        # v_src_range=10.0,         
        # v_meas_range_type=0, v_meas_range=10.0,
        # i_meas_range_type=0, i_meas_range=0.2,  
        # v_limit=5.0, i_limit=0.1, power_limit=1.0,
        # start_pct=0.1, stop_pct=0.9, num_pulses=1,
        # period=20e-6, delay=1e-7, width=10e-6, rise=1e-7, fall=1e-7,
        # load_ohm=1e6,
        # )

    # -----------------------
    # PMU-Specific Functions
    # -----------------------
    def configure_pulse(self, v_src_range, v_meas_range_type, v_meas_range,
                        i_meas_range_type, i_meas_range,
                        v_limit, i_limit, power_limit,
                        start_pct, stop_pct, num_pulses,
                        period, delay, width, rise, fall,
                        load_ohm):
        """Configure pulse parameters for this channel.

        This method keeps the configuration minimal and readable. Values are not
        validated here; use helper validate methods if needed before calling.
        """
        # try:
        #     self.lpt.pulse_ranges(self._card_id, self._chan,
        #                         v_src_range,
        #                         v_meas_range_type, v_meas_range,
        #                         i_meas_range_type, i_meas_range)
        # except Exception as e:
        #     print("pulse_ranges failed:", e)
        #     raise

        self.lpt.pg2_init(self._card_id, 0)
        self.lpt.rpm_config(self._card_id, self._chan,
                            self.param.KI_RPM_PATHWAY, self.param.KI_RPM_PULSE)
        self.lpt.pulse_meas_sm(self._card_id, self._chan, 0, 1, 0, 1, 0, 1, 1)
        self.lpt.pulse_ranges(self._card_id, self._chan, v_src_range,
                              v_meas_range_type, v_meas_range,
                              i_meas_range_type, i_meas_range)
        self.lpt.pulse_limits(self._card_id, self._chan, v_limit, i_limit, power_limit)
        self.lpt.pulse_meas_timing(self._card_id, self._chan,
                                   start_pct, stop_pct, int(num_pulses))
        self.lpt.pulse_source_timing(self._card_id, self._chan,
                                     period, delay, width, rise, fall)
        self.lpt.pulse_load(self._card_id, self._chan, load_ohm)

    # ---- Simple setters to adjust parts of config without resending all ----
    def set_pulse_source_timing(self, period: float, delay: float, width: float, rise: float, fall: float):
        self.lpt.pulse_source_timing(self._card_id, self._chan, period, delay, width, rise, fall)

    def set_pulse_meas_timing(self, start_pct: float, stop_pct: float, num_pulses: int):
        self.lpt.pulse_meas_timing(self._card_id, self._chan, start_pct, stop_pct, int(num_pulses))

    def set_pulse_limits(self, v_limit: float, i_limit: float, power_limit: float):
        self.lpt.pulse_limits(self._card_id, self._chan, v_limit, i_limit, power_limit)

    def set_ranges(self, v_src_range: float, v_meas_range_type: int, v_meas_range: float,
                   i_meas_range_type: int, i_meas_range: float):
        self.lpt.pulse_ranges(self._card_id, self._chan, v_src_range,
                              v_meas_range_type, v_meas_range,
                              i_meas_range_type, i_meas_range)

    def set_load(self, load_ohm: float):
        self.lpt.pulse_load(self._card_id, self._chan, load_ohm)

    def arm_single_pulse(self, amplitude_v: float, base_v: float = 0.0):
        """Prepare a single pulse with given amplitude.

        Use together with exec_and_fetch() to execute and read back data.
        """
        self.lpt.pulse_sweep_linear(self._card_id, self._chan,
                                    self.param.PULSE_AMPLITUDE_SP,
                                    float(amplitude_v), float(amplitude_v), float(base_v))
        self.lpt.pulse_output(self._card_id, self._chan, 1)

    def exec_and_fetch(self, as_dataframe: bool = True):
        """Execute the pulse sequence configured and fetch results."""
        self.lpt.pulse_exec(self.param.PULSE_MODE_SIMPLE)

        # Poll for completion
        timeout, t0 = 30.0, time.time()
        while True:
            status, _ = self.lpt.pulse_exec_status()
            if status != self.param.PMU_TEST_STATUS_RUNNING:
                break
            if time.time() - t0 > timeout:
                self.lpt.dev_abort()
                raise TimeoutError("PMU pulse execution timed out")
            time.sleep(0.05)

        # Fetch data
        buf_size = self.lpt.pulse_chan_status(self._card_id, self._chan)
        v, i, ts, statuses = self.lpt.pulse_fetch(self._card_id, self._chan, 0, max(0, buf_size - 1))

        if as_dataframe:
            df = pd.DataFrame({
                "t (s)": ts,
                "V (V)": v,
                "I (A)": i,
                "Status": statuses,
            })
            df["Channel"] = self._chan
            return df

        return v, i, ts, statuses

    # --------------- High-level wrappers ---------------
    def run_fixed_amplitude_pulses(self, amplitude_v: float, base_v: float, num_pulses: int,
                                   width_s: float, period_s: float,
                                   rise_s: float = 1e-7, fall_s: float = 1e-7,
                                   as_dataframe: bool = True):
        """Run a simple pulse train of identical pulses and fetch results."""
        self.set_pulse_source_timing(period_s, 1e-7, width_s, rise_s, fall_s)
        self.set_pulse_meas_timing(0.1, 0.9, num_pulses)
        self.lpt.pulse_sweep_linear(self._card_id, self._chan,
                                    self.param.PULSE_AMPLITUDE_SP,
                                    float(amplitude_v), float(amplitude_v), float(base_v))
        self.lpt.pulse_output(self._card_id, self._chan, 1)
        return self.exec_and_fetch(as_dataframe=as_dataframe)

    def run_amplitude_sweep(self, start_v: float, stop_v: float, step_v: float,
                            base_v: float, width_s: float, period_s: float,
                            num_pulses: int | None = None,
                            as_dataframe: bool = True):
        """Run a linear amplitude sweep and fetch results."""
        if num_pulses is None:
            try:
                num_pulses = int(abs(stop_v - start_v) / abs(step_v)) + 1
            except Exception:
                num_pulses = 1
        self.set_pulse_source_timing(period_s, 1e-7, width_s, 1e-7, 1e-7)
        self.set_pulse_meas_timing(0.1, 0.9, num_pulses)
        self.lpt.pulse_sweep_linear(self._card_id, self._chan,
                                    self.param.PULSE_AMPLITUDE_SP,
                                    float(start_v), float(stop_v), float(step_v))
        self.lpt.pulse_output(self._card_id, self._chan, 1)
        return self.exec_and_fetch(as_dataframe=as_dataframe)

    def run_bitstring(self, pattern: str, amplitude_v: float, base_v: float,
                      width_s: float, period_s: float,
                      rise_s: float = 1e-7, fall_s: float = 1e-7,
                      as_dataframe: bool = True):
        """Run a pulse pattern like "1011"; '1' applies amplitude_v, '0' applies base_v.

        Implementation executes one pulse at a time and concatenates results.
        """
        dfs = []
        for ch in str(pattern):
            level = amplitude_v if ch == '1' else base_v
            self.set_pulse_source_timing(period_s, 1e-7, width_s, rise_s, fall_s)
            self.set_pulse_meas_timing(0.1, 0.9, 1)
            self.arm_single_pulse(level, base_v)
            df = self.exec_and_fetch(as_dataframe=True)
            dfs.append(df if isinstance(df, pd.DataFrame) else pd.DataFrame({
                "t (s)": df[2], "V (V)": df[0], "I (A)": df[1], "Status": df[3]
            }))
        out = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
        return out if as_dataframe else (
            out.get("V (V)", []).to_list(),
            out.get("I (A)", []).to_list(),
            out.get("t (s)", []).to_list(),
        )

    def output(self, enable: bool):
        self.lpt.pulse_output(self._card_id, self._chan, 1 if enable else 0)

    def close(self):
        try:
            self.output(False)
        except Exception:
            pass
        self._base.close()

    # ---- Introspection helpers ----
    def is_connected(self) -> bool:
        try:
            return self._card_id is not None and self.lpt is not None
        except Exception:
            return False

if __name__ == "__main__":
    # Minimal self-test (requires reachable 4200A LPT server). Adjust IP as needed.
    addr = "192.168.0.10:8888"
    print("Keithley 4200A Controller Test")
    try:
        ctrl = Keithley4200AController(addr)
        print(ctrl.get_idn())
        ctrl.enable_output(False)
        pmu = Keithley4200A_PMUController(addr + "|PMU1-CH1")
        print("PMU connected:", pmu.is_connected())

        df = pmu.run_fixed_amplitude_pulses(amplitude_v=0.5, base_v=0.0, num_pulses=1,
                                            width_s=10e-6, period_s=20e-6)
        print("Fetched rows:", len(df) if isinstance(df, pd.DataFrame) else "n/a")
        pmu.close()
        ctrl.close()
    except Exception as exc:
        print("Self-test skipped/failed:", exc)

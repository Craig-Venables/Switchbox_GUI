import pyvisa
import numpy as np
import time

__all__ = ['K2400', 'K2401', 'K2461', 'K6221']


class K2400:
    """
    Keithley 2400 control interface using RS232 connection, designed for use when switching
    """

    def connect(self, port):
        """
        connects to the instrument with baud rate 19200 and timeout 10s. prints IDN.

        :param int port: the COM port number i.e. 3 for COM3

        :returns: None
        """
        rm = pyvisa.ResourceManager('@ivi')
        self.k2400 = rm.open_resource(f'COM{port}', baud_rate=19200)
        self.k2400.close()
        self.k2400.open()
        self.k2400.baud_rate = 19200
        self.k2400.timeout = 10000
        self.k2400.write_termination = '\r\n'
        self.k2400.read_termination = '\r\n'
        self.k2400.write('*rst')
        self.k2400.write('*cls')
        print('connected to: ', self.k2400.query('*IDN?'))

    def use_rear_io(self, use_rear):
        if use_rear:
            self.k2400.write('route:terminals rear')
        else:
            self.k2400.write('route:terminals front')

    # Sends a square pulse of 5ms duration and amplitude "current" Amps
    def pulse_current(self, current, four_wire=True):
        """
        Sends a square pulse of 5ms duration and specified amplitude Amps

        :param float current: current in AMPS
        :param four_wire: bool, whether to use 4 wire mode (default, True) or 2 wire (False)

        :returns: None
        """
        self.k2400.write('*rst')
        self.k2400.write(':SYSTEM:BEEP:STATE OFF')
        self.k2400.write('trac:cle')
        self.k2400.write('*cls')
        if four_wire:
            self.k2400.write('syst:rsen on')
        else:
            self.k2400.write('syst:rsen off')
        self.k2400.write('trig:coun 1')
        self.k2400.write('sour:func curr')
        self.k2400.write('sens:func:conc off')
        self.k2400.write('sens:volt:rang:auto on')
        self.k2400.write('sens:volt:prot:lev 20')
        self.k2400.write(f'sour:curr:lev {current}')
        self.k2400.write('trig:del 0')
        self.k2400.write('sour:del 0')
        self.k2400.write('sour:cle:auto on')
        self.k2400.write('init')
        self.k2400.write('*wai')

    def prepare_measure_only(self, range=0, nplc=2, four_wire=True):
        """
        Prepare to measure many points in 2 or 4 wire mode one at a time. Use with read_one

        :param float current: the source current for measurements
        :param float num: number of points to measure
        :param float nplc: number of powerline cycles per measurement
        :param four_wire: bool, whether to use 4 wire mode (default, True) or 2 wire (False)

        :returns: None
        """
        self.k2400.write('*rst')
        self.k2400.write('*cls')
        self.k2400.write(':SYSTEM:BEEP:STATE OFF')
        self.k2400.write('sour:func curr')
        self.k2400.write(f'sour:curr {0}')
        self.k2400.write('sour:curr:rang:auto on')
        self.k2400.write('sens:volt:prot:lev 20')
        self.k2400.write('sens:func "volt"')
        self.k2400.write(f'sens:volt:nplc {nplc}')
        if range == 0:
            self.k2400.write('sens:volt:rang:auto on')
        else:
            self.k2400.write('sens:volt:rang:auto off')
            self.k2400.write(f'sens:volt:rang {range}')
        if four_wire:
            self.k2400.write('syst:rsen on')
        else:
            self.k2400.write('syst:rsen off')
        time.sleep(0.5)
        self.k2400.write('form:elem time, volt, curr')

    def prepare_measure_one(self, current, range=0, nplc=2, four_wire=True):
        """
        Prepare to measure many points in 2 ir 4 wire mode one at a time. Use with read_one

        :param float current: the source current for measurements
        :param float num: number of points to measure
        :param float nplc: number of powerline cycles per measurement
        :param four_wire: bool, whether to use 4 wire mode (default, True) or 2 wire (False)

        :returns: None
        """
        self.k2400.write('*rst')
        self.k2400.write('*cls')
        self.k2400.write(':SYSTEM:BEEP:STATE OFF')
        self.k2400.write('sour:func curr')
        self.k2400.write(f'sour:curr {current}')
        self.k2400.write('sour:curr:rang:auto on')
        self.k2400.write('sens:volt:prot:lev 20')
        self.k2400.write('sens:func "volt"')
        self.k2400.write(f'sens:volt:nplc {nplc}')
        if range == 0:
            self.k2400.write('sens:volt:rang:auto on')
        else:
            self.k2400.write('sens:volt:rang:auto off')
            self.k2400.write(f'sens:volt:rang {range}')
        if four_wire:
            self.k2400.write('syst:rsen on')
        else:
            self.k2400.write('syst:rsen off')
        self.k2400.write('form:elem time, volt, curr')
        # self.k2400.write('outp on')

    def read_one(self):
        voltage, current, t = self.k2400.query_ascii_values('READ?')
        return t, voltage, current

    def fetch_one(self):
        # data = self.k2400.query_ascii_values('fetch?')
        # print(data)
        # t = data[2]
        # voltage = data[0]
        # current = data[1]
        voltage, current, t = self.k2400.query_ascii_values('fetch?')
        return t, voltage, current

    # Sets up the parameters to measure data and store it in buffer
    def prepare_measure_n(self, current, num, nplc=2, four_wire=True):
        """
        Measure many points in 2 or 4 wire mode. Use with "trigger" and "read buffer"

        :param float current: the source current for measurements
        :param float num: number of points to measure
        :param float nplc: number of powerline cycles per measurement
        :param four_wire: bool, whether to use 4 wire mode (default, True) or 2 wire (False)

        :returns: None
        """
        self.k2400.write('*rst')
        self.k2400.write('*cls')
        self.k2400.write(':SYSTEM:BEEP:STATE OFF')
        self.k2400.write('sour:func curr')
        self.k2400.write(f'sour:curr {current}')
        self.k2400.write('sour:curr:rang:auto on')
        self.k2400.write('sens:volt:prot:lev 20')
        self.k2400.write('sens:func "volt"')
        self.k2400.write(f'sens:volt:nplc {nplc}')
        self.k2400.write('sens:volt:rang:auto on')
        if four_wire:
            self.k2400.write('syst:rsen on')
        else:
            self.k2400.write('syst:rsen off')
        self.k2400.write('form:elem time, volt, curr')
        self.k2400.write('trac:cle')  # clear buffer
        self.k2400.write(f'trig:count {num}')  # number of p
        self.k2400.write(f'trac:poin {num}')  # size of buff
        self.k2400.write('trac:feed sens')  # what goes in b
        self.k2400.write('trac:feed:cont next')  # doesn't o
        self.k2400.write('trac:tst:form abs')
        self.k2400.write('outp on')

    def trigger(self):
        """
        Send the command to start measurements and wait to finish before processing further commands.

        :returns: None
        """
        self.k2400.write('init')
        self.k2400.write('*wai')

    def read_buffer(self):
        """
        Disables output current and then reads all data from the buffer in the format: current, voltage, time, current voltage time...

        :returns: time, voltage, current. Use v/c to get resistance.
        :rtype: (np.ndarray, np.ndarray, np.ndarray)
        """
        self.k2400.write('outp off')
        data = np.array(self.k2400.query_ascii_values('trac:data?'))
        t = data[2::3]
        v = data[1::3]
        c = data[0::3]
        return t, v, c

    def disable_output_current(self):
        self.k2400.write('outp off')

    def enable_output_current(self):
        self.k2400.write('outp on')

    def close(self):
        """
        Closes the instrument, i.e. frees the port up for other applications/threads. Also disables output.

        :returns: None
        """
        self.k2400.write('outp off')
        self.k2400.close()


class K2401:
    """
    Keithley 2401 control interface using RS232 connection, designed for use when switching
    """

    def connect(self, port):
        """
        connects to the instrument with baud rate 19200 and timeout 10s. prints IDN.

        :param port: int, the COM port number i.e. 3 for COM3

        :returns: None
        """
        rm = pyvisa.ResourceManager('@ivi')
        self.k2401 = rm.open_resource(f'COM{port}', baud_rate=19200)
        self.k2401.close()
        self.k2401.open()
        self.k2401.baud_rate = 19200
        self.k2401.timeout = 10000
        self.k2401.write_termination = '\r\n'
        self.k2401.read_termination = '\r\n'
        self.k2401.write('*rst')
        self.k2401.write('*cls')
        print('connected to: ', self.k2401.query('*IDN?'))

    def pulse_current(self, current, four_wire=True):
        """
        Sends a square pulse of 5ms duration and specified amplitude Amps

        :param current: float, current in AMPS
        :param four_wire: bool, whether to use 4 wire mode (default, True) or 2 wire (False)

        :returns: None
        """
        self.k2401.write('*rst')
        self.k2401.write('trac:cle')
        self.k2401.write('*cls')
        if four_wire:
            self.k2401.write('syst:rsen on')
        else:
            self.k2401.write('syst:rsen off')
        self.k2401.write('trig:coun 1')
        self.k2401.write('sour:func curr')
        self.k2401.write('sens:func:conc off')
        self.k2401.write('sens:volt:rang:auto on')
        self.k2401.write('sens:volt:prot:lev 20')
        self.k2401.write(f'sour:curr:lev {current}')
        self.k2401.write('trig:del 0')
        self.k2401.write('sour:del 0')
        self.k2401.write('sour:cle:auto on')
        self.k2401.write('init')
        self.k2401.write('*wai')

    # Sets up the parameters to measure data and store it in buffer
    def measure_n(self, current, num, nplc=2, four_wire=True):
        """
        Measure many points in 4 wire mode. Use with "trigger" and "read buffer"

        :param current: float, the source current for 4wire measurements
        :param num: float/int, number of points to measure
        :param nplc: float/int, number of powerline cycles per measurement
        :param four_wire: bool, whether to use 4 wire mode (default, True) or 2 wire (False)

        :returns: None
        """
        self.k2401.write('*rst')
        self.k2401.write('*cls')
        self.k2401.write('sour:func curr')
        self.k2401.write(f'sour:curr {current}')
        self.k2401.write('sour:curr:rang:auto on')
        self.k2401.write('sens:volt:prot:lev 20')
        self.k2401.write('sens:func "volt"')
        self.k2401.write(f'sens:volt:nplc {nplc}')
        self.k2401.write('sens:volt:rang:auto on')
        if four_wire:
            self.k2401.write('syst:rsen on')
        else:
            self.k2401.write('syst:rsen off')
        self.k2401.write('form:elem time, volt, curr')
        self.k2401.write('trac:cle')  # clear buffer
        self.k2401.write(f'trig:count {num}')  # number of p
        self.k2401.write(f'trac:poin {num}')  # size of buff
        self.k2401.write('trac:feed sens')  # what goes in b
        self.k2401.write('trac:feed:cont next')  # doesn't o
        self.k2401.write('trac:tst:form abs')
        self.k2401.write('outp on')

    def trigger(self):
        """
        Send the command to start measurements and wait to finish before processing further commands.

        :returns: None
        """
        self.k2401.write('init')
        self.k2401.write('*wai')

    # reads the results from the buffer
    def read_buffer(self):
        """
        Disables output current and then reads all data from the buffer in the format: current, voltage, time, current voltage time...

        :returns: time, voltage, current. Use v/c to get resistance.
        :rtype: (np.ndarray, np.ndarray, np.ndarray)
        """
        self.k2401.write('outp off')
        data = np.array(self.k2401.query_ascii_values('trac:data?'))
        t = data[2::3]
        v = data[1::3]
        c = data[0::3]
        return t, v, c

    def close(self):
        """
        Closes the instrument, i.e. frees the port up for other applications/threads. Also disables output.

        :returns: None
        """
        self.k2401.write('outp off')
        self.k2401.close()


class K2461:
    """
    Keithley 2461 control interface using USB_pyvisa connection, designed for use when switching
    """

    def connect(self):
        """
        Connects to our Keithley 2461 sourcemeter instrument using the known unique identifier. Sets timeout to 50 seconds and
        resets the instrument.

        :returns: None
        """
        rm = pyvisa.ResourceManager('@ivi')
        self.k2461 = rm.open_resource('USB0::0x05E6::0x2461::04121022::INSTR', write_termination='\n', send_end=True)
        self.k2461.timeout = 50000
        print('connected to: ', self.k2461.query('*idn?'))
        self.k2461.write('*rst')

    def prepare_pulsing_voltage(self, voltage, width, clim=100e-3):
        """
        Forms a voltage pulse trigger group for the instrument.See also: send_pulse and set_ext_trig()

        :param float voltage: The desired peak voltage of the sample in volts
        :param float width: The duration of the rise time and plateau in seconds
        :param float clim: The current limit for the pulse def:100mA

        :returns: None
        """
        self.k2461.write('*rst')
        self.k2461.write(
            f'sour:puls:swe:volt:lin 0, 0, {voltage}, 2, {width}, off, "defbuffer1", 0, 0, 1, {clim}, {clim}, off, off')
        self.set_ext_trig()

    def prepare_pulsing_current(self, current, width, vlim=40):
        """
        Forms a current pulse trigger group for the instrument. See also: send_pulse and set_ext_trig()

        :param float current: Desired peak current in AMPS (please use 1e-3 for milliamps for eg.
        :param float width: Duration of pulse rise and plateau time in seconds
        :param float vlim: The voltage limit for the pulse def: 40V

        :returns: None
        """
        self.k2461.write('*rst')
        self.k2461.write(
            f'sour:puls:swe:curr:lin 0, 0, {current}, 2, {width}, off, "defbuffer1", 0, 0, 1, {vlim}, {vlim}, off, off')

    def prepare_customsweep_currentpulse(self, sweep_list, width, nsweeps, delay, vlim=40, meason=1, range=0.2):
        self.k2461.write('*rst')
        self.k2461.write(f'stat:cle')
        self.k2461.write(f'stat:ques:map 0, 2732, 2731')
        self.k2461.write(f'stat:ques:enable 1')
        self.k2461.write(f'stat:oper:map 0, 2732, 2731')
        self.k2461.write(f'stat:oper:enable 1')
        # self.k2461.write(f'trac:make "mybuffer", {num}')

        self.k2461.write('sour:func curr')
        self.k2461.write('sens:func "volt"')
        self.k2461.write(f'sour:curr:vlim 0.2')
        self.k2461.write(f'sour:puls:curr:vlim 0.2') # didn't do anything
        self.k2461.write(f'sour:curr:range {10e-3}')
        self.k2461.write('sens:volt:rsen on')
        self.k2461.write('sens:volt:nplc 0.01')
        self.k2461.write('sens:volt:azer 0')
        self.k2461.write('sens:volt:rang:auto off')
        self.k2461.write('sens:volt:rsen on')
        self.k2461.write(f'sens:volt:rang 0.2')

        # self.k2461.write('sour:curr:rang:auto on')
        # self.k2461.write(f'sour:puls:list:curr {list}')
        self.k2461.write(f'source:puls:list:curr {sweep_list[0]}')
        for x in sweep_list[1:]:
            self.k2461.write(f'source:puls:list:curr:append {x}')
        self.k2461.write(
            f'source:puls:swe:curr:list {width}, {meason}, "defbuffer1", 1, {nsweeps}, {delay}, {delay}, 1')


    def set_ext_trig(self, pin=3):
        """
        Configures the DIO pins on the instrument to send an external positive edges pulse to occur just before the
        voltage pulse is sent to the DUT

        :param pin: int/float the DIO pin on the instrument that is connected to the stinger on the BNC cable for the
                    scope (default 3). The script will work without a scope connected, of course.

        :returns: None
        """
        # todo(stu) figure out how to avoid the k2461 warning about pulse width.
        self.k2461.write(f'dig:line{pin}:mode trig, out')
        self.k2461.write(f'trig:dig{pin}:out:log pos')
        self.k2461.write(f'trig:dig{pin}:out:stim NOT1')
        self.k2461.write('trig:bloc:not 5, 1')
        self.k2461.write(f'TRIG:DIG{pin}:OUT:PULS 100e-6')

    def send_pulse(self):
        """
        Activates the preloaded trigger group from prepare_pulsing_voltage or prepare_pulsing_current to emit a pulse
        and (if configured) an external trigger

        :returns: None
        """
        self.k2461.write('init')  # send pulse
        # self.k2461.write('*wai')

    def prepare_measure_n(self, current, num, nplc=2):
        """
        Prepares the instruments to measure specified number of points in a 4wire resistance configuration. Use trigger
        start the measurement and read_buffer to collect the data. This does not enable probe current.

        :param float current: probing current amplitude in amps
        :param float num: number of points to measure
        :param float nplc: number of powerline cycles per point def: 2

        :returns: None
        """
        self.k2461.write('*rst')
        self.k2461.write(f'trac:make "mybuffer", {num}')
        self.k2461.write('sour:curr:rang 200e-6')
        self.k2461.write('sour:func curr')
        self.k2461.write(f'sour:curr {current}')
        self.k2461.write('sour:curr:read:back on')
        self.k2461.write('sens:func "volt"')
        self.k2461.write('sens:volt:rsen on')
        self.k2461.write(f'sens:volt:nplc {nplc}')
        self.k2461.write('sens:volt:rang:auto on')
        self.k2461.write(f'count {num}')

    def prepare_measure_one(self, current, nplc=2, four_wire=True):
        """
        Prepares the instrument to measure a 4wire resistance one at a time. For use with either trigger_fetch and
        fetch_one or with read_one. This does not enables probe current. use enable output current after

        :param float current:
        :param float nplc:
        :param bool four_wire: whether to measure in 4 wire or 2 wire mode

        :returns: None
        """
        self.k2461.write('sens:func "volt"')
        self.k2461.write('sens:volt:rang:auto on')
        if four_wire:
            self.k2461.write('sens:volt:rsen on')
        else:
            self.k2461.write('sens:volt:rsen off')
        self.k2461.write(f'sens:volt:nplc {nplc}')
        self.k2461.write('sour:func curr')
        self.k2461.write(f'sour:curr {current}')
        self.k2461.write('sour:curr:range:auto on')
        self.k2461.write('sour:curr:vlim 2')

    def enable_4_wire_probe(self, current, nplc=2, vlim=1):
        """
        Prepares the instrument to measure a 4wire resistance one at a time. For use with either trigger_fetch and
        fetch_one or with read_one. This enables probe current.

        :param float current:
        :param float nplc:

        :returns: None
        """
        self.k2461.write('*rst')
        self.k2461.write('sour:func curr')
        self.k2461.write('sens:func "volt"')
        self.k2461.write(f'sens:volt:rang:auto on')
        self.k2461.write('sens:volt:rsen on')
        self.k2461.write(f'sens:volt:nplc {nplc}')
        self.k2461.write(f'sour:curr {current}')
        self.k2461.write('sour:curr:range:auto on')
        self.k2461.write(f'sour:curr:vlim {vlim}')
        self.k2461.write('outp on')

    # For use when reading one value from Source meter at a time in 2 wire mode.
    # Applies current and measures voltage required to apply that current
    # nplc: 0.02, 0.2, 1, 10, 100, 200. 0.2 is "fast".
    def enable_2_wire_probe(self, current, nplc=2, vlim=1):
        """
        Prepares the instrument to measure a 2wire resistance one at a time. For use with either trigger_fetch and
        fetch_one or with read_one. This enables probe current.

        :param float current: probing current in amps
        :param float nplc: number of powerline cycles to measure for

        :returns: None
        """
        self.k2461.write('*rst')
        self.k2461.write('sour:func curr')
        self.k2461.write('sens:func "volt"')
        self.k2461.write('sens:volt:rang:auto on')
        self.k2461.write('sens:volt:rsen off')
        self.k2461.write(f'sens:volt:nplc {nplc}')
        self.k2461.write(f'sour:curr {current}')
        self.k2461.write('sour:curr:range:auto on')
        self.k2461.write(f'sour:curr:vlim {vlim}')
        self.k2461.write('outp on')

    def trigger(self):
        """
        Starts applying current and initiates the measurement set up using measure_n. Also use read_buffer then
        disable_probe_current.

        :returns: None
        """
        # self.k2461.write('init')
        self.k2461.write('outp on')
        self.k2461.write('trac:trig "mybuffer"')
        self.k2461.write('*wai')

    def trigger_before_fetch(self):
        """
        Triggers a single measurement for reading back off later. Use for higher synchronicity between instruments.
        Use fetch_one to get the data. See also: read_one

        :returns: None
        """
        self.k2461.write('trac:trig "defbuffer1"')
        self.k2461.write('*wai')

    def read_buffer(self, num):
        """
        Reads a specified number of points from the buffer and returns the data as numpy arrays

        :param float num: number of points to be read

        :returns: time relative to trigger, voltage, current. Use v/c to resistance.
        :rtype: (np.ndarray, np.ndarray, np.ndarray)
        """
        self.k2461.write('outp off')
        try:
            data = np.array(self.k2461.query_ascii_values(f'trac:data? 1, {num}, "mybuffer", sour, read, rel'))
            t = data[2::3]
            v = data[1::3]
            c = data[0::3]
            return t, v, c
        except:
            print('could not read data from K2461')
            return np.array([]), np.array([]), np.array([])

    def read_one(self):
        """
        Measures, reads and returns a single value from the instrument. For use with enable_2_wire_probe and
        enable_4_wire_probe. To measure and read separately, see trigger_fetch and fetch_one

        :returns: current, voltage. Do v/c for resistance
        :rtype: (float, float)
        """
        data = np.array([self.k2461.query_ascii_values('read? "defbuffer1", sour, read')])
        # print(data)
        cur = data[0][0]
        vol = data[0][1]
        return cur, vol

    def fetch_one(self):
        """
        Reads and returns a single value from the instrument. For use with trigger_fetch and either enable_2_wire_probe
        or enable_4_wire_probe.

        :returns: current, voltage. Do v/c for resistance
        :rtype: (float, float)
        """
        data = self.k2461.query_ascii_values('fetch? "defbuffer1", sour, read')
        return data[1], data[0]

    def enable_probe_current(self):
        """
        Stops the instrument from outputting current. Same as hitting "output on/off" on the front IO.

        :returns: None
        """
        self.k2461.write('outp on')

    def get_trace(self, num, check_period=10):
        """
        Retrieves the measured values after an output sweep such as delta pulsing. It does this by waiting a while then
        checking whether the instrument is still armed but waiting for a trigger event. If this is detected, the abort
        command is sent and the data is retrieved.

        :param float delay: Time to wait between checking the instrument's state in seconds

        :returns: the trace data
        :rtype: np.ndarray
        """
        start_time = time.time()
        running = 1
        while running:
            time.sleep(check_period)
            status = int(self.k2461.query_ascii_values('*STB?')[0])
            state = format(status, '#08b')
            # print(status)
            qsb = state[-4] == '1'
            msb = state[-1] == '1'
            if msb or qsb:
                running = False
            print(f'time elapsed: {time.time() - start_time}')
        print('Measurement Finished, reading data')
        time.sleep(1)
        data = np.array(self.k2461.query_ascii_values(f'trac:data? 1, {num}, "defbuffer1", sour, read, rel'))
        t = data[2::3]
        v = data[1::3]
        c = data[0::3]
        self.k2461.write('*CLS')
        return t, v, c

    def disable_probe_current(self):
        """
        Stops the instrument from outputting current. Same as hitting "output on/off" on the front IO.

        :returns: None
        """
        self.k2461.write('outp off')

    def close(self):
        """
        Closes the instrument connection, i.e. frees the port up for other applications/threads. Also disables output.

        :returns: None
        """
        self.k2461.write('*rst')
        self.k2461.write('*sre 0')
        self.k2461.write('outp off')
        self.k2461.close()

    def BEEP(self, Hz=500, length=1):
        """ Alex's Beeper
    
        DO NOT REMOVE
    
        OF VITAL IMPORTANCE
        :returns: None
        """
        self.k2461.write(f'SYST:BEEPer {Hz}, {length}')
        

class K6221:
    """
    Keithley 6221 control interface using Ethernet, RS232 or GPIB connection, designed for use in delta pulsing or
    second harmonic measurements
    """

    def connect_ethernet(self, IP='192.168.0.12'):
        """
        Connect to the instrument using ethernet port

        :param str IP: IP address of the instrument

        :returns: None
        """
        self.rm = pyvisa.ResourceManager('@ivi')
        self.K6221 = self.rm.open_resource(f'TCPIP::{IP}::1394::SOCKET', write_termination='\r\n',
                                           read_termination='\n', timeout=10000)
        self.K6221.write('source:sweep:abort')
        self.K6221.write('*rst')
        self.K6221.write('*cls')
        # self.K6221.timeout = 10000

    def connect_GPIB(self, addr=12):
        """
        Connect to the instrument using GPIB connector

        :param int addr: address of the instrument

        :returns: None
        """
        self.addr = addr
        self.rm = pyvisa.ResourceManager('@ivi')
        self.K6221 = self.rm.open_resource(f'GPIB0::{self.addr}::INSTR', read_termination='\n', timeout=10000)
        self.K6221.write('abort')
        self.K6221.write('*rst')
        self.K6221.write('*cls')
        self.K6221.write('display:enable 0')
        self.send_to_2182A('display:enable 0')

    def connect_RS232(self, port):
        """
        Connects to device using RS232 port with baud rate of 19.2K

        :param int port: The COM port number e.g. for COM16, port = 16

        :returns: None
        """
        rm = pyvisa.ResourceManager('@ivi')
        self.K6221 = rm.open_resource(f'COM{port}', baud_rate=19200)
        self.K6221.close()
        self.K6221.open()
        self.K6221.baud_rate = 19200
        self.K6221.timeout = 10000
        self.K6221.write_termination = '\r\n'
        self.K6221.read_termination = '\r\n'
        self.K6221.write('*rst')
        self.K6221.write('*cls')
        print('connected to: ', self.K6221.query('*IDN?'))

    def set_compliance(self, volts):
        """
        Sets compliance voltage

        :param float volts: Compliance limit in volts

        :returns:
        """
        self.K6221.write(f'source:current:compliance {volts}')

    def configure_pulse(self, width, count, n_low=2):
        """
        Configure a single value pulse train for use with pulse delta measurements. Sense delay is always set to
        half the width. You must set the output amplitude elsewhere (not implemented, we used front panel control).
        Use before arm_pulse_sweep, trigger and get_trace.

        :param float width: duration of the pulse high stage in seconds
        :param int count: number of pulses to send
        :param int n_low: number of measurements to take at the low value (1 or 2).

        :returns: None
        """
        self.K6221.write(f'source:pdelta:sweep on')
        self.K6221.write(f'source:pdelta:width {width}')
        self.K6221.write(f'source:pdelta:count {count}')
        self.K6221.write(f'source:pdelta:lmeasure {n_low}')
        self.K6221.write(f'source:pdelta:sdelay {width / 2}')

    def configure_linear_sweep(self, start, stop, step, delay, count, ranging='best'):
        """
        Configures the instrument to send a set of pules with linearly increasing amplitudes. Cannot be used to do
        decreasing sweep. For this, use configure_custom_sweep.
        Use before arm_pulse_sweep, trigger and get_trace.

        :param float start: first current amplitude in Amps
        :param float stop: last current amplitude in Amps
        :param float step: current step amount in Ampls
        :param float delay: delay between pulses in seconds
        :param int count: number of repeats of the sweep to measure
        :param str ranging: ranging mode ['auto', 'best', 'fixed'].

        :returns: None
        """
        self.K6221.write(f'source:sweep:spacing linear')
        self.K6221.write(f'source:current:start {start}')
        self.K6221.write(f'source:current:stop {stop}')
        self.K6221.write(f'source:current:step {step}')
        self.K6221.write(f'source:delay {delay}')
        self.K6221.write(f'source:sweep:count {count}')
        self.K6221.write(f'source:sweep:ranging {ranging}')

    def configure_custom_sweep(self, sweep_list, delay, compliance, count, bias=0.0, ranging='best'):
        """
        Configures the instrument to send a set of pules with arbitrary amplitudes.
        Use before arm_pulse_sweep, trigger and get_trace.

        :param list-like sweep_list: list of pulse amplitudes in Amps
        :param float delay: delay between pulses in seconds
        :param float compliance: compliance limit in volts
        :param int count: number of repeats of the sweep to measure
        :param float bias: offset for the lo values (0.0 typically)
        :param str ranging: ranging mode ['auto', 'best', 'fixed'].

        :returns: None
        """
        self.K6221.write(f'source:current {bias}')
        self.K6221.write('source:sweep:spacing list')
        # self.K6221.write(f'source:delay {delay}')  # cycle time for lin/log sweeps
        self.K6221.write(f'source:list:delay {delay}')  # cycle time list for custom
        self.K6221.write(f'source:list:current {sweep_list[0]}')
        for x in sweep_list[1:]:
            self.K6221.write(f'source:list:current:append {x}')
            self.K6221.write(f'source:list:delay:append {delay}')
        self.K6221.write(f'source:list:compliance {compliance}')
        self.K6221.write(f'source:sweep:count {count}')
        self.K6221.write(f'source:sweep:ranging {ranging}')
        self.K6221.write('source:sweep:cabort off')

    def configure_switching_custom_sweep(self, sweep_list, delay_list, compliance, count, bias=0, ranging='best'):
        """
        Configures the instrument to send a set of pules with arbitrary amplitudes but also with arbitrary delays
        between pulses. Use before arm_pulse_sweep, trigger and get_trace.

        :param list-like sweep_list: list of pulse amplitudes in Amps
        :param list-like delay_list: list of corresponding delays between pulses
        :param float compliance: compliance limit in volts
        :param int count: number of repeats of the sweep to measure
        :param float bias: offset for the lo values (0.0 typically)
        :param str ranging: ranging mode ['auto', 'best', 'fixed'].

        :returns: None
        """
        self.K6221.write(f'source:current {bias}')
        self.K6221.write('source:sweep:spacing list')
        # Create list with first value then append all other values in the loop.
        self.K6221.write(f'source:list:current {sweep_list[0]}')
        for x in sweep_list[1::]:
            self.K6221.write(f'source:list:current:append {x}')
        self.K6221.write(f'source:list:delay {delay_list[0]}')
        for y in delay_list[1::]:
            self.K6221.write(f'source:list:delay:append {y}')
        self.K6221.write(f'source:list:compliance {compliance}')
        self.K6221.write(f'source:sweep:count {count}')
        self.K6221.write(f'source:sweep:ranging {ranging}')
        self.K6221.write('source:sweep:cabort off')

    def arm_pulse_sweep(self):
        """
        Disables the screens to reduce jitter and arms the pulse sweeping ready for a trigger event.
        Use after configuring a pulse sweep and before trigger. See also: get_trace.

        :returns: None
        """
        self.K6221.write('display:enable 0')
        self.send_to_2182A('display:enable 0')
        self.K6221.write(f'source:pdelta:arm')

    def configure_diff_conductance(self, start, stop, step, delta, delay):
        """
        Prepares the instrument for differential conductance measurement sweeps.
        Use with arm_diff_cond, trigger and get_trace.

        :param float start: starting current (Amps)
        :param float stop: stopping current (Amps)
        :param float step: current steps (Amps)
        :param float delta: delta value (Amps) see manual for more info
        :param float delay: time between measurements. Current is always on for this measurement so keep it short.

        :returns: None
        """
        self.K6221.write(f'source:dcon:start {start}')
        self.K6221.write(f'source:dcon:step {step}')
        self.K6221.write(f'source:dcon:stop {stop}')
        self.K6221.write(f'source:dcon:delta {delta}')
        self.K6221.write(f'source:dcon:delay {delay}')

    def arm_diff_cond(self):
        """
        Disables the screens to reduce jitter and arms the diff conductance sweeping ready for a trigger event.
        Use after configuring a diff cond sweep and before trigger. See also: get_trace.
        :returns:
        """
        self.K6221.write('display:enable 0')
        self.send_to_2182A('display:enable 0')
        self.K6221.write(f'source:dcon:arm')

    def trigger(self):
        """
        Triggers whatever output has been configured. Does not work with waves.

        :returns: None
        """
        self.K6221.write('INIT:IMM')

    def get_trace_fast(self):
        is_finished = False
        while not is_finished:
            time.sleep(0.1)
            state = int(self.K6221.query('status:operation:cond?'))
            is_finished = bin(state)[-2] == '1'
            sweeping = bin(state)[-4] == '1'
            aborted = bin(state)[-3] == '1'
            if not sweeping:
                print('Not sweeping or done?')
            if aborted:
                is_finished = True
                print('apparently this sweep is aborted, script is ending measurement.')
        data = self.K6221.query_ascii_values('trace:data?')
        return np.array(data)

    def get_trace(self, delay=60):
        """
        Retrieves the measured values after an output sweep such as delta pulsing. It does this by waiting a while then
        checking whether the instrument is still armed but waiting for a trigger event. If this is detected, the abort
        command is sent and the data is retrieved.

        :param float delay: Time to wait between checking the instrument's state in seconds

        :returns: the trace data
        :rtype: np.ndarray
        """
        start_time = time.time()
        is_finished = False
        while not is_finished:
            time.sleep()
            state = int(self.K6221.query('status:operation:cond?'))
            is_finished = bin(state)[-2] == '1'
            sweeping = bin(state)[-4] == '1'
            aborted = bin(state)[-3] == '1'
            if not sweeping:
                print('Not sweeping or done?')
            if aborted:
                is_finished = True
                print('apparently this sweep is aborted, script is ending measurement.')
            print(f'state: {state}' + f'    time elapsed: {time.time() - start_time}')
        print('Measurement Finished, Aborting wave')
        self.K6221.write(f'source:sweep:abort')
        time.sleep()
        print('reading data')
        data = self.K6221.query_ascii_values('trace:data?')
        return np.array(data)

    def set_sense_chan_and_range(self, channel, volt_range):
        """
        Sets the 2182A's measurement channel and specifies the measurement range

        :param int channel: measurement channel (1 or 2)
        :param float volt_range: maximum voltage amplitude in Volts

        :returns: None
        """
        channel_comm = f'sense:channel {channel}'
        self.K6221.write(f'system:communicate:serial:send "{channel_comm}"')

        if volt_range == 'Auto' or volt_range == 'auto':
            range_comm = f'sense:voltage:channel{channel}:range:auto on'
            self.send_to_2182A(range_comm)
        else:
            range_comm = f'sense:voltage:channel{channel}:range:auto off'
            self.send_to_2182A(range_comm)
            range_comm = f'sense:voltage:channel{channel}:range {volt_range}'
            self.send_to_2182A(range_comm)

    def send_to_2182A(self, string):
        """
        Command used to send a command to the 2182A if attached.

        :param str string: The command string to be send

        :returns: None
        """
        self.K6221.write(f'system:communicate:serial:send "{string}"')

    def sine_wave(self, hz, ma, duty=50):
        """
        Prepare the instrument to produce a sine wave output. Use with wave_output_on and wave_output_off

        :param hz: Frequency in Hz
        :param float ma: peak - DC amplitude in Milliamps (Ip not Ipp or Irms)
        :param duty: Duty cycle def: 50%

        :returns: None
        """
        self.K6221.write('*RST')
        self.K6221.write('SOUR:WAVE:FUNC SIN')
        self.K6221.write(f'SOUR:WAVE:FREQ {hz}')
        self.K6221.write(f'SOUR:WAVE:AMPL {ma * 1e-3}')
        self.K6221.write('SOUR:WAVE:ARM')

    def set_phase_marker(self, enable=1, phase=0, pin=4):
        """
        Enable/disable the phase marker and set the phase and output pin

        :param bool enable: enable (1) or disable (0) the phase marker.
        :param float phase: The phase that the marker pulse is output at (in degrees)
        :param int pin: desired output pin on the trigger connector. default=4

        :returns: None
        """
        self.K6221.write(f'SOUR:WAVE:PMARK:OLIN {pin}')
        self.K6221.write(f'SOUR:WAVE:PMARK:LEV {phase}')
        self.K6221.write(f'SOUR:WAVE:PMARK:STAT {enable}')

    # Current in mA and Freq in Hz duty in %
    def square_wave(self, hz, ma, duty=50):
        """
        Prepare a square wave output. Use with wave_output_on and wave_output_off

        :param float hz: desired frequency in Hz
        :param float ma: desired amplitude in milliAmps
        :param float duty: Duty cycle def: 50%

        :returns: None
        """
        self.K6221.write('*RST')
        self.K6221.write('SOUR:WAVE:FUNC SQU')
        self.K6221.write(f'SOUR:WAVE:FREQ {hz}')
        self.K6221.write(f'SOUR:WAVE:AMPL {ma * 1e-3}')
        self.K6221.write(f'SOUR:WAVE:DCYC {duty}')

    def wave_output_on(self):
        """
        Enables the output for the wave prepared using sine_wave or square_wave

        :returns: None
        """
        self.K6221.write('SOUR:WAVE:ARM')
        self.K6221.write('SOUR:WAVE:INIT')

    def wave_output_off(self):
        """
        Disables current output

        :returns:
        """
        self.K6221.write('SOUR:WAVE:ABOR')

    def close(self):
        """
        Closes the instrument connection, i.e. frees the port up for other applications/threads. Also disables output.

        :returns: None
        """
        self.K6221.write('abort')
        self.K6221.write('display:enable 1')
        self.K6221.close()
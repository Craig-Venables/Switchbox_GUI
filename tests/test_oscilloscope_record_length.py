class DummyScope:
    def __init__(self):
        self.last_points = None

    def set_record_length(self, points):
        self.last_points = points
        return points


def test_configure_record_length_calls_scope():
    from Equipment.managers.oscilloscope import OscilloscopeManager

    mgr = OscilloscopeManager(auto_detect=False)
    dummy = DummyScope()
    mgr.scope = dummy

    applied = mgr.configure_record_length(12345)

    assert dummy.last_points == 12345
    assert applied == 12345


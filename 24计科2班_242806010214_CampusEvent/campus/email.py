class MockEmailSender:
    """Mock sender for CR-02; no real network access."""

    def __init__(self, fail=False):
        self.fail = fail

    def send(self, recipient, subject, content):
        if self.fail:
            raise RuntimeError("mock email failure")
        return True

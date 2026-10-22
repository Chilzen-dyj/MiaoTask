class Stopped(Exception):
    pass


class NeedsAttention(Exception):
    def __init__(self, message, *, kind='attention', evidence_saved=False):
        super().__init__(message)
        self.kind = kind
        self.evidence_saved = evidence_saved


class TaskUnavailable(Exception):
    """A terminal condition for this task, rather than a reason to retry it."""
    pass

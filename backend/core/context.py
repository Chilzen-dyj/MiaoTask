"""Execution identity shared by workers, drivers and structured log routing."""
from contextvars import ContextVar
from functools import wraps

workspace_scope = ContextVar('workspace_scope', default='')


def device_scoped(method):
    @wraps(method)
    def run(self, *args, **kwargs):
        token = workspace_scope.set(getattr(self, 'workspace_id', ''))
        try:
            return method(self, *args, **kwargs)
        finally:
            workspace_scope.reset(token)
    return run

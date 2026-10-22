"""Activity lifecycle contract composed from the preserved session machinery.

Implement entry, parsing, actions and verification in an application package.
Core owns the loop, identity tracking, control and bounded return budget.
"""
from abc import ABC, abstractmethod
from backend.core.execution.session import Session
from backend.core.execution.retry import TaskTracking
from backend.core.execution.loop import SessionLoop
from backend.core.execution.navigator import Navigator


class Activity(SessionLoop, Navigator, TaskTracking, Session, ABC):
    claim_actions = frozenset()
    external_apps = ()

    @abstractmethod
    def default_config(self):
        pass

    @abstractmethod
    def parse_tasks(self, nodes, width, height):
        pass

    @abstractmethod
    def is_task_list(self, nodes):
        pass

    @abstractmethod
    def execute(self, task, before):
        pass

    @abstractmethod
    def verify(self, task, before, after, explicit=False):
        pass

    def task_assets(self, screen, center_y):
        return []

    def guard(self, screen):
        self.assert_instance(screen)
        from backend.core.execution.guard import check_attention
        check_attention(self, screen)

    def setup(self):
        pass

    def teardown(self):
        pass

    def run(self, auto_open=False):
        try:
            self.setup()
            return super().run(auto_open)
        finally:
            self.teardown()

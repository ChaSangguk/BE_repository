"""Compatibility imports for the original debate views module."""

from .part_c.joined.views import DebateCursorPagination, JoinedDebateListView
from .part_c.result.views import DebateResultView
from .part_c.stance.views import MyStanceEventListView, MyStanceView
from .part_c.timing.views import DebateTimingView


__all__ = [
    "DebateCursorPagination",
    "DebateResultView",
    "DebateTimingView",
    "JoinedDebateListView",
    "MyStanceEventListView",
    "MyStanceView",
]

"""Errors raised by the domain engine."""

from __future__ import annotations


class PlannerError(Exception):
    """Base class for domain engine failures."""


class PlannerConfigError(PlannerError, ValueError):
    """Settings or template values outside their allowed range."""


class DayNotEditableError(PlannerError):
    """Days outside the window, past days and eaten days cannot change."""


class SwapRejectedError(PlannerError):
    """The requested dinner breaks a hard rule for that day."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

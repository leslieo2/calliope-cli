from __future__ import annotations


class CalliopeError(Exception):
    """Base exception for Calliope CLI."""


class ConfigError(CalliopeError):
    """Raised when configuration file is invalid."""


class AgentSpecError(CalliopeError):
    """Raised when agent specification is invalid."""

"""
Agent Project Recovery - Core Module

Lightweight state persistence for AI agents.
Save project state before interruption, restore instantly on resume.

License: MIT
"""

from .core import ProjectRecovery
from .version import __version__

__all__ = ["ProjectRecovery", "__version__"]

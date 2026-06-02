"""
Agent Project Recovery - Hook Integration

Standard hook functions for integrating with AI agent frameworks.

License: MIT
"""

import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .core import ProjectRecovery, _SYSTEM_MSG_PREFIXES


def create_hooks(recovery: ProjectRecovery) -> Dict[str, Callable]:
    """
    Create standard hook functions for an AI agent framework.
    
    Usage:
        recovery = ProjectRecovery("~/.my-agent/project-state.yaml")
        hooks = create_hooks(recovery)
        
        # Register hooks in your framework
        agent.on_session_start(hooks["on_session_start"])
        agent.post_tool_call(hooks["post_tool_call"])
        agent.pre_llm_call(hooks["pre_llm_call"])
        agent.on_session_end(hooks["on_session_end"])
    
    Returns:
        Dict with keys: on_session_start, post_tool_call, pre_llm_call, on_session_end
    """
    
    # Track injection state
    _injected_this_session = False
    # Track user messages for session summary
    _session_user_messages: List[str] = []
    _last_user_msg: str = ""
    
    def on_session_start(session_id: str, **kwargs) -> None:
        """Called when a new session starts."""
        nonlocal _injected_this_session, _session_user_messages, _last_user_msg
        _injected_this_session = False
        _session_user_messages = []
        _last_user_msg = ""
        recovery.record_session_start(session_id)
    
    def post_tool_call(
        tool: str,
        args: Dict[str, Any],
        success: bool,
        summary: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Called after every tool invocation."""
        recovery.record_tool_call(tool, args, success, summary)
        
        # Sync todo state if todo tool was used
        if tool == "todo" and success:
            _sync_todo_from_args(recovery, args)
    
    def pre_llm_call(
        messages: List[Dict[str, Any]],
        user_message: Optional[str] = None,
        **kwargs,
    ) -> Optional[Dict[str, str]]:
        """
        Called before every LLM API call.
        
        Extracts and tracks user messages for session summary.
        Returns context dict to inject, or None.
        """
        nonlocal _injected_this_session, _session_user_messages, _last_user_msg
        
        # Extract last user message
        user_msg = user_message or ""
        if not user_msg and messages:
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    user_msg = msg.get("content", "")
                    if isinstance(user_msg, list):
                        # Multi-part message
                        user_msg = " ".join(
                            p.get("text", "") for p in user_msg
                            if isinstance(p, dict) and p.get("type") == "text"
                        )
                    break
        
        # Track user messages (filter system messages, deduplicate)
        if user_msg and user_msg != _last_user_msg and len(user_msg) > 5:
            _last_user_msg = user_msg
            if not user_msg.startswith(_SYSTEM_MSG_PREFIXES):
                _session_user_messages.append(user_msg[:200])
                if len(_session_user_messages) > 5:
                    _session_user_messages.pop(0)
        
        # Only inject once per session
        if _injected_this_session:
            return None
        
        # Check freshness
        if not recovery.is_fresh():
            return None
        
        # Generate summary
        summary = recovery.generate_recovery_summary()
        
        # Only inject if there's meaningful content
        if not summary or len(summary) < 50:
            return None
        
        _injected_this_session = True
        return {"context": summary}
    
    def on_session_end(
        session_id: str,
        completed: bool = True,
        **kwargs,
    ) -> None:
        """Called when session ends. Passes tracked user messages."""
        recovery.record_session_end(
            session_id,
            completed=completed,
            user_messages=_session_user_messages[-5:] if _session_user_messages else None,
        )
    
    return {
        "on_session_start": on_session_start,
        "post_tool_call": post_tool_call,
        "pre_llm_call": pre_llm_call,
        "on_session_end": on_session_end,
    }


def _sync_todo_from_args(recovery: ProjectRecovery, args: Dict[str, Any]) -> None:
    """
    Sync todo state from todo tool arguments.
    
    This is a best-effort parser for common todo tool formats.
    Adapt this for your specific todo tool implementation.
    """
    action = args.get("action", "")
    
    # Handle common todo actions
    if action in ("create", "update", "merge"):
        todos = args.get("todos", [])
        if todos:
            recovery.sync_todo_state(todos)
    
    elif action == "complete":
        # After completion, we need to check if there are remaining tasks
        # This requires reading the current todo list from the framework
        # For now, we'll just clear current_task if it was the completed one
        pass


class HermesIntegration:
    """
    Integration example for Hermes Agent.
    
    Usage in hermes-core/hooks.py:
    
        from agent_recovery.hooks import HermesIntegration
        
        _recovery = HermesIntegration("~/.hermes/project-state.yaml")
        
        def on_session_start(session_id, **_):
            _recovery.on_session_start(session_id)
        
        def post_tool_call(tool, args, success, **_):
            _recovery.post_tool_call(tool, args, success)
        
        # ... etc
    """
    
    def __init__(self, state_path: str):
        self.recovery = ProjectRecovery(state_path)
        self.hooks = create_hooks(self.recovery)
        self._recovery_injected = False
        self._session_user_messages: List[str] = []
        self._last_user_msg: str = ""
    
    def on_session_start(self, session_id: str, **kwargs) -> None:
        """Hermes on_session_start hook."""
        self._recovery_injected = False
        self._session_user_messages = []
        self._last_user_msg = ""
        self.hooks["on_session_start"](session_id, **kwargs)
    
    def post_tool_call(
        self,
        tool: str,
        args: Dict[str, Any],
        success: bool,
        **kwargs,
    ) -> None:
        """Hermes post_tool_call hook."""
        self.hooks["post_tool_call"](tool, args, success, **kwargs)
    
    def pre_llm_call(
        self,
        messages: List[Dict[str, Any]],
        user_message: Optional[str] = None,
        **kwargs,
    ) -> Optional[Dict[str, str]]:
        """
        Hermes pre_llm_call hook.
        
        Extracts user messages for tracking, filters system messages.
        Returns context dict for injection, or None.
        """
        # Extract and track user message
        user_msg = user_message or ""
        if not user_msg and messages:
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    user_msg = msg.get("content", "")
                    if isinstance(user_msg, list):
                        user_msg = " ".join(
                            p.get("text", "") for p in user_msg
                            if isinstance(p, dict) and p.get("type") == "text"
                        )
                    break
        
        if user_msg and user_msg != self._last_user_msg and len(user_msg) > 5:
            self._last_user_msg = user_msg
            if not user_msg.startswith(_SYSTEM_MSG_PREFIXES):
                self._session_user_messages.append(user_msg[:200])
                if len(self._session_user_messages) > 5:
                    self._session_user_messages.pop(0)
        
        if self._recovery_injected:
            return None
        
        result = self.hooks["pre_llm_call"](messages, user_message=user_message, **kwargs)
        if result:
            self._recovery_injected = True
        return result
    
    def on_session_end(
        self,
        session_id: str,
        completed: bool = True,
        **kwargs,
    ) -> None:
        """Hermes on_session_end hook. Passes tracked user messages."""
        self.recovery.record_session_end(
            session_id,
            completed=completed,
            user_messages=self._session_user_messages[-5:] if self._session_user_messages else None,
        )


class ClaudeCodeIntegration:
    """
    Integration example for Claude Code.
    
    Usage:
        from agent_recovery.hooks import ClaudeCodeIntegration
        
        recovery = ClaudeCodeIntegration("~/.claude-code/project-state.yaml")
        
        # In your tool wrapper
        def tool_call(tool_name, args):
            result = execute_tool(tool_name, args)
            recovery.record_tool_call(tool_name, args, success=True)
            return result
    """
    
    def __init__(self, state_path: str):
        self.recovery = ProjectRecovery(state_path)
    
    def record_tool_call(
        self,
        tool: str,
        args: Dict[str, Any],
        success: bool,
        summary: Optional[str] = None,
    ) -> None:
        """Record a tool call."""
        self.recovery.record_tool_call(tool, args, success, summary)
    
    def get_recovery_context(self) -> Optional[str]:
        """
        Get recovery context for injection.
        
        Call this before generating a response.
        Returns None if no context available.
        """
        if not self.recovery.is_fresh():
            return None
        
        summary = self.recovery.generate_recovery_summary()
        if summary and len(summary) > 50:
            return summary
        return None
    
    def set_state(self, field: str, value: Optional[str]) -> None:
        """Set state explicitly."""
        self.recovery.set_state(field, value, source="explicit_statement")

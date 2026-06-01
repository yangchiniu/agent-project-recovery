"""
Example: Integrating Agent Project Recovery with Hermes Agent

This example shows how to integrate the recovery system into Hermes Agent's hook system.

License: MIT
"""

import logging
from typing import Any, Dict, List, Optional

from agent_recovery import ProjectRecovery
from agent_recovery.hooks import create_hooks

# Configure logging
logger = logging.getLogger(__name__)


class HermesRecoveryIntegration:
    """
    Integration class for Hermes Agent.
    
    Usage:
        # In hermes-core/hooks.py
        from examples.hermes_integration import HermesRecoveryIntegration
        
        _recovery = HermesRecoveryIntegration("~/.hermes/project-state.yaml")
        
        # Then use _recovery methods in your hooks
    """
    
    def __init__(self, state_path: str = "~/.hermes/project-state.yaml"):
        self.recovery = ProjectRecovery(state_path)
        self.hooks = create_hooks(self.recovery)
        self._recovery_injected = False
        
        logger.info("HermesRecoveryIntegration initialized: %s", state_path)
    
    def on_session_start(self, session_id: str, **kwargs) -> None:
        """
        Hermes on_session_start hook.
        
        Call this when a new session starts.
        """
        self._recovery_injected = False
        self.hooks["on_session_start"](session_id, **kwargs)
        logger.debug("Recovery: session started %s", session_id)
    
    def post_tool_call(
        self,
        tool: str,
        args: Dict[str, Any],
        success: bool,
        **kwargs,
    ) -> None:
        """
        Hermes post_tool_call hook.
        
        Call this after every tool invocation.
        """
        self.hooks["post_tool_call"](tool, args, success, **kwargs)
        
        # Log significant events
        if tool == "todo" and success:
            logger.debug("Recovery: todo state synced")
    
    def pre_llm_call(
        self,
        messages: List[Dict[str, Any]],
        **kwargs,
    ) -> Optional[Dict[str, str]]:
        """
        Hermes pre_llm_call hook.
        
        Call this before every LLM API call.
        Returns context dict for injection, or None.
        """
        if self._recovery_injected:
            return None
        
        result = self.hooks["pre_llm_call"](messages, **kwargs)
        
        if result:
            self._recovery_injected = True
            logger.info(
                "Recovery: injected context (age=%.0fs)",
                self.recovery.get_age_seconds(),
            )
        
        return result
    
    def on_session_end(
        self,
        session_id: str,
        completed: bool = True,
        **kwargs,
    ) -> None:
        """
        Hermes on_session_end hook.
        
        Call this when session ends.
        """
        self.hooks["on_session_end"](session_id, completed, **kwargs)
        logger.debug("Recovery: session ended %s (completed=%s)", session_id, completed)


# ── Example: Complete integration in hooks.py ─────────────────────────────

"""
# In ~/.hermes/plugins/hermes-core/hooks.py

from examples.hermes_integration import HermesRecoveryIntegration

# Initialize recovery (at module level)
_recovery = HermesRecoveryIntegration("~/.hermes/project-state.yaml")

# In on_session_start hook
def on_session_start(session_id: str, **_) -> None:
    _recovery.on_session_start(session_id)
    # ... other initialization ...

# In post_tool_call hook
def post_tool_call(
    tool: str,
    args: Dict[str, Any],
    success: bool,
    **_,
) -> None:
    _recovery.post_tool_call(tool, args, success)
    # ... other post-tool logic ...

# In pre_llm_call hook
def pre_llm_call(
    messages: list = None,
    **_,
) -> Optional[dict]:
    # ... other pre-LLM logic ...
    
    # Recovery injection (one-shot)
    recovery_context = _recovery.pre_llm_call(messages or [])
    if recovery_context:
        return recovery_context
    
    return None

# In on_session_end hook
def on_session_end(session_id: str, **_) -> None:
    _recovery.on_session_end(session_id)
    # ... other cleanup ...
"""


# ── Example: Standalone testing ───────────────────────────────────────────

def test_integration():
    """Test the integration without Hermes."""
    import tempfile
    import os
    
    # Create temporary state file
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        state_path = f.name
    
    try:
        # Initialize
        integration = HermesRecoveryIntegration(state_path)
        
        # Simulate session start
        integration.on_session_start("test-session-001")
        
        # Simulate tool calls
        integration.post_tool_call(
            tool="read_file",
            args={"path": "src/main.py"},
            success=True,
        )
        
        integration.post_tool_call(
            tool="terminal",
            args={"command": "pytest tests/"},
            success=True,
        )
        
        integration.post_tool_call(
            tool="todo",
            args={
                "action": "update",
                "todos": [
                    {"id": "1", "content": "Implement auth", "status": "in_progress"},
                    {"id": "2", "content": "Add tests", "status": "pending"},
                ],
            },
            success=True,
        )
        
        # Simulate pre-LLM call
        context = integration.pre_llm_call([{"role": "user", "content": "Continue"}])
        
        if context:
            print("✓ Recovery context injected:")
            print(context["context"])
        else:
            print("✗ No context injected")
        
        # Simulate session end
        integration.on_session_end("test-session-001", completed=True)
        
        print("\n✓ Integration test passed")
        
    finally:
        # Cleanup
        os.unlink(state_path)


if __name__ == "__main__":
    test_integration()

"""
Example: Standalone Usage of Agent Project Recovery

This example shows how to use the recovery system independently,
without any specific agent framework.

License: MIT
"""

import tempfile
import os
from pathlib import Path

from agent_recovery import ProjectRecovery


def example_basic_usage():
    """Basic usage example."""
    print("=== Basic Usage Example ===\n")
    
    # Create a temporary state file for this example
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        state_path = f.name
    
    try:
        # Initialize recovery
        recovery = ProjectRecovery(state_path)
        
        # Record session start
        recovery.record_session_start("example-session-001")
        
        # Record some tool calls
        recovery.record_tool_call(
            tool="read_file",
            args={"path": "src/auth/jwt.py"},
            success=True,
        )
        
        recovery.record_tool_call(
            tool="write_file",
            args={"path": "src/auth/jwt.py", "content": "..."},
            success=True,
        )
        
        recovery.record_tool_call(
            tool="terminal",
            args={"command": "pytest tests/test_jwt.py"},
            success=True,
        )
        
        # Set state explicitly
        recovery.set_state("goal", "Implement user authentication", source="explicit_statement")
        recovery.set_state("current_task", "Debugging JWT validation", source="explicit_statement")
        recovery.set_state("branch", "feature/auth", source="explicit_statement")
        
        # Generate and print recovery summary
        summary = recovery.generate_recovery_summary()
        print("Recovery Summary:")
        print(summary)
        
        # Record session end
        recovery.record_session_end("example-session-001", completed=True)
        
        print("\n✓ Basic usage example completed")
        
    finally:
        os.unlink(state_path)


def example_todo_integration():
    """Example with todo integration."""
    print("\n=== Todo Integration Example ===\n")
    
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        state_path = f.name
    
    try:
        recovery = ProjectRecovery(state_path)
        
        # Simulate todo tool usage
        todos = [
            {"id": "1", "content": "Implement JWT validation", "status": "in_progress"},
            {"id": "2", "content": "Add refresh token", "status": "pending"},
            {"id": "3", "content": "Write tests", "status": "pending"},
        ]
        
        # Record todo tool call
        recovery.record_tool_call(
            tool="todo",
            args={"action": "update", "todos": todos},
            success=True,
        )
        
        # Sync todo state
        recovery.sync_todo_state(todos)
        
        # Generate summary
        summary = recovery.generate_recovery_summary()
        print("Recovery Summary with Todo:")
        print(summary)
        
        print("\n✓ Todo integration example completed")
        
    finally:
        os.unlink(state_path)


def example_state_management():
    """Example of state management operations."""
    print("\n=== State Management Example ===\n")
    
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        state_path = f.name
    
    try:
        recovery = ProjectRecovery(state_path)
        
        # Set various state fields
        recovery.set_state("goal", "Build a web application", source="explicit_statement")
        recovery.set_state("current_task", "Setting up project structure", source="explicit_statement")
        recovery.set_state("next_task", "Implement user authentication", source="explicit_statement")
        recovery.set_state("branch", "main", source="explicit_statement")
        
        # Get current state
        state = recovery.get_state()
        print("Current state:")
        print(f"  Goal: {state['state']['goal']['value']}")
        print(f"  Current task: {state['state']['current_task']['value']}")
        print(f"  Next task: {state['state']['next_task']['value']}")
        print(f"  Branch: {state['state']['branch']['value']}")
        
        # Update current task
        recovery.set_state("current_task", "Implementing user authentication", source="explicit_statement")
        
        # Clear next task
        recovery.set_state("next_task", None, source="none")
        
        # Generate summary
        summary = recovery.generate_recovery_summary()
        print("\nUpdated summary:")
        print(summary)
        
        print("\n✓ State management example completed")
        
    finally:
        os.unlink(state_path)


def example_freshness_check():
    """Example of freshness checking."""
    print("\n=== Freshness Check Example ===\n")
    
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        state_path = f.name
    
    try:
        recovery = ProjectRecovery(state_path)
        
        # Set some state
        recovery.set_state("current_task", "Working on something", source="explicit_statement")
        
        # Check freshness
        print(f"Is fresh: {recovery.is_fresh()}")
        print(f"Age (seconds): {recovery.get_age_seconds():.2f}")
        
        # Generate summary (should include "Current:")
        summary = recovery.generate_recovery_summary()
        print(f"\nSummary contains 'Current:': {'Current:' in summary}")
        
        print("\n✓ Freshness check example completed")
        
    finally:
        os.unlink(state_path)


def example_export_import():
    """Example of export/import functionality."""
    print("\n=== Export/Import Example ===\n")
    
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        state_path = f.name
    
    try:
        recovery = ProjectRecovery(state_path)
        
        # Set some state
        recovery.set_state("goal", "Export test", source="explicit_statement")
        recovery.set_state("current_task", "Testing export", source="explicit_statement")
        
        # Export to JSON
        json_str = recovery.export_json()
        print("Exported JSON:")
        print(json_str[:200] + "..." if len(json_str) > 200 else json_str)
        
        # Create new recovery instance
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            import_path = f.name
        
        recovery2 = ProjectRecovery(import_path)
        
        # Import from JSON
        recovery2.import_json(json_str)
        
        # Verify import
        state = recovery2.get_state()
        print(f"\nImported goal: {state['state']['goal']['value']}")
        print(f"Imported current_task: {state['state']['current_task']['value']}")
        
        print("\n✓ Export/import example completed")
        
    finally:
        os.unlink(state_path)
        if 'import_path' in locals():
            os.unlink(import_path)


def example_reset():
    """Example of reset functionality."""
    print("\n=== Reset Example ===\n")
    
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        state_path = f.name
    
    try:
        recovery = ProjectRecovery(state_path)
        
        # Set some state
        recovery.set_state("goal", "Will be reset", source="explicit_statement")
        recovery.set_state("current_task", "Will be reset", source="explicit_statement")
        
        # Show before reset
        state = recovery.get_state()
        print("Before reset:")
        print(f"  Goal: {state['state']['goal']['value']}")
        print(f"  Current task: {state['state']['current_task']['value']}")
        
        # Reset
        recovery.reset()
        
        # Show after reset
        state = recovery.get_state()
        print("\nAfter reset:")
        print(f"  Goal: {state['state']['goal']['value']}")
        print(f"  Current task: {state['state']['current_task']['value']}")
        
        print("\n✓ Reset example completed")
        
    finally:
        os.unlink(state_path)


if __name__ == "__main__":
    example_basic_usage()
    example_todo_integration()
    example_state_management()
    example_freshness_check()
    example_export_import()
    example_reset()
    
    print("\n" + "="*50)
    print("All examples completed successfully!")
    print("="*50)

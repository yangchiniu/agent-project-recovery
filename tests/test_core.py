"""
Tests for Agent Project Recovery

License: MIT
"""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from agent_recovery import ProjectRecovery, __version__


@pytest.fixture
def temp_state_path():
    """Create a temporary state file path."""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        path = f.name
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def recovery(temp_state_path):
    """Create a ProjectRecovery instance."""
    return ProjectRecovery(temp_state_path)


class TestVersion:
    def test_version_exists(self):
        assert __version__ is not None
    
    def test_version_format(self):
        parts = __version__.split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()


class TestInitialization:
    def test_creates_state_file(self, temp_state_path):
        """State file should be created on initialization."""
        assert not os.path.exists(temp_state_path)
        ProjectRecovery(temp_state_path)
        assert os.path.exists(temp_state_path)
    
    def test_creates_parent_directories(self, temp_state_path):
        """Should create parent directories if they don't exist."""
        nested_path = os.path.join(temp_state_path, "nested", "state.yaml")
        ProjectRecovery(nested_path)
        assert os.path.exists(nested_path)
        # Cleanup
        os.unlink(nested_path)
        os.rmdir(os.path.dirname(nested_path))
    
    def test_empty_state_structure(self, recovery):
        """Initial state should have correct structure."""
        state = recovery.get_state()
        
        assert state["version"] == 1
        assert "updated_at" in state
        
        # State layer
        assert state["state"]["goal"]["value"] is None
        assert state["state"]["goal"]["source"] == "none"
        assert state["state"]["current_task"]["value"] is None
        assert state["state"]["next_task"]["value"] is None
        assert state["state"]["branch"]["value"] is None
        
        # Facts layer
        assert state["facts"]["files_touched"] == []
        assert state["facts"]["artifacts"] == []
        assert state["facts"]["commits"] == []
        assert state["facts"]["tools_used"] == []
        
        # Events layer
        assert state["events"] == []


class TestSessionLifecycle:
    def test_record_session_start(self, recovery):
        """Should record session start event."""
        recovery.record_session_start("sess-001")
        
        state = recovery.get_state()
        assert len(state["events"]) == 1
        
        event = state["events"][0]
        assert event["type"] == "session_started"
        assert event["session_id"] == "sess-001"
    
    def test_record_session_end(self, recovery):
        """Should record session end event."""
        recovery.record_session_start("sess-001")
        recovery.record_session_end("sess-001", completed=True)
        
        state = recovery.get_state()
        assert len(state["events"]) == 2
        
        event = state["events"][1]
        assert event["type"] == "session_ended"
        assert event["session_id"] == "sess-001"
        assert event["completed"] is True
    
    def test_record_session_end_interrupted(self, recovery):
        """Should record interrupted session."""
        recovery.record_session_start("sess-001")
        recovery.record_session_end("sess-001", completed=False)
        
        state = recovery.get_state()
        event = state["events"][1]
        assert event["completed"] is False


class TestToolCallRecording:
    def test_record_tool_call(self, recovery):
        """Should record tool call event."""
        recovery.record_tool_call(
            tool="read_file",
            args={"path": "file.py"},
            success=True,
        )
        
        state = recovery.get_state()
        assert len(state["events"]) == 1
        
        event = state["events"][0]
        assert event["type"] == "tool_call"
        assert event["tool"] == "read_file"
        assert event["success"] is True
    
    def test_record_tool_call_with_summary(self, recovery):
        """Should use provided summary."""
        recovery.record_tool_call(
            tool="terminal",
            args={"command": "ls -la"},
            success=True,
            summary="List files",
        )
        
        state = recovery.get_state()
        event = state["events"][0]
        assert event["summary"] == "List files"
    
    def test_record_tool_call_auto_summary(self, recovery):
        """Should generate summary automatically."""
        recovery.record_tool_call(
            tool="read_file",
            args={"path": "src/main.py"},
            success=True,
        )
        
        state = recovery.get_state()
        event = state["events"][0]
        assert "src/main.py" in event["summary"]
    
    def test_update_facts_on_success(self, recovery):
        """Should update facts when tool call succeeds."""
        recovery.record_tool_call(
            tool="read_file",
            args={"path": "file.py"},
            success=True,
        )
        
        state = recovery.get_state()
        assert "file.py" in state["facts"]["files_touched"]
        assert "read_file" in state["facts"]["tools_used"]
    
    def test_no_facts_update_on_failure(self, recovery):
        """Should not update facts when tool call fails."""
        recovery.record_tool_call(
            tool="read_file",
            args={"path": "file.py"},
            success=False,
        )
        
        state = recovery.get_state()
        assert "file.py" not in state["facts"]["files_touched"]
        assert "read_file" not in state["facts"]["tools_used"]
    
    def test_track_artifacts(self, recovery):
        """Should track artifacts from write_file/patch."""
        recovery.record_tool_call(
            tool="write_file",
            args={"path": "output.txt", "content": "data"},
            success=True,
        )
        
        state = recovery.get_state()
        assert "output.txt" in state["facts"]["artifacts"]
    
    def test_track_commits(self, recovery):
        """Should extract commit messages from terminal commands."""
        recovery.record_tool_call(
            tool="terminal",
            args={"command": 'git commit -m "feat: add feature"'},
            success=True,
        )
        
        state = recovery.get_state()
        assert len(state["facts"]["commits"]) == 1
        assert state["facts"]["commits"][0]["msg"] == "feat: add feature"
    
    def test_deduplicate_tools(self, recovery):
        """Should deduplicate tools in MRU order."""
        recovery.record_tool_call("read_file", {"path": "a.py"}, True)
        recovery.record_tool_call("terminal", {"command": "ls"}, True)
        recovery.record_tool_call("read_file", {"path": "b.py"}, True)
        
        state = recovery.get_state()
        tools = state["facts"]["tools_used"]
        assert tools[0] == "read_file"  # Most recent
        assert tools[1] == "terminal"
        assert len(tools) == 2
    
    def test_capacity_limits(self, recovery):
        """Should enforce capacity limits."""
        # Add more than MAX_FILES_TOUCHED
        for i in range(60):
            recovery.record_tool_call(
                "read_file",
                {"path": f"file_{i}.py"},
                True,
            )
        
        state = recovery.get_state()
        assert len(state["facts"]["files_touched"]) == 50  # MAX_FILES_TOUCHED


class TestStateManagement:
    def test_set_state(self, recovery):
        """Should set state field."""
        recovery.set_state("current_task", "Working on auth", source="explicit_statement")
        
        state = recovery.get_state()
        assert state["state"]["current_task"]["value"] == "Working on auth"
        assert state["state"]["current_task"]["source"] == "explicit_statement"
    
    def test_set_state_null(self, recovery):
        """Should clear state field."""
        recovery.set_state("current_task", "Working", source="explicit_statement")
        recovery.set_state("current_task", None, source="none")
        
        state = recovery.get_state()
        assert state["state"]["current_task"]["value"] is None
        assert state["state"]["current_task"]["source"] == "none"
    
    def test_set_state_invalid_field(self, recovery):
        """Should raise error for invalid field."""
        with pytest.raises(ValueError, match="Invalid state field"):
            recovery.set_state("invalid_field", "value")
    
    def test_set_state_invalid_source(self, recovery):
        """Should raise error for invalid source."""
        with pytest.raises(ValueError, match="Invalid source"):
            recovery.set_state("current_task", "value", source="invalid")
    
    def test_set_state_records_event(self, recovery):
        """Should record explicit_state event."""
        recovery.set_state("goal", "Build MVP", source="explicit_statement")
        
        state = recovery.get_state()
        event = state["events"][0]
        assert event["type"] == "explicit_state"
        assert event["field"] == "goal"
        assert event["value"] == "Build MVP"
        assert event["source"] == "explicit_statement"


class TestTodoSync:
    def test_sync_todo_state(self, recovery):
        """Should sync state from todo list."""
        todos = [
            {"id": "1", "content": "Task A", "status": "in_progress"},
            {"id": "2", "content": "Task B", "status": "pending"},
            {"id": "3", "content": "Task C", "status": "pending"},
        ]
        
        recovery.sync_todo_state(todos)
        
        state = recovery.get_state()
        assert state["state"]["current_task"]["value"] == "Task A"
        assert state["state"]["current_task"]["source"] == "todo"
        assert state["state"]["next_task"]["value"] == "Task B"
        assert state["state"]["next_task"]["source"] == "todo"
    
    def test_sync_todo_no_in_progress(self, recovery):
        """Should handle no in-progress task."""
        todos = [
            {"id": "1", "content": "Task A", "status": "completed"},
            {"id": "2", "content": "Task B", "status": "pending"},
        ]
        
        recovery.sync_todo_state(todos)
        
        state = recovery.get_state()
        # current_task should not be updated
        assert state["state"]["current_task"]["value"] is None
    
    def test_sync_todo_all_completed(self, recovery):
        """Should handle all tasks completed."""
        # First set a task
        todos = [
            {"id": "1", "content": "Task A", "status": "in_progress"},
        ]
        recovery.sync_todo_state(todos)
        
        # Then complete all
        todos = [
            {"id": "1", "content": "Task A", "status": "completed"},
        ]
        recovery.sync_todo_state(todos)
        
        state = recovery.get_state()
        assert state["state"]["current_task"]["value"] is None


class TestRecoverySummary:
    def test_generate_summary_empty(self, recovery):
        """Should generate summary even with empty state."""
        summary = recovery.generate_recovery_summary()
        
        assert "[Project Recovery]" in summary
        assert "Updated:" in summary
    
    def test_generate_summary_with_state(self, recovery):
        """Should include state fields in summary."""
        recovery.set_state("goal", "Build MVP", source="explicit_statement")
        recovery.set_state("current_task", "Implementing auth", source="explicit_statement")
        
        summary = recovery.generate_recovery_summary()
        
        assert "Goal: Build MVP" in summary
        assert "Current: Implementing auth" in summary
    
    def test_generate_summary_omits_null(self, recovery):
        """Should omit null state fields."""
        recovery.set_state("goal", "Build MVP", source="explicit_statement")
        # current_task is null
        
        summary = recovery.generate_recovery_summary()
        
        assert "Goal: Build MVP" in summary
        assert "Current:" not in summary
    
    def test_generate_summary_with_facts(self, recovery):
        """Should include facts in summary."""
        recovery.record_tool_call("read_file", {"path": "file.py"}, True)
        recovery.record_tool_call("terminal", {"command": "pytest"}, True)
        
        summary = recovery.generate_recovery_summary()
        
        assert "Recent tools:" in summary
        assert "read_file" in summary
        assert "terminal" in summary
    
    def test_generate_summary_with_events(self, recovery):
        """Should include recent events."""
        recovery.record_session_start("sess-001")
        recovery.record_tool_call("read_file", {"path": "file.py"}, True)
        
        summary = recovery.generate_recovery_summary()
        
        assert "Recent activity:" in summary
        assert "session_started" in summary
        assert "tool_call" in summary


class TestFreshness:
    def test_is_fresh_new_file(self, recovery):
        """New file should be fresh."""
        assert recovery.is_fresh() is True
    
    def test_is_fresh_old_file(self, temp_state_path):
        """Old file should not be fresh."""
        recovery = ProjectRecovery(temp_state_path)
        
        # Modify file timestamp to be old
        old_time = time.time() - 7200  # 2 hours ago
        os.utime(temp_state_path, (old_time, old_time))
        
        assert recovery.is_fresh() is False
    
    def test_get_age_seconds(self, recovery):
        """Should return age in seconds."""
        age = recovery.get_age_seconds()
        assert age < 1  # Just created


class TestUtilities:
    def test_reset(self, recovery):
        """Should reset state to empty."""
        recovery.set_state("goal", "Build MVP", source="explicit_statement")
        recovery.record_tool_call("read_file", {"path": "file.py"}, True)
        
        recovery.reset()
        
        state = recovery.get_state()
        assert state["state"]["goal"]["value"] is None
        assert state["facts"]["files_touched"] == []
        assert state["events"] == []
    
    def test_export_json(self, recovery):
        """Should export state as JSON."""
        recovery.set_state("goal", "Test", source="explicit_statement")
        
        json_str = recovery.export_json()
        data = json.loads(json_str)
        
        assert data["state"]["goal"]["value"] == "Test"
    
    def test_import_json(self, recovery):
        """Should import state from JSON."""
        data = {
            "version": 1,
            "project": "test",
            "updated_at": "2026-06-02T12:00:00+00:00",
            "state": {
                "goal": {"value": "Imported", "source": "explicit_statement"},
                "current_task": {"value": None, "source": "none"},
                "next_task": {"value": None, "source": "none"},
                "branch": {"value": None, "source": "none"},
            },
            "facts": {
                "files_touched": [],
                "artifacts": [],
                "commits": [],
                "tools_used": [],
            },
            "events": [],
        }
        
        recovery.import_json(json.dumps(data))
        
        state = recovery.get_state()
        assert state["state"]["goal"]["value"] == "Imported"


class TestThreadSafety:
    def test_concurrent_writes(self, temp_state_path):
        """Should handle concurrent writes safely."""
        import threading
        
        recovery = ProjectRecovery(temp_state_path)
        errors = []
        
        def write_state(i):
            try:
                for _ in range(10):
                    recovery.set_state("current_task", f"Task {i}", source="explicit_statement")
                    recovery.record_tool_call("read_file", {"path": f"file_{i}.py"}, True)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=write_state, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # No errors should occur
        assert len(errors) == 0
        
        # State should be valid
        state = recovery.get_state()
        assert "state" in state
        assert "facts" in state


class TestEdgeCases:
    def test_empty_todo_list(self, recovery):
        """Should handle empty todo list."""
        recovery.sync_todo_state([])
        
        state = recovery.get_state()
        assert state["state"]["current_task"]["value"] is None
    
    def test_long_tool_summary(self, recovery):
        """Should truncate long summaries."""
        long_command = "a" * 300
        
        recovery.record_tool_call(
            "terminal",
            {"command": long_command},
            True,
        )
        
        state = recovery.get_state()
        event = state["events"][0]
        assert len(event["summary"]) <= 200
    
    def test_special_characters_in_state(self, recovery):
        """Should handle special characters."""
        recovery.set_state("current_task", "Working on 特殊字符 & symbols", source="explicit_statement")
        
        state = recovery.get_state()
        assert state["state"]["current_task"]["value"] == "Working on 特殊字符 & symbols"
    
    def test_yaml_format(self, temp_state_path):
        """Should support YAML format."""
        yaml_path = temp_state_path + ".yaml"
        recovery = ProjectRecovery(yaml_path)
        
        recovery.set_state("goal", "Test YAML", source="explicit_statement")
        
        # Read raw file
        with open(yaml_path, "r") as f:
            content = f.read()
        
        assert "Test YAML" in content
        
        # Cleanup
        os.unlink(yaml_path)
    
    def test_json_format(self, temp_state_path):
        """Should support JSON format."""
        json_path = temp_state_path + ".json"
        recovery = ProjectRecovery(json_path)
        
        recovery.set_state("goal", "Test JSON", source="explicit_statement")
        
        # Read raw file
        with open(json_path, "r") as f:
            data = json.load(f)
        
        assert data["state"]["goal"]["value"] == "Test JSON"
        
        # Cleanup
        os.unlink(json_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

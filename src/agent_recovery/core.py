"""
Agent Project Recovery - Core Implementation

B+ Layered Architecture:
- Layer 1 (Facts): Deterministic, auto-maintained
- Layer 2 (State): Declarative, human-readable
- Layer 3 (Events): Append-only evidence chain

License: MIT
"""

import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# System message prefixes that should be filtered from user_messages
# (auto-generated hook messages, not real user input)
_SYSTEM_MSG_PREFIXES = (
    "Review the conversation above",
)


class ProjectRecovery:
    """
    Lightweight state persistence for AI agents.
    
    Usage:
        recovery = ProjectRecovery("~/.my-agent/project-state.yaml")
        
        # Record tool calls automatically
        recovery.record_tool_call("read_file", {"path": "file.py"}, success=True)
        
        # Set state explicitly
        recovery.set_state("current_task", "Implementing auth", source="explicit_statement")
        
        # Generate recovery summary
        summary = recovery.generate_recovery_summary()
    """
    
    # Capacity limits
    MAX_FILES_TOUCHED = 50
    MAX_ARTIFACTS = 50
    MAX_COMMITS = 20
    MAX_TOOLS_USED = 30
    MAX_EVENTS = 100
    
    # Freshness threshold (seconds)
    FRESHNESS_THRESHOLD = 3600  # 1 hour
    
    def __init__(self, state_path: str = "project-state.yaml"):
        """
        Initialize ProjectRecovery.
        
        Args:
            state_path: Path to the state file (YAML or JSON)
        """
        self._state_path = Path(state_path).expanduser()
        self._state_lock = threading.Lock()
        self._ensure_state_file()
    
    def _ensure_state_file(self) -> None:
        """Create state file if it doesn't exist."""
        if not self._state_path.exists():
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            initial_state = self._empty_state()
            self._write_state(initial_state)
    
    def _empty_state(self) -> Dict[str, Any]:
        """Create empty state structure."""
        return {
            "version": 1,
            "project": "",
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "current_session": None,
            "last_session": None,
            "state": {
                "goal": {"value": None, "source": "none"},
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
    
    def _read_state(self) -> Dict[str, Any]:
        """Read state from file."""
        if not self._state_path.exists():
            return self._empty_state()
        
        try:
            content = self._state_path.read_text(encoding="utf-8")
            if self._state_path.suffix in (".yaml", ".yml"):
                import yaml
                return yaml.safe_load(content) or self._empty_state()
            else:
                return json.loads(content)
        except Exception:
            return self._empty_state()
    
    def _write_state(self, state: Dict[str, Any]) -> None:
        """Write state to file."""
        state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self._state_path.suffix in (".yaml", ".yml"):
            import yaml
            content = yaml.dump(state, default_flow_style=False, allow_unicode=True, sort_keys=False)
        else:
            content = json.dumps(state, indent=2, ensure_ascii=False)
        
        self._state_path.write_text(content, encoding="utf-8")
    
    def _append_event(self, state: Dict[str, Any], event: Dict[str, Any]) -> None:
        """Append event to events list, maintaining capacity limit."""
        events = state.setdefault("events", [])
        events.append(event)
        
        # Trim to capacity
        if len(events) > self.MAX_EVENTS:
            state["events"] = events[-self.MAX_EVENTS:]
    
    # ── Public API: Recording ──────────────────────────────────────────────
    
    def record_session_start(self, session_id: str) -> None:
        """Record session start event and track current session."""
        with self._state_lock:
            state = self._read_state()
            state["current_session"] = session_id
            self._append_event(state, {
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "type": "session_started",
                "session_id": session_id,
            })
            self._write_state(state)
    
    def record_session_end(
        self,
        session_id: str,
        completed: bool = True,
        user_messages: Optional[List[str]] = None,
    ) -> None:
        """
        Record session end event with optional user message summary.
        
        Includes YAML-level dedup: if last_session or the last session_ended
        event already has this session_id, the write is skipped. This guards
        against module reload resetting in-memory dedup state.
        
        Args:
            session_id: Session identifier
            completed: Whether the session completed normally
            user_messages: Optional list of user messages from this session
        """
        with self._state_lock:
            state = self._read_state()
            
            # YAML-level dedup: if last_session already has this session_id, skip
            existing_last = state.get("last_session") or {}
            if existing_last.get("session_id") == session_id:
                return
            
            # Also check events: if the last session_ended event has this session_id, skip
            events = state.get("events", [])
            for e in reversed(events):
                if e.get("type") == "session_ended":
                    if e.get("session_id") == session_id:
                        return
                    break
            
            # Filter system messages from user_messages
            if user_messages:
                user_messages = [
                    m for m in user_messages
                    if not m.startswith(_SYSTEM_MSG_PREFIXES)
                ]
            
            event = {
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "type": "session_ended",
                "session_id": session_id,
                "completed": completed,
            }
            if user_messages:
                event["user_messages"] = user_messages[-5:]
            self._append_event(state, event)
            
            # Write last_session for quick recovery (only if there are real messages)
            if user_messages:
                state["last_session"] = {
                    "session_id": session_id,
                    "ended_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "completed": completed,
                    "user_messages": user_messages[-5:],
                }
            
            # Clear current_session since session is ending
            state["current_session"] = None
            self._write_state(state)
    
    def record_tool_call(
        self,
        tool: str,
        args: Dict[str, Any],
        success: bool,
        summary: Optional[str] = None,
    ) -> None:
        """
        Record a tool call and update facts layer.
        
        This is the primary entry point for automatic state tracking.
        Call this after every tool invocation.
        
        Args:
            tool: Tool name (e.g., "read_file", "terminal")
            args: Tool arguments
            success: Whether the call succeeded
            summary: Optional human-readable summary
        """
        with self._state_lock:
            state = self._read_state()
            
            # Generate summary if not provided
            if summary is None:
                summary = self._generate_tool_summary(tool, args)
            
            # Append event
            self._append_event(state, {
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "type": "tool_call",
                "tool": tool,
                "success": success,
                "summary": summary[:200],  # Truncate long summaries
            })
            
            # Update facts layer
            if success:
                self._update_facts(state, tool, args)
            
            self._write_state(state)
    
    def _generate_tool_summary(self, tool: str, args: Dict[str, Any]) -> str:
        """Generate a human-readable summary of a tool call."""
        if tool == "read_file":
            path = args.get("path", "?")
            return f"read_file: {path}"
        
        elif tool == "write_file":
            path = args.get("path", "?")
            return f"write_file: {path}"
        
        elif tool == "patch":
            path = args.get("path", "?")
            return f"patch: {path}"
        
        elif tool == "terminal":
            cmd = args.get("command", "?")
            # Truncate long commands
            if len(cmd) > 100:
                cmd = cmd[:100] + "..."
            return f"$ {cmd}"
        
        elif tool == "todo":
            action = args.get("action", "?")
            return f"todo: {action}"
        
        else:
            return tool
    
    def _update_facts(self, state: Dict[str, Any], tool: str, args: Dict[str, Any]) -> None:
        """Update facts layer based on tool call."""
        facts = state.setdefault("facts", {
            "files_touched": [],
            "artifacts": [],
            "commits": [],
            "tools_used": [],
        })
        
        # Track tools used (MRU, deduplicated)
        tools_used = facts.get("tools_used", [])
        if tool in tools_used:
            tools_used.remove(tool)
        tools_used.insert(0, tool)
        facts["tools_used"] = tools_used[:self.MAX_TOOLS_USED]
        
        # Track files touched
        files_touched = facts.get("files_touched", [])
        
        if tool in ("read_file", "write_file", "patch"):
            path = args.get("path", "")
            if path and path not in files_touched:
                files_touched.append(path)
                facts["files_touched"] = files_touched[-self.MAX_FILES_TOUCHED:]
        
        elif tool == "terminal":
            # Try to extract file paths from terminal commands
            cmd = args.get("command", "")
            extracted = self._extract_files_from_terminal(cmd)
            for f in extracted:
                if f not in files_touched:
                    files_touched.append(f)
            facts["files_touched"] = files_touched[-self.MAX_FILES_TOUCHED:]
        
        # Track artifacts (write_file/patch outputs)
        artifacts = facts.get("artifacts", [])
        if tool in ("write_file", "patch"):
            path = args.get("path", "")
            if path and path not in artifacts:
                artifacts.append(path)
                facts["artifacts"] = artifacts[-self.MAX_ARTIFACTS]
        
        # Track commits
        commits = facts.get("commits", [])
        if tool == "terminal":
            cmd = args.get("command", "")
            commit_match = re.search(r'git\s+commit\s+.*-m\s+["\'](.+?)["\']', cmd)
            if commit_match:
                msg = commit_match.group(1)
                if not any(c.get("msg") == msg for c in commits):
                    commits.append({
                        "msg": msg,
                        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    })
                    facts["commits"] = commits[-self.MAX_COMMITS:]
    
    def _extract_files_from_terminal(self, cmd: str) -> List[str]:
        """Extract file paths from terminal commands (best-effort)."""
        files = []
        
        # Common patterns
        patterns = [
            r'(?:cat|head|tail|less|more|grep|rg|find|ls)\s+[^\s]*?(/[^\s]+)',
            r'(?:vim|nano|code|subl)\s+([^\s]+)',
            r'(?:python|node|bash)\s+([^\s]+\.(?:py|js|sh))',
            r'(?:pytest|unittest)\s+([^\s]+\.py)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, cmd)
            files.extend(matches)
        
        # Deduplicate
        return list(dict.fromkeys(files))
    
    # ── Public API: State Management ───────────────────────────────────────
    
    def set_state(
        self,
        field: str,
        value: Optional[str],
        source: str = "explicit_statement",
    ) -> None:
        """
        Set a state field explicitly.
        
        Args:
            field: State field name (goal, current_task, next_task, branch)
            value: Field value (None to clear)
            source: Source of the value (explicit_statement, todo, none)
        """
        if field not in ("goal", "current_task", "next_task", "branch"):
            raise ValueError(f"Invalid state field: {field}")
        
        if source not in ("explicit_statement", "todo", "none"):
            raise ValueError(f"Invalid source: {source}")
        
        with self._state_lock:
            state = self._read_state()
            
            state["state"][field] = {
                "value": value,
                "source": source if value is not None else "none",
            }
            
            # Record event
            self._append_event(state, {
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "type": "explicit_state",
                "field": field,
                "value": value,
                "source": source,
            })
            
            self._write_state(state)
    
    def sync_todo_state(self, todos: List[Dict[str, Any]]) -> None:
        """
        Sync state from todo list.
        
        Call this when the todo list changes.
        
        Args:
            todos: List of todo items with {id, content, status}
        """
        with self._state_lock:
            state = self._read_state()
            
            # Find current task (in_progress)
            current = None
            next_task = None
            pending_found = False
            
            for todo in todos:
                if todo.get("status") == "in_progress":
                    current = todo.get("content")
                elif todo.get("status") == "pending" and not pending_found:
                    next_task = todo.get("content")
                    pending_found = True
            
            # Update state
            if current is not None:
                state["state"]["current_task"] = {
                    "value": current,
                    "source": "todo",
                }
            elif state["state"]["current_task"].get("source") == "todo":
                # Current task completed
                state["state"]["current_task"] = {
                    "value": None,
                    "source": "todo",
                }
                self._append_event(state, {
                    "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "type": "todo_update",
                    "field": "current_task",
                    "value": None,
                    "source": "todo",
                    "note": "all tasks completed",
                })
            
            if next_task is not None:
                state["state"]["next_task"] = {
                    "value": next_task,
                    "source": "todo",
                }
            
            self._write_state(state)
    
    # ── Public API: Retrieval ──────────────────────────────────────────────
    
    def get_state(self) -> Dict[str, Any]:
        """Get the full state."""
        with self._state_lock:
            return self._read_state()
    
    def is_fresh(self) -> bool:
        """Check if the state file is fresh (updated within threshold)."""
        if not self._state_path.exists():
            return False
        
        age = time.time() - self._state_path.stat().st_mtime
        return age < self.FRESHNESS_THRESHOLD
    
    def get_age_seconds(self) -> float:
        """Get the age of the state file in seconds."""
        if not self._state_path.exists():
            return float("inf")
        return time.time() - self._state_path.stat().st_mtime
    
    def generate_recovery_summary(self, state: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a human-readable recovery summary.
        
        This is the primary output for LLM context injection.
        
        Args:
            state: Optional state dict (reads from file if not provided)
            
        Returns:
            Compact text block suitable for injection into system prompt
        """
        if state is None:
            state = self.get_state()
        
        lines = ["[Project Recovery]", ""]
        
        # State layer
        s = state.get("state", {})
        goal = s.get("goal", {}).get("value")
        current = s.get("current_task", {}).get("value")
        next_t = s.get("next_task", {}).get("value")
        branch = s.get("branch", {}).get("value")
        
        if goal:
            lines.append(f"Goal: {goal}")
        if current:
            lines.append(f"Current: {current}")
        elif s.get("current_task", {}).get("source") == "todo":
            lines.append("Current: (all tasks completed)")
        if next_t:
            lines.append(f"Next: {next_t}")
        if branch:
            lines.append(f"Branch: {branch}")
        lines.append("")
        
        # Last session info (for recovery context)
        cur_sid = state.get("current_session")
        if cur_sid:
            lines.append(f"Current session: {cur_sid}")
        last = state.get("last_session")
        if last:
            sid = last.get("session_id", "?")
            ended = last.get("ended_at", "?")[:19]
            msgs = last.get("user_messages", [])
            if msgs:
                lines.append(f"Last session ({sid}, ended {ended}):")
                for m in msgs:
                    lines.append(f"  - {m[:120]}")
                lines.append("")
        
        # Facts layer
        f = state.get("facts", {})
        tools = f.get("tools_used", [])[:8]
        files = f.get("files_touched", [])[:8]
        artifacts = f.get("artifacts", [])[:5]
        commits = f.get("commits", [])[:3]
        
        if tools:
            lines.append(f"Recent tools: {', '.join(tools)}")
        if files:
            lines.append(f"Files touched: {', '.join(files)}")
        if artifacts:
            lines.append(f"Artifacts: {', '.join(artifacts)}")
        if commits:
            for c in commits:
                msg = c.get('msg', '?').split('\n')[0][:80]
                lines.append(f"Commit: {msg}")
        
        # Recent events — show session boundaries and explicit state changes,
        # skip individual tool_call noise (those are already in "Recent tools").
        events = state.get("events", [])
        meaningful = []
        _seen_end_sessions: set = set()
        for ev in reversed(events):
            ev_type = ev.get("type", "")
            if ev_type == "tool_call":
                continue  # skip noise — tool names are in "Recent tools" above
            if ev_type == "session_ended":
                sid = ev.get("session_id", "")
                if sid in _seen_end_sessions:
                    continue  # deduplicate repeated session_ended for same session
                _seen_end_sessions.add(sid)
            meaningful.append(ev)
            if len(meaningful) >= 8:
                break
        meaningful.reverse()
        
        if meaningful:
            lines.append("")
            lines.append("Recent activity:")
            for ev in meaningful:
                ev_type = ev.get("type", "?")
                summary = ev.get("summary", "")
                if not summary:
                    if ev_type == "session_started":
                        summary = f"session {ev.get('session_id', '?')}"
                    elif ev_type == "session_ended":
                        sid = ev.get("session_id", "?")
                        comp = "completed" if ev.get("completed") else "interrupted"
                        um = ev.get("user_messages", [])
                        msg_count = len(um) if um else 0
                        summary = f"session {sid} ({comp}, {msg_count} msgs)"
                    elif ev_type == "explicit_state":
                        field = ev.get("field", "?")
                        val = ev.get("value", "")
                        summary = f"{field} = {val}"
                    else:
                        summary = ev.get("tool", ev_type)
                at = ev.get("at", "")[:19]
                lines.append(f"  [{at}] {ev_type}: {summary}")
        
        lines.append("")
        lines.append(f"Updated: {state.get('updated_at', 'unknown')}")
        
        return "\n".join(lines)
    
    # ── Public API: Utilities ──────────────────────────────────────────────
    
    def reset(self) -> None:
        """Reset state to empty (use with caution)."""
        with self._state_lock:
            self._write_state(self._empty_state())
    
    def export_json(self) -> str:
        """Export state as JSON string."""
        state = self.get_state()
        return json.dumps(state, indent=2, ensure_ascii=False)
    
    def import_json(self, json_str: str) -> None:
        """Import state from JSON string."""
        state = json.loads(json_str)
        with self._state_lock:
            self._write_state(state)

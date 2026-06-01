# Pitfalls and Known Issues

This document describes known issues, edge cases, and workarounds for Agent Project Recovery.

---

## Critical Issues

### 1. Auto-injection Silent No-op

**Symptom**: Auto-injection doesn't trigger, agent doesn't know previous context.

**Cause**: All state fields are null. The `pre_llm_call` hook only injects if the summary contains "Current:", which requires `current_task` to have a value.

**Root Cause**: No todo tool was used in the previous session, so `current_task` was never set.

**Workaround**:
1. Use todo tool to track tasks (recommended)
2. Manually set state: `hermes-recover set current_task "Working on X"`
3. Use manual recovery: say "搜索记忆，恢复" (if memory-recovery skill is installed)

**Design Decision**: This is intentional. Injecting empty context wastes tokens. The system only injects when there's meaningful state to restore.

---

### 2. hooks.py Overwritten by Agent Updates

**Symptom**: Recovery stops working after agent framework update.

**Cause**: Agent framework updates may overwrite `hooks.py`, removing the recovery integration code.

**Workaround**:
1. Backup your hooks.py before updates
2. Re-apply integration after updates
3. Use drop-in files (e.g., systemd drop-ins) for persistent configuration

**Long-term Solution**: Package integration as a plugin that survives updates.

---

### 3. Terminal File Extraction is Best-Effort

**Symptom**: Files accessed via terminal commands don't appear in `files_touched`.

**Cause**: File extraction from terminal commands uses regex patterns, which may miss:
- Complex command pipelines
- Indirect file access (e.g., `cat file | grep ...`)
- Files accessed via variables

**Example**:
```bash
# Detected
cat src/auth/jwt.py
vim src/auth/jwt.py
pytest tests/test_auth.py

# NOT detected
cat $(find . -name "*.py" | head -1)
FILES="src/auth/jwt.py"; cat $FILES
```

**Workaround**: Accept that terminal file extraction is best-effort. For critical files, use `read_file` or `write_file` tools directly.

---

### 4. 1-Hour Freshness Threshold

**Symptom**: Auto-injection doesn't trigger after a long break.

**Cause**: The `pre_llm_call` hook only injects if the state file is < 1 hour old.

**Rationale**: Stale state might be misleading. If the user hasn't worked on the project for hours, the state might no longer be relevant.

**Workaround**:
1. Manually trigger recovery: `hermes-recover` or say "搜索记忆，恢复"
2. Adjust threshold in code (not recommended — 1 hour is a good default)
3. Use explicit state setting to "refresh" the state

---

### 5. Thread Safety Edge Cases

**Symptom**: State file corruption under high concurrency.

**Cause**: While `_state_lock` protects against concurrent writes within a single process, it doesn't protect against:
- Multiple agent processes writing to the same file
- External editors modifying the file
- Filesystem-level race conditions

**Workaround**:
1. Use a single agent process per state file
2. Don't edit state files manually while agent is running
3. Use atomic file writes (write to temp, then rename)

**Note**: This is a rare edge case. Most users won't encounter it.

---

## Moderate Issues

### 6. YAML Parse Errors

**Symptom**: State file becomes unreadable.

**Cause**: Malformed YAML (e.g., manual editing errors, encoding issues).

**Workaround**:
1. Delete the state file — it will be recreated
2. Use JSON format instead (more forgiving)
3. Validate YAML before saving

**Prevention**: Don't manually edit state files. Use CLI or API.

---

### 7. Events Overflow

**Symptom**: Old events disappear.

**Cause**: Events are capped at 100 entries. When the limit is exceeded, oldest events are dropped.

**Rationale**: Events are for debugging recent activity, not long-term history.

**Workaround**: Accept that old events are lost. For long-term history, use session search or backup.

---

### 8. Todo Sync Delay

**Symptom**: `current_task` doesn't update immediately after todo change.

**Cause**: Todo sync happens in `post_tool_call`, which is called after the todo tool returns. If the todo tool takes time, the sync is delayed.

**Workaround**: Accept the delay (usually < 1 second). For immediate updates, use explicit state setting.

---

### 9. Multiple Projects Confusion

**Symptom**: State from project A appears in project B.

**Cause**: Using the same state file for multiple projects.

**Workaround**:
1. Use separate state files per project
2. Set `project` field in state file
3. Use project-specific paths (e.g., `~/.my-agent/project-a/state.yaml`)

---

### 10. State File in Version Control

**Symptom**: State file committed to git, causing merge conflicts.

**Cause**: State file contains session-specific data (timestamps, session IDs) that differ across developers.

**Workaround**:
1. Add state file to `.gitignore`
2. Use `.git/info/exclude` for local-only exclusion
3. Store state file outside the repository (e.g., `~/.my-agent/`)

---

## Minor Issues

### 11. Long File Paths

**Symptom**: Recovery summary is truncated or hard to read.

**Cause**: Long file paths (e.g., `/home/user/very/long/path/to/file.py`) take up space in the summary.

**Workaround**: Use relative paths when possible. The system already truncates long paths in some cases.

---

### 12. Unicode in State

**Symptom**: State file contains garbled characters.

**Cause**: Encoding issues (e.g., UTF-8 vs Latin-1).

**Workaround**: Ensure your environment uses UTF-8. The system explicitly uses `encoding="utf-8"` for all file operations.

---

### 13. Empty Todo List

**Symptom**: `current_task` cleared unexpectedly.

**Cause**: Todo list is empty or all tasks are completed. The system sets `current_task` to null when no task is in progress.

**Design Decision**: This is intentional. When all tasks are completed, there's no current task.

---

### 14. State File Permissions

**Symptom**: Permission denied when writing state file.

**Cause**: State file or directory has restrictive permissions.

**Workaround**:
1. Check file permissions: `ls -la ~/.my-agent/project-state.yaml`
2. Ensure directory is writable: `chmod u+w ~/.my-agent/`
3. Use a different path with appropriate permissions

---

## Edge Cases

### 15. Crash During Write

**Symptom**: State file is partially written or corrupted.

**Cause**: Agent crashes while writing state file.

**Recovery**: The system uses `_read_state()` which returns empty state on parse errors. The state file will be recreated on next write.

**Prevention**: Use atomic writes (write to temp file, then rename).

---

### 16. Very Long Sessions

**Symptom**: State file grows large.

**Cause**: Many tool calls and events accumulate.

**Mitigation**: Capacity limits (100 events, 50 files, etc.) prevent unbounded growth.

**Note**: Even with many tool calls, the state file rarely exceeds 10 KB.

---

### 17. No Tool Calls

**Symptom**: Facts layer is empty.

**Cause**: Session had no tool calls (e.g., only conversation).

**Design Decision**: This is acceptable. Facts layer is empty when there are no facts to record.

---

### 18. State Field Mismatch

**Symptom**: Unknown state field in state file.

**Cause**: State file was created by a different version or modified manually.

**Workaround**: The system ignores unknown fields. Only `goal`, `current_task`, `next_task`, `branch` are recognized.

---

## Best Practices

### 1. Use Todo Tool

The most reliable way to keep state synchronized is to use the todo tool for task tracking. This ensures `current_task` and `next_task` are always up-to-date.

### 2. Don't Edit State Files Manually

Use CLI or API to modify state. Manual editing risks corruption.

### 3. Use Separate State Files Per Project

Avoid confusion by using project-specific state files.

### 4. Add State Files to .gitignore

State files contain session-specific data that shouldn't be version-controlled.

### 5. Monitor State File Freshness

Check `hermes-recover` output for freshness indicators:
- `[Fresh: 300s ago]` — Auto-injection will trigger
- `[Stale: 2.5h ago]` — Auto-injection skipped
- `[Old: 3.2 days ago]` — State likely outdated

### 6. Use Manual Recovery as Fallback

If auto-injection doesn't trigger, use manual recovery:
```bash
hermes-recover                    # View state
hermes-recover set current_task X  # Set state manually
```

### 7. Test Integration After Updates

After updating your agent framework, verify that recovery still works:
1. Start a new session
2. Use todo to set a task
3. End session
4. Start new session
5. Check if recovery context was injected

---

## Debugging

### Enable Debug Logging

```python
import logging
logging.getLogger("agent_recovery").setLevel(logging.DEBUG)
```

### Check State File

```bash
cat ~/.my-agent/project-state.yaml
```

### Verify Freshness

```bash
stat -c %Y ~/.my-agent/project-state.yaml
# Compare with current time
date +%s
```

### Test Auto-injection

```python
from agent_recovery import ProjectRecovery

recovery = ProjectRecovery("~/.my-agent/project-state.yaml")
print(recovery.is_fresh())  # Should be True
print(recovery.generate_recovery_summary())  # Should contain "Current:"
```

---

## Reporting Issues

When reporting issues, include:
1. Agent framework and version
2. Python version
3. State file contents (redact sensitive data)
4. Steps to reproduce
5. Expected vs actual behavior

---

## Contributing Fixes

If you fix a pitfall or edge case:
1. Add it to this document
2. Include a test case
3. Update the relevant code
4. Submit a pull request

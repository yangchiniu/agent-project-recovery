# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-03

### Added

- **User message tracking**: `record_session_end` now accepts `user_messages` parameter to store what the user said during the session
- **`last_session` state**: Top-level state field for instant recovery context — shows what the user was asking about
- **`current_session` tracking**: `record_session_start` now writes `current_session` to state
- **System message filtering**: Auto-generated messages (e.g., "Review the conversation above...") are filtered from `user_messages` at both the hook layer and the core layer
- **YAML-level dedup**: `record_session_end` checks the state file itself (not just in-memory variables) to prevent duplicate `session_ended` events — survives module reloads
- **Recovery summary improvements**: `generate_recovery_summary` now shows `last_session` with user messages, skips `tool_call` noise, and deduplicates `session_ended` events in the activity timeline

### Changed

- `record_session_end` signature: added optional `user_messages: List[str]` parameter (backward compatible)
- `generate_recovery_summary` output: more compact, focused on session context rather than tool noise
- `pre_llm_call` in hooks: now extracts and tracks user messages for session summary
- `_empty_state`: includes `current_session` and `last_session` fields

### Fixed

- **Duplicate session_ended events**: Module reload (e.g., during hot-fix) would reset the in-memory dedup guard, causing the same session to be recorded multiple times. Fixed with YAML-level dedup.
- **System messages in user_messages**: Auto-generated hook messages like "Review the conversation above..." were being stored as user messages. Fixed with prefix-based filtering in both hooks and core.

### Design Decisions

- **Dual-layer filtering**: System messages are filtered in both `hooks.py` (pre_llm_call) and `core.py` (record_session_end). Defense in depth — even if one layer misses, the other catches it.
- **YAML as source of truth for dedup**: In-memory variables are fast but fragile (module reload resets them). The YAML file is slow but durable. We check both.
- **last_session only written with real messages**: Empty/tool-only sessions don't clobber a meaningful last_session. This prevents recovery context from being wiped by automated sub-sessions.

## [1.0.0] - 2026-06-02

### Added

- Initial release
- B+ layered architecture (Facts, State, Events)
- Automatic tool call recording via `post_tool_call`
- Todo state synchronization
- One-shot recovery context injection via `pre_llm_call`
- CLI tool (`hermes-recover`)
- Thread-safe state management
- Capacity limits (facts: 50, events: 100)
- Freshness threshold (1 hour)
- YAML/JSON state file support
- Integration examples for Hermes, Claude Code
- Comprehensive documentation

### Design Decisions

- **Allow null**: State fields can be null, no LLM inference
- **Bind to todo**: `current_task` synced from todo tool as highest-trust source
- **Facts are deterministic**: Zero human intervention, 100% accurate
- **Events are append-only**: Evidence chain for debugging, never deleted

## [0.4.0] - 2026-06-01

### Changed

- Bound `current_task` to todo tool as Level 1 source
- Added `sync_todo_state()` for automatic todo synchronization
- Updated hook integration to detect todo tool calls

### Rationale

The question "when does current_task get updated?" was solved by binding it to the todo tool. Users naturally use todo to track tasks, so the state stays in sync without explicit management.

## [0.3.0] - 2026-05-31

### Changed

- Separated Facts and State into distinct layers
- Added `source` field to all state entries
- Made Events append-only with capacity limit

### Rationale

Mixing deterministic facts (which files were touched) with human-readable state (what's the current goal) created confusion. The B+ separation clarified responsibilities:
- Facts: machine-recorded, 100% accurate, zero cost
- State: human-declared, allows null, bound to trusted sources
- Events: timeline, append-only, for debugging

## [0.2.0] - 2026-05-30

### Added

- `project-state.yaml` data model
- `pre_llm_call` hook for auto-injection
- Freshness threshold (1 hour)
- Recovery summary generation

### Changed

- Renamed from "Memory Recovery" to "Agent Project Recovery"
- Shifted paradigm from "search history" to "save state"

### Rationale

The original "Memory Recovery" approach was searching chat history after interruption. This was expensive (80-100K tokens) and slow (30+ seconds). The new approach saves state before interruption, enabling instant recovery with 2-5K tokens.

## [0.1.0] - 2026-05-29

### Added

- Initial prototype
- Session search-based recovery
- Memory recovery skill

### Problems Identified

- Token consumption: 80-100K per recovery
- Latency: 30+ seconds
- Reliability: LLM might miss key information in long histories
- Scalability: cost grows linearly with session length

### Decision

This approach was fundamentally flawed. Searching history is an "after the fact" solution to a "before the fact" problem. The correct approach is to save state proactively.

---

## Design Evolution Summary

```
v0.1: Memory Recovery (事后搜索)
  Problem: Agent doesn't know what it was doing
  Solution: Search chat history, let LLM summarize
  Result: Works, but expensive (80-100K tokens)

v0.2: Agent Project Recovery (事前保存)
  Insight: Don't search history, save state
  Solution: project-state.yaml + auto-recording
  Result: Recovery cost drops to 2-5K tokens

v0.3: B+ Layered Architecture
  Problem: State and facts mixed together
  Solution: Separate into Facts (machine) + State (human) + Events (timeline)
  Result: Zero-intervention Facts + nullable State

v0.4: Bind to Todo Tool
  Problem: When does current_task update?
  Solution: Bind to todo tool as highest-trust source
  Result: State stays in sync with natural workflow

v1.0: Production Ready
  ✅ Complete 4-point hook integration
  ✅ CLI tool
  ✅ Cross-agent compatible data format
  ✅ Thread safety
  ✅ Capacity limits

v1.1: Session Context & Robustness
  Problem: Recovery summary didn't show what the user was asking about
  Solution: User message tracking + last_session state + system message filtering
  Result: Agent knows "what was I doing" without searching chat history
  Bugfix: YAML-level dedup prevents duplicate events after module reload
```

---

## Key Insights

1. **Paradigm Shift**: From Information Retrieval to State Management
2. **Cost Reduction**: 95% token reduction (80-100K → 2-5K)
3. **Latency Reduction**: 99% time reduction (30s → <1s)
4. **Reliability**: Deterministic state beats probabilistic search
5. **Simplicity**: YAML file beats vector database
6. **Robustness**: YAML-level dedup beats in-memory guards

---

## Acknowledgments

This project emerged from real-world needs in [Hermes Agent](https://github.com/nousresearch/hermes-agent).

Key contributions from iterative design discussions:
- Initial diagnosis of the "post-hoc search" problem
- GitHub research on similar projects (agentkeeper, Octopoda-OS, etc.)
- Three rounds of design convergence
- Critical feedback on B+ architecture, todo binding, and null handling
- Bug reports on duplicate events and system message leakage

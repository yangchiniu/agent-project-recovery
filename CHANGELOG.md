# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
```

---

## Key Insights

1. **Paradigm Shift**: From Information Retrieval to State Management
2. **Cost Reduction**: 95% token reduction (80-100K → 2-5K)
3. **Latency Reduction**: 99% time reduction (30s → <1s)
4. **Reliability**: Deterministic state beats probabilistic search
5. **Simplicity**: YAML file beats vector database

---

## Acknowledgments

This project emerged from real-world needs in [Hermes Agent](https://github.com/nousresearch/hermes-agent).

Key contributions from iterative design discussions:
- Initial diagnosis of the "post-hoc search" problem
- GitHub research on similar projects (agentkeeper, Octopoda-OS, etc.)
- Three rounds of design convergence
- Critical feedback on B+ architecture, todo binding, and null handling

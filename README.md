# Agent Project Recovery

**从"崩溃后搜索聊天记录"到"事前保存项目状态"的范式转变**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 问题：AI Agent 的"失忆"成本

当一个长对话中断后，AI Agent 面临一个昂贵的选择：

```
用户："继续上次的工作"
Agent："让我搜索一下之前的聊天记录..."
↓
session_search → 读取 80-100K tokens 的历史消息
↓
LLM 花费 30 秒理解上下文
↓
终于知道上次在做什么
```

**每次恢复消耗 80-100K tokens，30+ 秒延迟。**

这不是技术问题，是架构问题——我们在用"事后搜索"解决"事前记录"应该解决的问题。

---

## 解决方案：Project Recovery

```
项目中断前：
  project-state.yaml 自动保存当前状态
  
项目恢复时：
  读取 2K tokens 的状态文件 → 立即知道上下文
```

**Token 消耗：80-100K → 2-5K（降低 95%）**  
**恢复时间：30+ 秒 → <1 秒**

---

## 核心设计：B+ 分层架构

```
┌─────────────────────────────────────────────────┐
│  Layer 2: State (声明式)                         │
│  goal / current_task / next_task / branch        │
│  来源: todo tool 同步 + 显式设置                   │
│  允许 null — 不推断填充                           │
├─────────────────────────────────────────────────┤
│  Layer 1: Facts (确定性)                         │
│  files_touched / commits / tools_used            │
│  来源: post_tool_call hook 自动记录               │
│  零人工干预                                       │
├─────────────────────────────────────────────────┤
│  Layer 3: Events (证据链)                        │
│  append-only, max 100 条                         │
│  来源: 所有工具调用和状态变更                      │
│  用于调试和审计                                   │
└─────────────────────────────────────────────────┘
```

### 为什么是"B+"？

- **B 层（Facts）**：机器记录，100% 准确，零成本
- **+ 层（State）**：人类语义，允许 null，绑定可信来源
- **Events**：不是层级，是时间线——只增不删的证据链

---

## 自动恢复链路

```python
# 新 session 启动
on_session_start → 初始化 project_recovery

# 用户发第一条消息
pre_llm_call → 检测 project-state.yaml 新鲜度
  ├── < 1 小时 且 有内容 → 自动注入恢复摘要
  └── >= 1 小时 或 不存在 → 跳过（靠 LLM 自行判断）

# 每次工具调用后
post_tool_call → 记录到 facts + events
  └── 如果是 todo tool → 同步到 state 层

# Session 结束
on_session_end → 记录结束事件
```

**用户视角：什么都不用做，下次打开 Agent 自动知道上次在做什么。**

---

## 快速开始

### 安装

```bash
pip install agent-project-recovery
```

### 独立使用

```python
from agent_recovery import ProjectRecovery

# 初始化
recovery = ProjectRecovery("./project-state.yaml")

# 记录工具调用
recovery.record_tool_call(
    tool="read_file",
    args={"path": "/path/to/file.py"},
    success=True
)

# 显式设置状态
recovery.set_state("current_task", "正在实现用户认证模块", source="explicit_statement")

# 生成恢复摘要
summary = recovery.generate_recovery_summary()
print(summary)
```

### CLI 使用

```bash
# 查看当前状态
hermes-recover

# 设置状态
hermes-recover set current_task "正在调试登录 bug"

# JSON 输出
hermes-recover --json
```

### 集成到 AI Agent 框架

```python
from agent_recovery import ProjectRecovery
from agent_recovery.hooks import create_hooks

recovery = ProjectRecovery("~/.my-agent/project-state.yaml")

# 创建标准 hook 函数
hooks = create_hooks(recovery)

# 在你的 Agent 框架中注册
agent.register_hook("on_session_start", hooks["on_session_start"])
agent.register_hook("post_tool_call", hooks["post_tool_call"])
agent.register_hook("pre_llm_call", hooks["pre_llm_call"])
agent.register_hook("on_session_end", hooks["on_session_end"])
```

---

## 设计演进：从 60 分到 90 分

### v0.1：Memory Recovery（事后搜索）

```
问题：Agent 重启后不知道上次在做什么
方案：搜索聊天记录，让 LLM 总结
结果：能用，但消耗 80-100K tokens
```

### v0.2：Agent Project Recovery（事前保存）

```
洞察：不要搜索历史，要保存状态
方案：project-state.yaml + 自动记录
结果：恢复消耗降至 2-5K tokens
```

### v0.3：B+ 分层架构

```
问题：状态和事实混在一起
方案：分离为 Facts（机器）+ State（人类）+ Events（时间线）
结果：零人工干预的 Facts 层 + 允许 null 的 State 层
```

### v0.4：绑定 Todo Tool

```
问题：current_task 什么时候更新？
方案：绑定 todo tool 作为最高可信源
结果：用户正常使用 todo，状态自动同步
```

### v1.0：生产就绪

```
✅ 完整的 4 点 hook 集成
✅ CLI 工具
✅ 跨 Agent 兼容的数据格式
✅ 线程安全（_state_lock）
✅ 容量限制（facts 50 条, events 100 条）
```

---

## 为什么不用现有方案？

| 方案 | 问题 |
|------|------|
| **搜索聊天记录** | 80-100K tokens，慢，LLM 可能遗漏关键信息 |
| **Embedding/RAG** | 重，需要向量库，增加依赖 |
| **长期记忆系统** | 解决的是不同问题（跨 session 记忆，不是项目状态恢复） |
| **手动保存** | 人会忘，不可靠 |

**Project Recovery 的定位：轻量、确定性、零配置。**

---

## 数据格式

```yaml
version: 1
project: "my-project"
updated_at: "2026-06-02T12:00:00+00:00"

state:
  goal:
    value: "实现用户认证系统"
    source: "explicit_statement"
  current_task:
    value: "正在调试 JWT token 验证"
    source: "todo"
  next_task:
    value: "添加 refresh token 机制"
    source: "todo"
  branch:
    value: "feature/auth"
    source: "explicit_statement"

facts:
  files_touched:
    - src/auth/jwt.py
    - tests/test_auth.py
  artifacts:
    - dist/auth-v1.0.0.tar.gz
  commits:
    - msg: "feat: add JWT validation"
      sha: "abc1234"
  tools_used:
    - read_file
    - terminal
    - patch

events:
  - at: "2026-06-02T11:55:00+00:00"
    type: "session_started"
    session_id: "sess_123"
  - at: "2026-06-02T11:56:00+00:00"
    type: "tool_call"
    tool: "terminal"
    success: true
    summary: "pytest tests/test_auth.py"
  - at: "2026-06-02T11:58:00+00:00"
    type: "todo_update"
    field: "current_task"
    value: "正在调试 JWT token 验证"
    source: "todo"
```

---

## 已知限制

1. **自动注入需要 State 层有内容**：如果所有 state 字段都是 null，自动注入不会触发（设计如此，避免空摘要浪费 token）

2. **1 小时新鲜度阈值**：长时间休息后需要手动触发恢复

3. **Terminal 文件提取是 best-effort**：正则匹配 terminal 命令中的文件路径，可能遗漏

4. **hooks.py 可能被覆盖**：Agent 框架更新时可能覆盖集成代码，需要重新集成

---

## 适用场景

✅ **适合**：
- 本地运行的 AI Agent（Hermes, Claude Code, Aider）
- 长对话频繁中断的工作流
- 多任务并行的开发环境
- Token 成本敏感的场景

❌ **不适合**：
- 需要跨 session 的长期记忆（那是不同问题）
- 需要语义搜索历史（那是 RAG 的活）
- 云原生、无状态的 Agent 架构

---

## 开发理念

> **不要搜索历史，要保存状态。**

这是 Project Recovery 的核心洞察。

传统方案是"事后补救"——中断后搜索聊天记录，让 LLM 重新理解上下文。

Project Recovery 是"事前预防"——每次工具调用后自动保存状态，中断后直接读取。

**范式转变：从 Information Retrieval 到 State Management。**

---

## 致谢

这个项目诞生于 [Hermes Agent](https://github.com/nousresearch/hermes-agent) 的实际需求。

感谢以下对话和迭代：
- 初始诊断：发现"事后搜索"的根本问题
- GitHub 调研：agentkeeper, Octopoda-OS 等项目的启发
- 三轮设计讨论：从全盘替换到轻量方案的收敛
- 同事的关键建议：B+ 分层、绑定 todo tool、允许 null

---

## License

MIT

---

## Contributing

欢迎 Issue 和 PR！

特别欢迎：
- 其他 AI Agent 框架的集成示例
- 性能优化建议
- 已知问题的修复

---

**Stop searching history. Start saving state.**

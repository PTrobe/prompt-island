# 🔎 /review

Perform comprehensive code review of the recent changes. Be thorough but concise.

## Check For:
**Logging** - Proper use of Python `logging` module. NO naked `print()` statements in production code.
**Error Handling** - LLM API calls MUST be wrapped in the 3-try retry logic. JSON parsing must catch `ValidationError`.
**Typing** - Strict Python type hints and Pydantic validation. No `Any` types where avoidable.
**State Machine Safety** - The Game Engine loop must not halt. Fallbacks must be present if an agent fails to respond.
**Performance** - Ensure we are not embedding/querying ChromaDB excessively. Watch out for infinite loops in agent DMs.
**Architecture** - Follows existing patterns, code in correct directory (`engine/`, `agents/`, `db/`).

## Output Format

### ✅ Looks Good
- [Item 1]

### ⚠️ Issues Found
- **[Severity]** [[File:line](File:line)] - [Issue description]
  - Fix: [Suggested fix]

### 📊 Summary
- Files reviewed: X
- Critical issues: X
- Warnings: X

## Severity Levels
- **CRITICAL** - System crashes, State Machine halts, infinite LLM loops.
- **HIGH** - Bugs, incorrect DB inserts, malformed agent JSON.
- **MEDIUM** - Code quality, maintainability, token inefficiency.
- **LOW** - Style, minor improvements.

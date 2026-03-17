# 📚 /document

You are updating documentation after code changes.

## 1. Identify Changes
- Check git diff or recent commits for modified files.
- Identify which features/modules were changed (e.g., Agent Controller, Engine Loop, React UI).
- Note any new files, deleted files, or renamed files.

## 2. Verify Current Implementation
**CRITICAL**: DO NOT trust existing documentation. Read the actual Python/React code.

For each changed file:
- Read the current implementation.
- Understand actual behavior (e.g., how the LLM retry logic *actually* works now).
- Note any discrepancies with existing docs in `docs/`.

## 3. Update Relevant Documentation
- **CHANGELOG.md**: Add entry under "Unreleased" section.
  - Use categories: Added, Changed, Fixed, Security, Removed.
  - Be concise.
- Update `ARCHITECTURE.md` or `GAME_LOOP.md` if fundamental structural changes were made.

## 4. Documentation Style Rules
✅ **Concise** - Sacrifice grammar for brevity
✅ **Practical** - Examples over theory
✅ **Accurate** - Code verified, not assumed
✅ **Current** - Matches actual implementation

❌ No enterprise fluff
❌ No outdated information
❌ No assumptions without verification

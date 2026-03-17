# 📋 /create-issue

User is mid-development and thought of a bug/feature/improvement for Prompt Island. Capture it fast so they can keep working.

## Your Goal
Create a complete issue with:
- Clear title
- TL;DR of what this is about
- Current state vs expected outcome
- Relevant files that need touching (e.g., `engine/loop.py`, `agents/schemas.py`)
- Risk/notes if applicable (e.g., "Will this break the LLM JSON parsing?")
- Proper type/priority/effort labels

## How to Get There
**Ask questions** to fill gaps - be concise, respect the user's time. Usually need:
- What's the issue/feature
- Current behavior vs desired behavior
- Type (bug/feature/improvement) and priority if not obvious

Keep questions brief. One message with 2-3 targeted questions beats multiple back-and-forths.

**Search for context** only when helpful:
- Grep codebase to find relevant files.
- Note any risks or dependencies you spot (especially regarding the Game State).

**Skip what's obvious** - If it's a straightforward bug, don't ask.
**Keep it fast** - Total exchange under 2min. Be conversational but brief.

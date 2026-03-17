# Error Handling & Retry Logic

## 1. Core Philosophy
LLMs are non-deterministic and will inevitably make mistakes. They might output malformed JSON, include conversational filler (e.g., "Here is your JSON:"), or hallucinate actions that violate game rules. 
The system must be **100% fault-tolerant**. The main Game Loop must NEVER crash due to a bad LLM response.

## 2. The Retry Loop architecture

Whenever the `Agent Controller` calls an LLM API, the response must be parsed into the `AgentAction` Pydantic model. If this parsing fails, or if game rules are violated, the system enters a retry loop.

**Maximum Retries:** 3 attempts per action.

* **Attempt 1 (Standard):** The standard prompt is sent.
* **Attempt 2 (Correction):** If Attempt 1 fails (e.g., JSONDecodeError), the system resends the exact same prompt but appends a high-priority system message: 
  `"SYSTEM ERROR: Your previous output was invalid. You must respond ONLY with valid JSON matching the exact schema. Do not include markdown formatting or conversational text."`
* **Attempt 3 (Final Attempt):** If Attempt 2 fails, the system sends the correction prompt again, but dynamically lowers the `temperature` to 0.1 to force the most probable (and usually most structurally sound) output.

## 3. Fallback Mechanisms (The "Brain Freeze")
If an agent fails all 3 retry attempts, the game cannot halt. The `Agent Controller` must gracefully catch the final exception and inject a **Fallback Action** on behalf of the agent to keep the game moving.

**Example Fallback Action:**
```json
{
  "inner_thought": "I am experiencing a severe system glitch and cannot think clearly right now.",
  "action_type": "speak_public",
  "target_agent_id": null,
  "message": "*stares blankly into space* I... I need a moment to process everything."
}

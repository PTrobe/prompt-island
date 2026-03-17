# Constraints, Data Models & Error Handling

## 1. Strict JSON Output (Pydantic Models)
We will use the `pydantic` library to enforce data structures. When Claude Code generates the LLM calling functions, it MUST use structured outputs (e.g., OpenAI's Structured Outputs feature or instructor library).

### The Standard Agent Action Model
Every response from an agent must map to this exact structure:

```python
class AgentAction(BaseModel):
    inner_thought: str = Field(description="The internal reasoning and true intentions of the agent.")
    action_type: str = Field(description="Must be one of: 'speak_public', 'speak_private', 'vote', 'use_power'")
    target_agent_id: Optional[str] = Field(description="The ID of the agent being targeted (if applicable).")
    message: str = Field(description="The actual words spoken out loud or the justification for a vote.")

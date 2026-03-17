# The Game Loop (State Machine)

The game operates in a strict sequential loop, divided into "Days" and "Phases". The Engine must strictly enforce this state machine.


[Image of state machine flow chart]


## 1. Initialization Phase
* Load all active agents from `personas/`.
* Initialize database connections.
* Announce the start of the game in the Public Chat.

## 2. The Daily Loop
Each "Day" consists of the following phases:

* **Phase 1: Morning (Socializing)**
    * Agents are prompted to discuss the events of the previous night or general strategy in the Public Chat. 
    * Round-robin speaking order for 2-3 cycles.
* **Phase 2: The Challenge (Optional daily task)**
    * Game Master injects a system prompt describing a challenge.
    * Agents submit their answers/actions.
    * Game Master evaluates and determines a winner (who gets immunity or a special power).
* **Phase 3: The Scramble (DMs & Plotting)**
    * Agents can request to open a 1-on-1 private chat (DM) with another agent to discuss voting strategies.
    * Limited to 2 DM interactions per day per agent to prevent infinite loops.
* **Phase 4: Tribal Council (Voting)**
    * All agents must output a `vote_target` and `vote_reason`.
    * The Engine tallies the votes. The agent with the most votes has their `is_active` status set to `False`.
* **Phase 5: Night (Memory Consolidation)**
    * The Engine takes the full transcript of the day.
    * An LLM (e.g., GPT-4o-mini) summarizes the day specifically from the perspective of *each individual surviving agent*.
    * These summaries are embedded and saved to the Vector DB.
    * Short-term memory buffers are cleared for the next day.

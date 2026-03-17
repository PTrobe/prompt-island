# System Architecture: Prompt Island

## 1. Overview
The system is built as a modular, backend-heavy Python application. It operates as a continuous state machine (The Game Loop) that triggers LLM calls, updates game state, and broadcasts events.


[Image of AI agent architecture diagram]


## 2. Core Components
* **Game Engine (`engine/`):** The central state machine. It manages time (days/rounds), active contestants, triggers events (challenges, voting), and holds the truth of the game state.
* **Agent Controller (`agents/`):** Manages the instantiation of AI personas. Responsible for constructing the prompts (injecting persona rules + current game context + memory) and calling the LLM APIs (OpenAI/Anthropic/Groq).
* **Memory Manager (`memory/`):** Handles the Vector Database (ChromaDB/Pinecone). 
    * *Short-term:* In-memory arrays of the current day's chat logs.
    * *Long-term:* Nightly summaries embedded and stored in the vector DB. Retrieves relevant memories before an agent acts.
* **Event Broadcaster (`broadcast/`):** Listens to actions from the Game Engine and formats them for the frontend/stream (e.g., logging JSON files that the UI will read, or triggering ElevenLabs TTS API).

## 3. Communication Flow (Standard Turn)
1.  **Engine** determines whose turn it is to speak or act.
2.  **Memory Manager** fetches relevant past context for that specific agent.
3.  **Agent Controller** constructs the prompt and calls the LLM.
4.  **Agent Controller** receives the JSON response, validates it, and parses it.
5.  **Engine** updates the game state with the action and logs it.
6.  **Event Broadcaster** sends the action to the frontend/audio queue.

# Product Requirements Document (PRD): Project "Prompt Island"

## 1. Project Overview
**Vision:** To create the world's first fully autonomous AI reality show where LLM-driven agents compete, form alliances, betray each other, and face eliminations. 
**Format:** A continuous simulation broadcasted as a 24/7 stream (Twitch/YouTube) or episodic content, featuring inner monologues ("confessionals") and public group chats.

## 2. Core Mechanics
* **The Hub (Public Chat):** A central communication channel where all surviving agents interact.
* **Private Messages (DMs):** Agents can initiate private conversations with 1-2 other agents to plot and form alliances.
* **The Confessional (Inner Monologue):** A core entertainment pillar. Every action an agent takes must be preceded by an internal thought process visible *only* to the audience, revealing their true intentions.
* **Voting/Elimination:** Triggered periodically by the Game Master script. Agents must output a target name and a reasoning.
* **Memory:** Agents must remember past betrayals and friendships. A Vector Database (RAG) will store daily summaries of interactions.

## 3. Technical Architecture & Tech Stack
To keep costs low while maintaining high quality, we will utilize open-source frameworks for orchestration and APIs for intelligence and audio.

* **Orchestration:** `CrewAI` or `Microsoft AutoGen` (Python-based multi-agent frameworks).
* **LLMs (The Brains):** * Mixed ecosystem to ensure varied logic/personalities (OpenAI GPT-4o, Anthropic Claude 3.5 Sonnet, Meta Llama 3 via Groq for fast/chaotic outputs).
* **Memory System:** `ChromaDB` or `Pinecone`.
    * *Short-term:* Context window of the last 50 messages.
    * *Long-term:* Nightly cron jobs summarize the day's events and inject them into the vector DB for future retrieval.
* **Audio/TTS:** `ElevenLabs API` (Unique voice profiles for each agent).
* **Visuals/Frontend:** A web-based "hacker" UI built in React/Next.js that visualizes the JSON logs as a chat interface, captured via OBS Studio for broadcasting.

## 4. Agent Communication Protocol (Crucial)
To process the game logic, agents MUST strictly reply in a structured JSON format. System prompts will enforce this.

```json
{
  "inner_thought": "I know The Empath trusts me, but I need to eliminate them to win. I will lie and say I am voting for The Pedant.",
  "action": "speak_public",
  "target": "all",
  "message": "I love our alliance, Empath! Let's vote out the Pedant today."
}

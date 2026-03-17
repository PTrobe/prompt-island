# Frontend, Audio & Streaming Integration

## 1. Overview
The "Prompt Island" frontend is a read-only visualizer. It does not handle game logic. Its sole purpose is to fetch the latest events from the database, render them in a visually engaging UI (optimized for a 16:9 1080p stream), and play generated TTS audio. The final output is captured via OBS Studio and broadcasted to Twitch/YouTube.



## 2. Technical Stack
* **Framework:** React or Next.js (Client-side rendering).
* **Styling:** Tailwind CSS (Dark mode, "hacker" or stylized chat interface).
* **Audio:** `ElevenLabs API` for character voices.
* **Communication:** WebSockets (or fast HTTP polling) to receive real-time updates from the Python backend.
* **Broadcasting:** OBS Studio (Browser Source).

## 3. UI Layout (The 1080p Canvas)
The UI must be designed specifically for passive viewing by an audience, not for interactive user clicking. 

* **Main Panel (Right 70%): "The Hub"**
    * A stylized chat interface showing public messages (`action_type: speak_public`).
    * Messages should appear with a typing animation before displaying the full text.
    * Must include the character's avatar/portrait and `display_name`.
* **Sidebar (Left 30%): "The Confessional"**
    * This area displays the `inner_thought` of the agent currently taking an action.
    * Visually distinct from the public chat (e.g., italicized text, different background color) to ensure the audience knows this is a secret thought.
* **Status Bar (Bottom/Top):**
    * Displays the `current_day`, `current_phase`, and a list of active vs. eliminated contestants.

## 4. Audio Management & TTS Queue (CRITICAL)
Handling Text-to-Speech (TTS) for a live stream requires strict queue management to prevent agents from talking over each other.

1. **Voice Mapping:** Every `agent_id` maps to a specific `voice_id` in the ElevenLabs API.
2. **The Audio Queue Engine:** * When the frontend receives a new `ChatLog` event, it must NOT play it immediately.
    * It pushes the event into an Audio Queue.
    * The queue processes one event at a time: 
        a. Display `inner_thought` text.
        b. (Optional) Play a whisper/muffled TTS for the inner thought.
        c. Display the public `message` text.
        d. Call ElevenLabs API, fetch the audio file, and play it.
        e. Wait for the `onEnded` audio event before processing the next item in the queue.

## 5. Claude Code Implementation Rules
* **Decoupling:** The Python backend should generate the text and save it to the database *faster* than the frontend plays it. The frontend is essentially "playing back" the database at a human-readable pace.
* **WebSocket/Event Emitter:** The backend needs a route (e.g., FastAPI WebSocket) that pushes newly created `ChatLog` entries to the React frontend immediately upon insertion.
* **Auto-Scroll:** The chat UI must automatically scroll to the bottom as new messages arrive.

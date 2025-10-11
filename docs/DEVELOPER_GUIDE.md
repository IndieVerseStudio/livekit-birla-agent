## Birla Opus Voice Agent – Developer Guide

This document orients new contributors to the Birla Opus Voice Agent built on LiveKit Agents (Python). It explains the architecture, local setup, data flows, tool contracts, how STT/TTS/LLM are wired, how the frontend would interact with the agent, and how to make safe changes.

### What this project is
- A voice assistant for Birla Opus stakeholders that can converse in Hindi/English and use domain tools to resolve common issues: KYC approval, point redemption, QR scanning, and account blocks.
- Built on LiveKit Agents for Python, which provides an event-driven runtime for real-time LLM agents over audio/video.

---

## High-level architecture

- Agent process
  - Entry file: `src/agent.py`
  - Class `Assistant` extends `Agent` and provides:
    - A long, domain-specific system prompt that enforces conversation policy and tool usage order.
    - Function tools (decorated methods) the LLM can call during a conversation.
  - `entrypoint(ctx)` constructs an `AgentSession` which wires:
    - LLM: Google Gemini via `livekit.plugins.google.LLM`
    - STT: Google STT via `google.STT`
    - TTS: Google TTS via `google.TTS`
    - VAD: `silero.VAD`
    - Optional: noise cancellation (commented), turn detection, metrics collection
  - The agent participates in a LiveKit room and communicates with clients via LiveKit SFU.

- Tools layer (`src/tools/*`)
  - Small, focused utilities that read CSV/JSON in `data/` and return structured results used by the assistant:
    - `customer_lookup.py`: find customers by phone or Opus ID from `data/mock.csv`
    - `phone_verification.py`: verify phone → list matching accounts from `data/mock.csv`
    - `kyc_status_checker.py`: compute KYC status/timeline from `data/mock.csv`
    - `code_history_tool.py`: QR scan history from `data/code_history.csv` with reference enrich from `data/code_history_reference.csv`
    - `cash_transfer_tool.py`: cash transfer history and redemption eligibility from `data/cash_transfer.csv` with reference enrich from `data/cash_transfer_reference.csv` and balance from `data/point_history.csv`
    - `account_block_status.py`: account block status from `data/mock_extended.csv`
    - `complaint_manager.py`: create complaint/enquiry records in `data/complaints.json` and helper record-creators for code-history/block flows
    - `instruction_loader.py`: maps intents → instruction text files under `data/Instructions/`
    - `intent_classifier.py`: simple regex-based intent detection across Hindi/English/Hinglish patterns
    - `hardcoded_context.py`: returns a sample registered phone for demo/dev

- Instruction flows (`data/Instructions/*.txt`)
  - Plain-text scripts followed verbatim once an intent is identified. Loaded by `instruction_loader.py`.

- Data dir (`/data`)
  - CSV/JSON mock datasets for local development and tool testing.

---

## Conversation flow (enforced in `Assistant.instructions`)

1) Greet and listen
2) Classify intent using `classify_customer_intent` (must run before any other tool)
3) Load the appropriate instructions with `load_instructions_for_intent`
4) When intent is unclear, ask a short, templated clarification (only if last classification returned UNCLEAR)
5) Execute required tools silently in one turn, then send a single consolidated reply (no streaming of intermediate tool results)
6) Offer additional help
7) Close the call and ensure an enquiry/complaint record exists (using the dedicated record creators or `ensure_record_creation_tool`)

---

## How STT, TTS, and the “brain” (LLM) are wired

- The “brain” is an LLM set on the `AgentSession` (here: `google.LLM(model="gemini-2.5-flash")`).
- STT (speech-to-text) converts incoming audio into text: `google.STT(model="telephony", spoken_punctuation=False, languages=["en-IN"], use_streaming=True)`.
- TTS (text-to-speech) converts model replies into audio: `google.TTS(gender="female", voice_name="hi-IN-Chirp3-HD-Achernar", language="hi-IN", use_streaming=True)`.
- VAD (voice activity detection) is used to find turns: `silero.VAD`.
- The LiveKit Agents runtime handles full-duplex audio, turn-taking, and function calls exposed by `@function_tool()`.

You can swap providers (e.g., OpenAI Realtime, Deepgram, Cartesia) by changing `AgentSession` construction. A commented sample for OpenAI Realtime is already in `src/agent.py`.

---

## Frontend and backend communication

- LiveKit acts as the real-time layer. The agent runs as a participant in a LiveKit room.
- A web or mobile frontend connects to the same LiveKit room and exchanges audio with the agent in real time.
- For a ready-made frontend, see the README links to LiveKit example clients (React, Flutter, iOS, Android, etc.).

---

## Local development setup

Prerequisites
- Python 3.9+
- [uv](https://github.com/astral-sh/uv) for managing the virtual environment and running commands
- A LiveKit deployment (Cloud or self-hosted) and API keys
- Provider credentials for the chosen LLM/STT/TTS

Steps
1) Install deps
   - `uv sync`
2) Create environment file
   - Copy `.env.example` → `.env.local` (if not present in the repo, create `.env.local` manually) and set:
     - `LIVEKIT_URL`
     - `LIVEKIT_API_KEY`
     - `LIVEKIT_API_SECRET`
     - Provider keys (pick those you actually use):
       - For Google providers: `GOOGLE_API_KEY` (Gemini) and/or `GOOGLE_APPLICATION_CREDENTIALS` (path to a JSON key) for STT/TTS, depending on your setup
       - For OpenAI: `OPENAI_API_KEY`
       - For Deepgram: `DEEPGRAM_API_KEY`
       - For Cartesia: `CARTESIA_API_KEY`
3) Download models
   - `uv run python src/agent.py download-files` (Silero VAD, etc.)
4) Run in console (local mic/speaker)
   - `uv run python src/agent.py console`
5) Run agent server for frontend/telephony
   - `uv run python src/agent.py dev`
6) Production entry
   - `uv run python src/agent.py start`

Notes
- The project loads environment from `.env.local` automatically.
- For LiveKit Cloud, you can also load env with `lk app env -w .env.local`.

---

## Project structure

```
src/
  agent.py                # Agent class, tools exposure, AgentSession wiring
  tools/
    account_block_status.py
    cash_transfer_tool.py
    code_history_tool.py
    complaint_manager.py
    customer_lookup.py
    hardcoded_context.py
    instruction_loader.py
    intent_classifier.py
    kyc_status_checker.py
    phone_verification.py
data/
  mock.csv, mock_extended.csv, point_history.csv,
  code_history.csv, code_history_reference.csv,
  cash_transfer.csv, cash_transfer_reference.csv,
  complaints.json,
  Instructions/*.txt
tests/
  test_agent.py           # Template tests (see Issues below)
```

---

## Tool glossary and contracts

Return shapes vary today (some return strings, others dicts). Standardizing on dicts is recommended (see Improvements).

- Identity & lookup
  - `hardcoded_context_tool() -> str`: returns a known registered number for demos
  - `verify_phone_number(phone_number) -> { success, is_registered, accounts[] }`
  - `customer_lookup_tool(mobile_number) -> str`
  - `customer_lookup_by_opus_id_tool(opus_id) -> str`

- KYC
  - `kyc_status_checker_tool(opus_id) -> { kyc_status, timeline_info, recommendation, message, ... }`

- QR scan history
  - `code_history_tool(...) -> { entries[], summary, advice[], message, requires_kyc_check, derived }`

- Points/redemption
  - `cash_transfer_history_tool(opus_pc_id, limit=3) -> { entries[], summary, point_balance, redemption_eligibility, advice[], message }`

- Account blocks
  - `account_block_status_tool(opus_id|mobile_number) -> { customer, block, timeline_info, recommendation, advice[], message }`

- Complaints/enquiries
  - `auto_create_complaint_tool(...)` (recommendation only; requires consent)
  - `create_complaint_tool(...)` (creates complaint in `data/complaints.json`)
  - `create_enquiry_tool(...)` (creates enquiry in `data/complaints.json`)
  - `create_record_from_code_history(...)` and `create_record_from_account_block(...)` (heuristic helpers)
  - `ensure_record_creation_tool(opus_id, customer_name, context) -> complaint recommendation or enquiry creation`

- Intent & instructions
  - `classify_customer_intent(customer_query) -> { intent, confidence, next_steps }`
  - `load_instructions_for_intent(intent, scenario?) -> { instructions, filename, summary }`
  - `get_available_instruction_flows() -> inventory`
  - `validate_instruction_files() -> validation report`

---

## Making changes

- Add a new tool
  1) Create `src/tools/my_tool.py` with a small, testable function. Prefer returning a dict with stable keys that the LLM can rely on.
  2) Expose it to the agent:
     - Option A: Import the pure function into `src/agent.py` and wrap it in an `@function_tool()` method on `Assistant` that delegates to your function.
     - Option B (advanced): Use `@function_tool()` at module level and register it explicitly for the agent (current pattern uses the class method approach).
  3) Mention it in the `Assistant.instructions` only if the tool is part of the scripted flows.

- Change STT/TTS/LLM
  - Modify `AgentSession` in `entrypoint()` (e.g., swap to OpenAI Realtime, Deepgram, or Cartesia). Keep VAD/turn-taking tuned for call quality.

- Update flows
  - Edit instruction text files under `data/Instructions/`.
  - Update `instruction_loader.py` mappings if you add a new file or scenario.

- Update datasets
  - CSVs in `data/` are read-only fixtures for local/dev. Keep headers stable; update parsing if you add columns.

---

## Known issues and blockers (today)

1) Tool duplication and drift
   - Several tools are defined twice: once as class methods in `src/agent.py` and again in `src/tools/*` (e.g., `verify_phone_number`, `kyc_status_checker_tool`, `hardcoded_context_tool`, complaint/enquiry creation).
   - Risk: behavioral drift, inconsistent return shapes, and harder testing.
   - Fix (quick): Make `Assistant` tool methods thin wrappers that delegate to the module functions. Do not reimplement logic inside `agent.py`.

2) Mixed return types across tools
   - Some tools return strings (often embedding data in a sentence), others return dicts.
   - This increases LLM prompting burden and adds parsing ambiguity.
   - Fix (quick): Standardize tool outputs to typed dicts with stable keys. Keep short human-readable `message` in addition.

3) README doesn’t match providers used in code
   - The current pipeline uses Google LLM/STT/TTS, while the README highlights OpenAI/Cartesia/Deepgram.
   - Fix (quick): Adjust README to list Google as the current default and add environment guidance.

4) Template tests reference non-existent tools
   - `tests/test_agent.py` expects a `lookup_weather` tool that doesn’t exist here.
   - Consequence: CI/test runs will fail or mislead contributors.
   - Fix (quick): Replace with unit tests for real tools (intent classification, instruction loading, CSV-backed tools). Remove weather tests.

5) Unused imports and features
   - Turn detector model is imported but unused; noise cancellation commented.
   - Fix (quick): Remove unused imports or wire the detector if needed.

6) Hardcoded demo phone
   - `hardcoded_context_tool` returns a fixed number for demos.
   - Fix (later): Replace with a feature-flagged or environment-driven behavior for production.

7) Path helpers repeated across modules
   - Each tool computes `project_root` and file paths similarly.
   - Fix (later): Extract to `src/utils/paths.py` to centralize.

8) Language/tone strings embedded in the system prompt
   - Long instruction text inside `agent.py` is harder to revise/reuse.
   - Fix (later): Move the conversation policy to a separate file and load at startup.

---

## Immediate improvements (recommended order)

1) Unify tools
   - Convert all tool methods in `Assistant` into thin wrappers that call `src/tools` functions.
   - Ensure every tool returns a dict with stable keys and a concise `message` field.

2) Update README and env guidance
   - Declare Google as the default stack used here; add `GOOGLE_API_KEY`/`GOOGLE_APPLICATION_CREDENTIALS` notes.

3) Fix tests
   - Remove weather tests and add:
     - `intent_classifier` unit tests
     - `instruction_loader` validation test
     - Happy-path tests for `code_history_tool`, `cash_transfer_tool`, `account_block_status_tool` with small fixture slices

4) Remove unused imports
   - Delete unused turn-detector import or wire it correctly.

5) Introduce a minimal utils module
   - `src/utils/paths.py` for shared `data` path helpers.

---

## Troubleshooting

- No audio or agent doesn’t speak
  - Check `LIVEKIT_*` credentials
  - Ensure `.env.local` is loaded
  - Verify provider keys and quotas

- Tool returns “file not found”
  - Confirm `data/*.csv` exist and paths are correct
  - Run from repository root so relative paths resolve

- Tests fail referencing weather
  - Replace template tests as noted above

---

## Deployment

- A `Dockerfile` is provided. Ensure `.env` handling for provider credentials and mount or bake in any model files that aren’t downloaded at runtime.
- For LiveKit Cloud, follow the official deployment guide and configure environment via LiveKit CLI or the Cloud dashboard.

---

## Quick reference

- Dev setup
  - `uv sync`
  - `.env.local` with LiveKit + provider keys
  - `uv run python src/agent.py download-files`
  - `uv run python src/agent.py console` or `dev`

- Key files
  - `src/agent.py` – agent wiring and tool exposure
  - `src/tools/*` – domain tools over CSV/JSON
  - `data/Instructions/*` – flow scripts



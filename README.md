# wca-ai-tool-s12-Apex-minds

**We Can Academy – AI Course, Season 12 group project**
**Group members:** 3922, 2633, 1019 (https://github.com/Mifar52,https://github.com/christopherwaweru820-droid, https://github.com/simonkiragu004-dot)

## What it does
A command-line chatbot for a fictional clinic (Afya Bora Community Clinic, Nairobi).
Patients ask about opening hours, services, prices and booking. The tool:
- remembers the whole conversation (full message list sent with every API call)
- does not repeat answers it already gave
- refuses to give a diagnosis
- checks every AI reply (JSON with required fields, one retry on failure)
- ends with an AI-written summary, saved to `sessions/session_<date>_<time>.json`

## How to run
1. Install Python 3.10+.
2. Install packages: `pip install -r requirements.txt`
3. Get an Anthropic API key (console.anthropic.com) and set it (see below).
4. Run: `python clinic_assistant.py`
5. Menu: **1** new session, **2** open a past session, **3** exit. Type `end` to finish a session.

## How to set the API key
Copy `.env.example` to `.env` with your own key:
```
ANTHROPIC_API_KEY=your-key-here
```
`.env` is listed in `.gitignore`, so it is never committed. **Never paste a key into the code.**

## Repository contents
- `clinic_assistant.py` – the program
- `requirements.txt` – packages
- `samples/` – one saved session from our testing
- `sessions/` – new sessions are saved here (ignored by git)

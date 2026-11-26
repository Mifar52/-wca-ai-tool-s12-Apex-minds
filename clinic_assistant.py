"""
Clinic FAQ Assistant - We Can Academy, AI Course, Season 12 group project.

A command-line chatbot for a (fictional) small clinic. It answers questions
about hours, services, prices and booking, remembers the whole conversation,
refuses to diagnose, and saves a summary of the session to a dated JSON file.
"""

import glob
import json
import os
from datetime import datetime

import anthropic
from dotenv import load_dotenv

# 1. SETTINGS
# ---------------------------------------------------------------------------
load_dotenv()  # loads ANTHROPIC_API_KEY from the .env file (never hard-coded)

MODEL = "claude-haiku-5-5"      # small, fast model - good for a chatbot
SESSIONS_DIR = "sessions"       # where new sessions are saved
SAMPLES_DIR = "samples"         # where the sample session lives

# Fields every chat reply must contain (checked by validate_fields)
REPLY_FIELDS = ["answer", "topic", "is_diagnosis_request", "already_answered"]
# Fields every summary must contain
SUMMARY_FIELDS = ["overview", "questions_and_answers", "topics_covered"]

# ---------------------------------------------------------------------------
# 2. PROMPTS (both follow R-T-C-C-O: Role, Task, Context, Constraints, Output)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
ROLE:
You are "Afya Assistant", the friendly virtual receptionist of Afya Bora
Community Clinic in Nairobi, Kenya. You speak politely and simply.

TASK:
Answer the patient's questions about the clinic's opening hours, services,
prices and booking. Use everything said earlier in this conversation: if the
patient asks something you already answered, do not repeat the full answer.
Briefly remind them of it and offer to help with something else.

CONTEXT (the only clinic information you may use):
- Name: Afya Bora Community Clinic, Tom Mboya Street, Nairobi.
- Opening hours: Monday to Friday 8:00am-6:00pm, Saturday 9:00am-1:00pm.
  Closed on Sundays and public holidays.
- Services and prices (KES): General consultation 1,000. Dental check-up
  1,500. Antenatal visit 1,200. Family planning visit 500. Child
  immunisation visit 500 (vaccine itself is free for the national
  schedule). Lab tests: malaria test 300, blood sugar test 200, full blood
  count 800.
- Booking: call or WhatsApp 0700 000 000 (reception, during opening hours),
  or walk in. Walk-ins are seen in order of arrival. Booked patients are
  seen first. Please arrive 10 minutes early.
- Payment: cash or M-Pesa at reception. Ask reception about insurance.
- Emergencies: the clinic does not handle emergencies. Go to the nearest
  hospital or call 999 / 112.

CONSTRAINTS:
- Use ONLY the clinic information above. If the answer is not there, say you
  do not know and suggest calling reception. Never invent prices or hours.
- NEVER diagnose, name possible illnesses, or suggest medicines or doses.
  If the patient asks for this, politely decline, set
  is_diagnosis_request to true, and suggest booking a consultation (or going
  to a hospital if it sounds urgent).
- Keep answers to a maximum of 3 short sentences.
- Reply in the language the patient uses (English or Kiswahili).

OUTPUT:
Reply with ONLY a JSON object, no markdown, no extra text, with exactly
these fields:
{
  "answer": "your reply to the patient",
  "topic": "one of: hours, services, prices, booking, payment, emergency, diagnosis, other",
  "is_diagnosis_request": true or false,
  "already_answered": true or false
}
""".strip()

SUMMARY_PROMPT = """
ROLE:
You are a careful clinic records assistant at Afya Bora Community Clinic.

TASK:
Summarise the conversation between a patient and the clinic's virtual
receptionist. List every question the patient asked, with the answer given.

CONTEXT:
The next message is the full transcript of one session. Lines starting with
"Patient:" are the patient's questions. Lines starting with "Assistant:" are
the answers that were given.

CONSTRAINTS:
- Use only what is in the transcript. Do not add or invent anything.
- Include every patient question, in the order asked.
- Do not include any medical advice or diagnosis.
- Keep each answer to one short sentence.

OUTPUT:
Reply with ONLY a JSON object, no markdown, no extra text, with exactly
these fields:
{
  "overview": "one or two sentences describing what the patient wanted",
  "questions_and_answers": [
    {"question": "...", "answer": "..."}
  ],
  "topics_covered": ["topic1", "topic2"]
}
""".strip()

# 3. API CALL AND ANSWER CHECK
# ---------------------------------------------------------------------------
def ask_model(system_prompt, messages):
    """Send the system prompt and the FULL message list to the model.
    Returns the reply text. Raises an exception if the call fails."""
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
    response = client.messages.create(
        model=MODEL,
        max_tokens=800,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


def parse_json(raw_text):
    """Turn the model's reply into a dict. Raises ValueError if it is not
    a valid JSON object. Removes json fences if the model added them."""
    text = raw_text.strip()
    if text.startswith(""):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:]
    data = json.loads(text)  # json.JSONDecodeError is a kind of ValueError
    if not isinstance(data, dict):
        raise ValueError("JSON is not an object")
    return data

def validate_fields(data, required_fields):
    """Check every required field is present and not empty.
    Returns a list of the fields that are missing or empty."""
    problems = []
    for field in required_fields:
        value = data.get(field)
        empty_text = isinstance(value, str) and not value.strip()
        empty_list = isinstance(value, list) and len(value) == 0
        if value is None or empty_text or empty_list:
            problems.append(field)  # note: False is a valid, non-empty value
    return problems


def get_valid_reply(system_prompt, messages, required_fields):
    """Call the model and check the reply. If the call or the check fails,
    retry ONCE. Returns the checked dict, or None if both attempts fail."""
    for attempt in (1, 2):
        extra = ""
        if attempt == 2:
            extra = ("\n\nIMPORTANT: your previous reply was invalid. Reply "
                     "with ONLY the JSON object, with every field filled in.")
        try:
            raw = ask_model(system_prompt + extra, messages)
        except Exception as error:  # no internet, bad key, rate limit...
            print(f"  [Connection problem: {error}]")
            continue
        try:
            data = parse_json(raw)
        except ValueError:
            print("  [The reply was not valid JSON]")
            continue
        problems = validate_fields(data, required_fields)
        if problems:
            print(f"  [The reply had missing or empty fields: {problems}]")
            continue
        return data
    return None

    # 4. SESSION: CHAT LOOP, SUMMARY, SAVING
# ---------------------------------------------------------------------------
def build_transcript(log):
    """Turn the saved turns into plain text for the summary call."""
    lines = []
    for turn in log:
        lines.append(f"Patient: {turn['patient']}")
        lines.append(f"Assistant: {turn['assistant']}")
    return "\n".join(lines)

def summarise(log):
    """Final AI call: summarise the whole conversation using SUMMARY_PROMPT.
    If it fails, build a simple summary without AI so nothing is lost."""
    messages = [{"role": "user", "content": build_transcript(log)}]
    summary = get_valid_reply(SUMMARY_PROMPT, messages, SUMMARY_FIELDS)
    if summary is None:
        print("  [AI summary unavailable - saving a basic summary instead]")
        summary = {
            "overview": "AI summary could not be created for this session.",
            "questions_and_answers": [
                {"question": t["patient"], "answer": t["assistant"]}
                for t in log
            ],
            "topics_covered": sorted({t["topic"] for t in log}),
        }
    return summary

def save_session(log, summary):
    """Save the conversation and summary to sessions/ with the date and time
    in the file name. Returns the file path, or None if saving fails."""
    now = datetime.now()
    path = os.path.join(
        SESSIONS_DIR, f"session_{now.strftime('%Y-%m-%d_%H-%M-%S')}.json")
    record = {
        "date": now.strftime("%Y-%m-%d %H:%M:%S"),
        "conversation": log,
        "summary": summary,
    }
    try:
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(record, file, indent=2, ensure_ascii=False)
        return path
    except OSError as error:
        print(f"  [Could not save the session: {error}]")
        return None


def display_summary(summary):
    """Print a summary in a readable way."""
    print("\n=== SESSION SUMMARY ===")
    print(summary["overview"])
    print("\nQuestions and answers:")
    for number, item in enumerate(summary["questions_and_answers"], start=1):
        print(f"  {number}. Q: {item['question']}")
        print(f"     A: {item['answer']}")
    print("\nTopics covered: " + ", ".join(summary["topics_covered"]))

    def run_session():
    """One conversation. 'messages' is the memory: it is sent in full with
    every API call, so the AI can use everything said earlier."""
    messages = []   # what the AI sees (alternating user / assistant)
    log = []        # what we save to the file
    print("\nAfya Assistant: Hello! Ask me about our hours, services, prices "
          "or booking.")
    print("(Type 'end' to finish the session.)")

    while True:
        try:
            user_text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_text:                      # empty input is handled
            print("Afya Assistant: Please type a question first.")
            continue
        if user_text.lower() in ("end", "quit", "exit"):
            break

        messages.append({"role": "user", "content": user_text})
        data = get_valid_reply(SYSTEM_PROMPT, messages, REPLY_FIELDS)

        if data is None:                       # both attempts failed
            messages.pop()                     # forget this failed question
            print("Afya Assistant: Sorry, I could not answer just now. "
                  "Please try again, or call reception on 0795 000 000.")
            continue

# Add the checked reply to memory and to the save-log
        messages.append({"role": "assistant",
                         "content": json.dumps(data, ensure_ascii=False)})
        log.append({
            "patient": user_text,
            "assistant": data["answer"],
            "topic": data["topic"],
            "is_diagnosis_request": data["is_diagnosis_request"],
            "already_answered": data["already_answered"],
        })
        print(f"\nAfya Assistant: {data['answer']}")

    if not log:
        print("\nNo questions were asked, so nothing was saved.")
        return

    print("\nCreating your session summary...")
    summary = summarise(log)
    display_summary(summary)
    path = save_session(log, summary)
    if path:
        print(f"\nSession saved to: {path}")
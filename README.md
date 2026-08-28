<<<<<<< HEAD
<<<<<<< HEAD
# WhatsApp-AI-Notification-Router
I got tired of WhatsApp notifications, so I built an enterprise-grade AI router. It uses Google Gemini to read my texts, look at images/voice notes, judge the sender's trust score, and decide whether to ping my phone, drop it in a SQLite database, or text them back automatically.
=======
# WhatsApp AI Notification Router (Enterprise)

An intelligent, AI-powered WhatsApp message notification router that uses Google Gemini to automatically filter, digest, and reply to messages based on user preferences, trust scores, and multimodal content analysis.

This Enterprise edition features a full **FastAPI** webhook server, **SQLAlchemy** asynchronous database storage, an interactive **Analytics Dashboard**, and **Two-Way Agentic Replies** via the official Meta WhatsApp Cloud API.

---

## 🚀 Enterprise Features

* **Meta Webhook Integration:** A production-ready FastAPI endpoint that receives, parses, and acknowledges live WhatsApp webhooks.
* **Two-Way Agentic Replies:** When a user asks a direct question (e.g. "What time is the meeting?"), the AI can choose the `reply` action and instantly send a WhatsApp text back to the sender via the Meta Graph API.
* **Asynchronous Database:** Uses SQLAlchemy 2.0 and SQLite (or PostgreSQL) to securely log all user profiles, sender context, and routing decisions.
* **Live Dashboard:** A real-time HTML dashboard (`http://localhost:8000/`) that polls the database to display the latest routed messages, AI reasoning, and automated replies.
* **Multimodal Analysis:** Processes images, audio (voice notes), and text to determine priority.
* **Dynamic Trust Scoring:** Learns from history to auto-mute spam and promote high-trust contacts.

---

## 🛠️ Installation & Setup

### 1. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy the example environment file and fill in your keys:
```bash
cp .env.example .env
```
You will need:
* `GEMINI_API_KEY`: Get this from Google AI Studio.
* `META_VERIFY_TOKEN`: A random string you choose to verify the Meta webhook.
* `META_ACCESS_TOKEN`: Your Permanent Page Access Token from the Meta App Dashboard.
* `META_PHONE_NUMBER_ID`: The Phone Number ID assigned to your real WhatsApp Business number.

### 3. Run the Server
```bash
uvicorn src.router.api:app --reload
```
The server will start on `http://127.0.0.1:8000`.

### 4. Connect to Meta (WhatsApp Cloud API)
1. Expose your local server using Ngrok: `ngrok http 8000`
2. Go to your **Meta App Dashboard** > **WhatsApp** > **Configuration**.
3. Set your Callback URL to `https://<your-ngrok-url>.ngrok-free.dev/webhook`.
4. Enter your `META_VERIFY_TOKEN` and click **Verify and Save**.
5. Subscribe to the `messages` webhook field.
6. *(Important)* If you are using a physical phone to test, ensure your app is in **Live Mode**, or use a verified test number in **Development Mode** following Meta's 24-hour sandbox rules.

---

## 💻 The Dashboard
Navigate to `http://localhost:8000/` in your browser while the server is running to view the live analytics dashboard. You will see messages appear in real-time as they are processed by the AI.

---

## 📁 Project Structure

```
whatsapp-notification-router/
├── .env.example                       # Environment variables template
├── requirements.txt                   # Project dependencies
├── pyproject.toml                     # Package configuration
├── router.db                          # SQLite database (auto-generated)
├── src/
│   └── router/
│       ├── api.py                     # FastAPI server and webhook endpoints
│       ├── config.py                  # API settings, thresholds, safety lists
│       ├── database.py                # SQLAlchemy async engine setup
│       ├── db_models.py               # Database table schemas
│       ├── engine.py                  # Core routing logic & AI orchestration
│       ├── meta_api.py                # Outbound WhatsApp Graph API client
│       ├── models.py                  # Pydantic data schemas
│       ├── prompt.py                  # Gemini prompt composition
│       ├── webhook.py                 # Meta webhook parsing logic
│       ├── webhook_models.py          # Strict Pydantic models for Meta payloads
│       └── dashboard.html             # UI for the live analytics dashboard
└── tests/
    ├── conftest.py                    # Pytest async database fixtures
    ├── test_api.py                    # Webhook API integration tests
    ├── test_engine.py                 # Core routing unit tests
    └── test_prompt.py                 # Prompt building tests
```

---

## 🧪 Testing

Run the automated test suite with `pytest`:
```bash
pytest tests/
```

---

## 📄 License
MIT License. Designed for privacy-first, intelligent message routing.
>>>>>>> f4db39c (Initial commit: WhatsApp AI Notification Router)
=======
# WhatsApp-AI-Notification-Router
I got tired of WhatsApp notifications, so I built an enterprise-grade AI router. It uses Google Gemini to read my texts, look at images/voice notes, judge the sender's trust score, and decide whether to ping my phone, drop it in a SQLite database, or text them back automatically.
>>>>>>> 30b60334da54bfef36cefdd94dcb39815a5e2361

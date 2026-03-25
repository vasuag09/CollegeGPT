# WhatsApp Integration Guide — NM-GPT

This document outlines the step-by-step process of connecting the **NM-GPT FastAPI backend** to a WhatsApp Bot using **Twilio**. 

By completing this guide, students will be able to text your assistant's phone number as if it were a real person, and receive context-aware, cited answers powered by the existing RAG pipeline.

---

## 1. Prerequisites (Twilio Sandbox)

Since applying for an official WhatsApp Business API account takes time, we will use the **Twilio Sandbox for WhatsApp** for prototyping.

1. Create a free account at [Twilio.com](https://www.twilio.com/).
2. Navigate to **Messaging > Try it out > Send a WhatsApp message**.
3. Activate the sandbox. Twilio will assign you a phone number and a join code (e.g., `join purple-lion`).
4. Any phone number that sends this join code to your Twilio number is automatically opted in to test the bot.

---

## 2. Install Dependencies

You will need the official Twilio Python SDK to efficiently parse incoming requests and generate outgoing WhatsApp responses (TwiML).

```bash
pip install twilio
pip freeze > requirements.txt
```

---

## 3. Environment Variables

Store your Twilio credentials safely. Update your `backend/config.py` and `.env` files.

**`.env`**
```env
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
```

**`backend/config.py`**
```python
import os

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
```

---

## 4. Add the Webhook Endpoint (`backend/app.py`)

Whenever a student sends a message, Twilio automatically fires an HTTP `POST` request to your backend containing the message body and the sender's phone number.

Import these at the top of `backend/app.py`:
```python
from fastapi import Form, Response
from twilio.twiml.messaging_response import MessagingResponse
from typing import Optional
```

Add the `POST /webhook/whatsapp` route above the main `app` instantiation:

```python
# In-memory dictionary to store conversational history per phone number (prototyping only)
# Format: {"+1234567890": [{"role": "user", "content": "..."}, ...]}
whatsapp_sessions = {}

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    From: str = Form(...),  # The sender's phone number (acts as session ID)
    Body: str = Form(...)   # The message content they sent
):
    """
    Receives incoming WhatsApp messages from Twilio, passes them through the RAG pipeline, 
    and returns a TwiML formatted XML response.
    """
    question = Body.strip()
    
    # Instantiate the existing RAG pipeline
    pipeline = get_pipeline()
    
    # Retrieve past conversation history for this specific phone number
    history = whatsapp_sessions.get(From, [])
    
    # Query the RAG Engine (Conversational Memory & Context Included)
    result = pipeline.query(question=question, top_k=5, history=history)
    answer = result["answer"]
    
    # Format the reply string cleanly
    if result["citations"]:
        citations_text = ", ".join(set([c["source"] for c in result["citations"]]))
        reply_text = f"{answer}\n\n*Source:* {citations_text}"
    else:
        reply_text = answer

    # Update in-memory history (keep the last 4 turns to save LLM tokens)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    whatsapp_sessions[From] = history[-6:]  # Keep last 3 pairs

    # Generate Twilio XML response
    twiml = MessagingResponse()
    twiml.message(reply_text)
    
    # Twilio requires an application/xml response payload
    return Response(content=str(twiml), media_type="application/xml")
```

---

## 5. Exposing Your Server (Local Dev)

Twilio lives on the internet and cannot reach a `localhost` URL. You must expose your running FastAPI server to a public URL.

1. Start your backend as usual:
   ```bash
   python -m uvicorn backend.app:app --host localhost --port 8000
   ```
2. Install [ngrok](https://ngrok.com/) and create a secure tunnel:
   ```bash
   ngrok http 8000
   ```
3. Ngrok will give you a public URL (e.g., `https://a1b2c3d4.ngrok-free.app`).

---

## 6. Connect the Webhook to Twilio

1. Go back to your Twilio Console -> **WhatsApp Sandbox Settings**.
2. Find the field labeled **"WHEN A MESSAGE COMES IN"**.
3. Paste the full ngrok webhook URL you just created: 
   `https://a1b2c3d4.ngrok-free.app/webhook/whatsapp`
4. Set the HTTP method to **POST**.
5. Save your settings.

---

## 7. Next Steps & Production Setup

Your WhatsApp bot is now fully functional locally! When you are ready for production:

*   **Database History:** Instead of the `whatsapp_sessions` dict, store the conversation arrays in your existing Supabase database.
*   **Production Webhook:** Update the Twilio URL from the ngrok address to your live Render backend URL (`https://nmgpt-api.onrender.com/webhook/whatsapp`).
*   **Rate Limiting:** Protect your webhook using FastAPI SlowAPI similar to the `/query` endpoints, ensuring external malicious requests don't spike your LLM token usage.

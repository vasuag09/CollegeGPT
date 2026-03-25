import pytest
from backend.app import whatsapp_sessions

def test_whatsapp_webhook_valid(client, mock_pipeline):
    response = client.post(
        "/webhook/whatsapp",
        data={"From": "whatsapp:+1234567890", "Body": "What is the attendance policy?"}
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml"
    
    text = response.text
    assert "<Response><Message>" in text
    assert "The minimum attendance requirement is 75%" in text
    assert "Student Resource Book" in text

    # Check history dictionary
    assert "whatsapp:+1234567890" in whatsapp_sessions
    history = whatsapp_sessions["whatsapp:+1234567890"]
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "What is the attendance policy?"

def test_whatsapp_webhook_history_is_passed(client, mock_pipeline):
    # Clear the global for test isolation
    whatsapp_sessions.clear()
    
    # 1. First turn
    client.post("/webhook/whatsapp", data={"From": "whatsapp:+111", "Body": "First message"})
    
    # 2. Second turn
    client.post("/webhook/whatsapp", data={"From": "whatsapp:+111", "Body": "Second message"})
    
    # Check the call args to pipeline.query for the second turn
    call_kwargs = mock_pipeline.query.call_args[1]
    history = call_kwargs.get("history")
    
    assert history is not None
    # History has 4 items because the route appended the second turn's QA before the test ran assertion
    assert len(history) == 4
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "First message"
    assert history[1]["role"] == "assistant"
    # The assistant content should match the mock's return value
    assert "75%" in history[1]["content"]

def test_whatsapp_webhook_handles_pipeline_error(client, mock_pipeline):
    mock_pipeline.query.side_effect = Exception("Simulated pipeline failure")
    
    response = client.post(
        "/webhook/whatsapp",
        data={"From": "whatsapp:+error", "Body": "Fail me"}
    )
    
    # We catch the exception and return a friendly TwiML instead of crashing
    assert response.status_code == 200
    assert "unable to access my knowledge base" in response.text

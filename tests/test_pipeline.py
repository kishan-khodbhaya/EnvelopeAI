import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def get_base_envelope():
    return {
        "envelope_id": "env_20260324_test",
        "schema_version": "envelope-v1",
        "tenant": {"id": "tenant1", "name": "Tenant 1"},
        "document": {"type": "manifest", "filename": "1.pdf", "page_count": 1},
        "processing_instructions": {
            "workflow": "v1",
            "confidence_threshold": 0.80,
            "hitl_on_failure": True
        },
        "extraction": {
            "shipment_id": {"value": "SHP-123", "confidence": 0.95},
            "ship_date": {"value": "2026-03-20", "confidence": 0.90},
            "recipient_name": {"value": "John Doe", "confidence": 0.90},
            "commodity_code": {"value": "8471.30.0100", "confidence": 0.90},
            "commodity_desc": {"value": "portable digital automatic data processing machine under 10kg", "confidence": 0.95}
        }
    }

def test_happy_path_auto_approve():
    envelope = get_base_envelope()
    response = client.post("/process", json=envelope)
    assert response.status_code == 200
    data = response.json()
    assert data["validation_results"]["is_valid"] == True
    assert data["decision"]["route"] == "auto_approve"
    assert len(data["audit"]) == 1

def test_low_confidence_recipient_hitl_review():
    envelope = get_base_envelope()
    envelope["extraction"]["recipient_name"]["confidence"] = 0.50
    response = client.post("/process", json=envelope)
    assert response.status_code == 200
    data = response.json()
    assert data["validation_results"]["is_valid"] == False
    assert "recipient_name" in data["validation_results"]["failed_fields"]
    assert data["decision"]["route"] == "hitl_review"

def test_low_commodity_confidence_triggers_llm(monkeypatch):
    envelope = get_base_envelope()
    envelope["extraction"]["commodity_code"]["confidence"] = 0.60
    
    def mock_get_settings():
        from app.config import Settings
        return Settings(gemini_api_key="") 
    monkeypatch.setattr("app.services.matcher.get_settings", mock_get_settings)
    
    response = client.post("/process", json=envelope)
    assert response.status_code == 200
    data = response.json()
    
    assert data["validation_results"]["is_valid"] == False
    assert data["matching_results"] is not None
    assert data["matching_results"]["matched_code"] == "8471.30.0100"
    assert data["matching_results"]["fallback_used"] == True
    assert "llm_match" in data["matching_results"]["source"]
    assert len(data["audit"]) == 2

def test_invalid_schema_422():
    envelope = get_base_envelope()
    del envelope["tenant"] 
    
    response = client.post("/process", json=envelope)
    assert response.status_code == 422
    data = response.json()
    assert "failed_fields" in data

@pytest.mark.asyncio
async def test_llm_failure_timeout(monkeypatch):
    from app.models.envelope import ExecutionEnvelope
    from app.services.matcher import match_commodity
    
    envelope = get_base_envelope()
    def mock_get_settings():
        from app.config import Settings
        return Settings(gemini_api_key="T3stK3y") 
    monkeypatch.setattr("app.services.matcher.get_settings", mock_get_settings)
    
    import httpx
    class MockAsyncClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): pass
        async def post(self, *args, **kwargs):
            raise httpx.ReadTimeout("Mocked timeout")
    
    monkeypatch.setattr("httpx.AsyncClient", MockAsyncClient)
    
    env_obj = ExecutionEnvelope(**envelope)
    env_obj.decision = type('obj', (object,), {'route': 'auto_approve'})() # fake decision before matching
    
    result = await match_commodity(env_obj)
    
    assert result.matching_results is not None
    assert result.matching_results.fallback_used == False
    assert result.matching_results.source == "no_match"
    assert result.decision.route == "hitl_review"

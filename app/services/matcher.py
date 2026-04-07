import logging
import httpx
from datetime import datetime, timezone
from pydantic import BaseModel

from app.models.envelope import (
    ExecutionEnvelope,
    MatchResult,
    AuditEntry,
    Decision
)
from app.config import get_settings

logger = logging.getLogger(__name__)

REFERENCE_DATASET = [
    {"hs_code": "8471.30.0100", "description": "portable digital automatic data processing machine under 10kg", "category": "electronics", "restricted": False, "typical_weight_kg": 2.5},
    {"hs_code": "8517.12.0000", "description": "telephones for cellular networks or for other wireless networks", "category": "electronics", "restricted": False, "typical_weight_kg": 0.2},
    {"hs_code": "6203.42.4011", "description": "men's or boys' trousers, breeches, and shorts of cotton", "category": "clothing", "restricted": False, "typical_weight_kg": 0.5},
    {"hs_code": "3926.90.9985", "description": "other articles of plastics and articles of other materials of headings 3901 to 3914", "category": "plastics", "restricted": False, "typical_weight_kg": 1.0},
    {"hs_code": "9403.60.8081", "description": "other wooden furniture", "category": "furniture", "restricted": False, "typical_weight_kg": 25.0},
    {"hs_code": "0901.21.0010", "description": "coffee, roasted, not decaffeinated", "category": "food", "restricted": False, "typical_weight_kg": 1.0},
    {"hs_code": "4202.92.3131", "description": "travel, sports, and similar bags with outer surface of textile materials", "category": "accessories", "restricted": False, "typical_weight_kg": 1.5},
    {"hs_code": "9503.00.0073", "description": "toys representing animals or non-human creatures", "category": "toys", "restricted": False, "typical_weight_kg": 0.3},
    {"hs_code": "9018.90.8000", "description": "other instruments and appliances used in medical, surgical, dental or veterinary sciences", "category": "medical", "restricted": True, "typical_weight_kg": 5.0},
    {"hs_code": "3004.90.9200", "description": "medicaments consisting of mixed or unmixed products for therapeutic or prophylactic uses", "category": "medical", "restricted": True, "typical_weight_kg": 0.1}
]

class LLMOutput(BaseModel):
    matched_code: str
    match_confidence: float
    rationale: str

def _create_llm_prompt(description: str) -> str:
    catalog_str = "\n".join([f"- {r['hs_code']}: {r['description']}" for r in REFERENCE_DATASET])
    return f"""You are an expert customs classifier.
Match the following item description to the best HS code from the reference catalog.

Item description: '{description}'

Reference Catalog:
{catalog_str}

Return EXACTLY a JSON object with this structure and no additional text or formatting. DO NOT wrap it in markdown block.
{{
  "matched_code": "string",
  "match_confidence": float (0.0 to 1.0),
  "rationale": "string"
}}
"""

async def match_commodity(envelope: ExecutionEnvelope) -> ExecutionEnvelope:
    logger.info(f"Starting commodity matching for envelope_id={envelope.envelope_id}")
    
    settings = get_settings()
    extraction = envelope.extraction
    
    # Only run matching if we have a descriptor
    desc_val = None
    if extraction.commodity_desc and extraction.commodity_desc.value:
         desc_val = str(extraction.commodity_desc.value)
         
    if not desc_val:
        logger.info(f"No commodity description available for envelope_id={envelope.envelope_id}, skipping matching")
        return _append_fallback(envelope, reason="No commodity description")

    prompt = _create_llm_prompt(desc_val)
    
    if not settings.gemini_api_key:
         logger.warning("No GEMINI_API_KEY provided. Using mock matching logic.")
         mock_match = next((m for m in REFERENCE_DATASET if m["hs_code"] == "8471.30.0100"), REFERENCE_DATASET[0])
         match_result = MatchResult(
             matched_code=mock_match["hs_code"],
             match_confidence=0.85,
             rationale=f"Mock matched based on description fallback",
             fallback_used=True,
             source="llm_match"
         )
         return _apply_match_result(envelope, match_result, success=True)

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.gemini_api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.0
            }
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            raw_text = data['candidates'][0]['content']['parts'][0]['text']
            llm_output = LLMOutput.model_validate_json(raw_text)
            
            match_result = MatchResult(
                matched_code=llm_output.matched_code,
                match_confidence=llm_output.match_confidence,
                rationale=llm_output.rationale,
                fallback_used=True,
                source="llm_match"
            )
            
            envelope = _apply_match_result(envelope, match_result, success=True)
            
    except Exception as e:
        logger.error(f"LLM match failed for envelope_id={envelope.envelope_id}: {str(e)}")
        envelope = _append_fallback(envelope, reason=f"LLM failure: {str(e)}")
        
    return envelope

def _apply_match_result(envelope: ExecutionEnvelope, result: MatchResult, success: bool, error_reason: str = "") -> ExecutionEnvelope:
    envelope.matching_results = result
    
    if not envelope.decision:
        is_valid = envelope.validation_results is not None and envelope.validation_results.is_valid
        envelope.decision = Decision(route="auto_approve" if is_valid else "hitl_review")

    if not success or result.match_confidence < 0.70:
        envelope.decision.route = "hitl_review"
        logger.info(f"Overridden decision route to hitl_review for envelope_id={envelope.envelope_id}")
             
    # Audit log
    timestamp_str = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    details = result.model_dump()
    if not success:
        details["error"] = error_reason
        
    audit_entry = AuditEntry(
        timestamp=timestamp_str,
        service="matching_service",
        action="match_commodity",
        envelope_id=envelope.envelope_id,
        result="success" if success else "failure",
        details=details
    )
    envelope.audit.append(audit_entry)
    
    return envelope

def _append_fallback(envelope: ExecutionEnvelope, reason: str) -> ExecutionEnvelope:
    fallback_result = MatchResult(
        matched_code="",
        match_confidence=0.0,
        rationale=reason,
        fallback_used=False,
        source="no_match"
    )
    return _apply_match_result(envelope, fallback_result, success=False, error_reason=reason)

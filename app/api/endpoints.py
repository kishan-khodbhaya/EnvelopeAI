import logging
from fastapi import APIRouter
from app.models.envelope import ExecutionEnvelope
from app.services.validator import validate_envelope
from app.services.matcher import match_commodity

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok", "service_name": "EnvelopeAI", "version": "1.0.0"}

@router.post("/validate", response_model=ExecutionEnvelope)
async def validate_endpoint(envelope: ExecutionEnvelope):
    logger.info(f"Received /validate request for envelope_id={envelope.envelope_id}")
    enriched_envelope = validate_envelope(envelope)
    return enriched_envelope

@router.post("/match", response_model=ExecutionEnvelope)
async def match_endpoint(envelope: ExecutionEnvelope):
    logger.info(f"Received /match request for envelope_id={envelope.envelope_id}")
    enriched_envelope = await match_commodity(envelope)
    return enriched_envelope

@router.post("/process", response_model=ExecutionEnvelope)
async def process_endpoint(envelope: ExecutionEnvelope):
    logger.info(f"Received /process request for envelope_id={envelope.envelope_id}")
    
    # 1. Validate
    envelope = validate_envelope(envelope)
    
    # 2. Match
    threshold = envelope.processing_instructions.confidence_threshold
    comm_code_conf = None
    if envelope.extraction.commodity_code and envelope.extraction.commodity_code.confidence is not None:
        comm_code_conf = envelope.extraction.commodity_code.confidence
        
    needs_matching = False
    if comm_code_conf is not None and comm_code_conf < threshold:
         needs_matching = True
    elif not envelope.extraction.commodity_code or envelope.extraction.commodity_code.value is None:
         # Fallback to matching if commodity code missing altogether
         needs_matching = True
         
    if needs_matching:
        logger.info(f"Commodity code logic triggered matching pipeline for envelope_id={envelope.envelope_id}")
        envelope = await match_commodity(envelope)
        
    return envelope

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

class Tenant(BaseModel):
    id: str
    name: str

class Document(BaseModel):
    type: str
    filename: str
    page_count: int

class ExtractionField(BaseModel):
    value: Optional[Any] = None
    confidence: Optional[float] = None

class Extraction(BaseModel):
    shipment_id: Optional[ExtractionField] = None
    ship_date: Optional[ExtractionField] = None
    recipient_name: Optional[ExtractionField] = None
    commodity_code: Optional[ExtractionField] = None
    commodity_desc: Optional[ExtractionField] = None

class ProcessingInstructions(BaseModel):
    workflow: str
    confidence_threshold: float
    hitl_on_failure: bool

class ValidationResults(BaseModel):
    is_valid: bool
    failed_fields: List[str] = []

class MatchResult(BaseModel):
    matched_code: str
    match_confidence: float
    rationale: str
    fallback_used: bool
    source: Literal["catalog_exact", "llm_match", "no_match"]

class Decision(BaseModel):
    route: Literal["auto_approve", "hitl_review", "rejected", "pending"]

class AuditEntry(BaseModel):
    timestamp: str 
    service: str
    action: str
    envelope_id: str
    result: Literal["success", "failure"]
    details: Dict[str, Any]

class ExecutionEnvelope(BaseModel):
    model_config = ConfigDict(extra='allow')
    
    envelope_id: str
    schema_version: str
    tenant: Tenant
    document: Document
    extraction: Extraction
    processing_instructions: ProcessingInstructions
    validation_results: Optional[ValidationResults] = None
    matching_results: Optional[MatchResult] = None
    decision: Optional[Decision] = None
    audit: List[AuditEntry] = []

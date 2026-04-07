import logging
from datetime import datetime, timezone
from typing import Dict

from app.models.envelope import (
    ExecutionEnvelope,
    ValidationResults,
    Decision,
    AuditEntry
)

logger = logging.getLogger(__name__)

def validate_envelope(envelope: ExecutionEnvelope) -> ExecutionEnvelope:
    logger.info(f"Starting validation for envelope_id={envelope.envelope_id}")
    
    failed_reasons: Dict[str, str] = {}
    threshold = envelope.processing_instructions.confidence_threshold
    
    # 1. Schema/Required Fields check
    extraction = envelope.extraction
    if not extraction.shipment_id or extraction.shipment_id.value is None:
        failed_reasons["shipment_id"] = "Missing or null"
    if not extraction.recipient_name or extraction.recipient_name.value is None:
        failed_reasons["recipient_name"] = "Missing or null"
        
    has_comm_code = extraction.commodity_code and extraction.commodity_code.value is not None
    has_comm_desc = extraction.commodity_desc and extraction.commodity_desc.value is not None
    
    if not (has_comm_code or has_comm_desc):
        failed_reasons["commodity_code"] = "At least one of commodity_code or commodity_desc must be present"

    # 2. Confidence Evaluation
    fields_to_check = {
        "shipment_id": extraction.shipment_id,
        "ship_date": extraction.ship_date,
        "recipient_name": extraction.recipient_name,
        "commodity_code": extraction.commodity_code,
        "commodity_desc": extraction.commodity_desc
    }
    
    for field_name, field_obj in fields_to_check.items():
        if field_obj and field_obj.confidence is not None:
            if field_obj.confidence < threshold:
                failed_reasons[field_name] = f"Confidence {field_obj.confidence} below threshold {threshold}"

    # 3. Date Validation: ship_date not future, not > 365 days old
    if extraction.ship_date and extraction.ship_date.value:
        try:
            s_date = datetime.strptime(str(extraction.ship_date.value), "%Y-%m-%d")
            now = datetime.now()
            delta_days = (now - s_date).days
            
            if delta_days < 0:
                failed_reasons["ship_date"] = "ship_date is in the future"
            elif delta_days > 365:
                failed_reasons["ship_date"] = "ship_date is older than 365 days"
        except ValueError:
             failed_reasons["ship_date"] = "Invalid date format, expected YYYY-MM-DD"
            
    is_valid = len(failed_reasons) == 0
    
    # Validation Results
    envelope.validation_results = ValidationResults(
        is_valid=is_valid,
        failed_fields=list(failed_reasons.keys())
    )
    
    # Decision Routing
    if is_valid:
        route = "auto_approve"
    else:
        route = "hitl_review" if envelope.processing_instructions.hitl_on_failure else "rejected"
        
    envelope.decision = Decision(route=route)
    
    # Audit Trail
    timestamp_str = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    result_status = "success" if is_valid else "failure"
    
    audit_entry = AuditEntry(
        timestamp=timestamp_str,
        service="validation_service",
        action="validate",
        envelope_id=envelope.envelope_id,
        result=result_status,
        details={"failed_reasons": failed_reasons} if not is_valid else {}
    )
    
    envelope.audit.append(audit_entry)
    
    logger.info(f"Validation complete for envelope_id={envelope.envelope_id}. Valid: {is_valid}, Route: {route}")
    
    return envelope

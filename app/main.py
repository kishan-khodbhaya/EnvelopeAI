import logging
import sys
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.api.endpoints import router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Document Intelligence API")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    failed_fields = []
    
    for err in errors:
        loc = ".".join([str(l) for l in err.get("loc", [])])
        msg = err.get("msg", "")
        failed_fields.append({"field": loc, "error": msg})
        
    # Grab envelope_id if available gracefully
    envelope_id = "unknown"
    try:
        body = await request.json()
        if isinstance(body, dict) and "envelope_id" in body:
            envelope_id = body.get("envelope_id")
    except:
        pass
        
    logger.error(f"[envelope_id={envelope_id}] Unprocessable Entity 422: {failed_fields}")
    
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid Execution Envelope schema format", "failed_fields": failed_fields}
    )

@app.get("/")
async def root():
    return {"message": "EnvelopeAI service is running"}

app.include_router(router)

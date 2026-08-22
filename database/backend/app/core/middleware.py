import uuid
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

logger = logging.getLogger("dependencyhub.request")

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
            
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        req_id = getattr(request.state, "request_id", "unknown")
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            process_time = time.perf_counter() - start_time
            logger.error(
                f"req_id={req_id} method={request.method} path={request.url.path} "
                f"status=500 duration={process_time:.4f}s error={exc.__class__.__name__}"
            )
            raise
        
        process_time = time.perf_counter() - start_time
        logger.info(
            f"req_id={req_id} method={request.method} path={request.url.path} "
            f"status={status_code} duration={process_time:.4f}s"
        )
        return response

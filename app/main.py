"""FastAPI application with endpoints, logging, and metrics."""

import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.logger import setup_logging

# Initialize configuration and logger
settings = get_settings()
logger = setup_logging(settings.log_level)

# Application state
request_count: int = 0
data_store: list[dict[str, Any]] = []
start_time: float = time.time()


class DataRequest(BaseModel):
    """Request model for POST /data."""
    
    message: str | None = Field(None, description="Optional message")
    data: dict[str, Any] | None = Field(None, description="Optional data dictionary")


class DataResponse(BaseModel):
    """Response model for POST /data."""
    
    status: str = Field("accepted", description="Status of the request")
    id: int = Field(description="Unique ID for this data entry")
    timestamp: str = Field(description="ISO 8601 timestamp")


class StatusResponse(BaseModel):
    """Response model for GET /status."""
    
    status: str = Field("operational", description="Service status")
    environment: str = Field(description="Environment name")
    version: str = Field(description="API version")
    timestamp: str = Field(description="ISO 8601 timestamp")
    request_count: int = Field(description="Total requests processed")
    uptime_seconds: float = Field(description="Seconds since service started")


class HealthResponse(BaseModel):
    """Response model for health checks."""
    
    status: str = Field("healthy", description="Service health status")


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore
    """Application lifespan context manager."""
    logger.info("application_started", extra={
        "environment": settings.environment,
        "version": settings.version,
        "port": settings.port,
    })
    yield
    logger.info("application_shutdown", extra={
        "total_requests": request_count,
        "stored_data_count": len(data_store),
    })


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Production-grade API with containerization and orchestration",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):  # type: ignore
    """Middleware to log all requests and responses."""
    global request_count
    request_count += 1
    
    logger.info("request_received", extra={
        "request_id": request_count,
        "method": request.method,
        "path": request.url.path,
        "client": request.client.host if request.client else "unknown",
    })
    
    response = await call_next(request)
    
    logger.info("request_completed", extra={
        "request_id": request_count,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
    })
    
    return response


@app.get(
    "/health",
    response_model=HealthResponse,
    responses={200: {"description": "Service is healthy"}},
    tags=["Health"],
)
async def health_check() -> HealthResponse:
    """Health check endpoint for load balancers and Kubernetes probes."""
    return HealthResponse(status="healthy")


@app.get(
    "/ready",
    response_model=HealthResponse,
    responses={200: {"description": "Service is ready"}},
    tags=["Health"],
)
async def readiness_check() -> HealthResponse:
    """Readiness check endpoint for Kubernetes."""
    return HealthResponse(status="ready")


@app.get(
    "/status",
    response_model=StatusResponse,
    responses={200: {"description": "Service status"}},
    tags=["API"],
)
async def get_status() -> StatusResponse:
    """Get service status including uptime and request count.
    
    Returns:
        StatusResponse with current service metrics
    """
    uptime = time.time() - start_time
    
    return StatusResponse(
        status="operational",
        environment=settings.environment,
        version=settings.version,
        timestamp=datetime.now(UTC).isoformat(),
        request_count=request_count,
        uptime_seconds=round(uptime, 2),
    )


@app.post(
    "/data",
    response_model=DataResponse,
    status_code=202,
    responses={202: {"description": "Data accepted for processing"}},
    tags=["API"],
)
async def receive_data(payload: DataRequest) -> DataResponse:
    """Accept and store data.
    
    Args:
        payload: Request containing optional message and data
        
    Returns:
        DataResponse with confirmation and unique ID
        
    Raises:
        Returns 202 Accepted status
    """
    data_id = len(data_store) + 1
    timestamp = datetime.now(UTC).isoformat()
    
    entry: dict[str, Any] = {
        "id": data_id,
        "timestamp": timestamp,
        "data": payload.model_dump(),
    }
    data_store.append(entry)
    
    logger.info("data_received", extra={
        "data_id": data_id,
        "total_stored": len(data_store),
    })
    
    return DataResponse(
        status="accepted",
        id=data_id,
        timestamp=timestamp,
    )


@app.get(
    "/metrics",
    responses={200: {"description": "Prometheus-compatible metrics"}},
    tags=["Monitoring"],
)
async def metrics(request: Request) -> Response:
    """Prometheus-compatible metrics endpoint.
    
    Supports both Prometheus text format and JSON:
    - Accept: application/vnd.google.protobuf → Prometheus text format
    - Accept: application/json (or default) → JSON format
    
    Returns:
        Prometheus metrics or JSON metrics based on Accept header
    """
    uptime = time.time() - start_time
    
    # Check if Prometheus is requesting (typically sends specific Accept header)
    accept_header = request.headers.get("accept", "application/json").lower()
    is_prometheus = "prometheus" in accept_header or "text/plain" in accept_header
    
    if is_prometheus:
        # Return Prometheus text format
        metrics_text = (
            f"# HELP qtec_api_requests_total Total requests processed\n"
            f"# TYPE qtec_api_requests_total counter\n"
            f"qtec_api_requests_total{{environment=\"{settings.environment}\"}} {request_count}\n"
            f"\n"
            f"# HELP qtec_api_stored_data_count Number of stored data entries\n"
            f"# TYPE qtec_api_stored_data_count gauge\n"
            f"qtec_api_stored_data_count{{environment=\"{settings.environment}\"}} {len(data_store)}\n"
            f"\n"
            f"# HELP qtec_api_uptime_seconds Service uptime in seconds\n"
            f"# TYPE qtec_api_uptime_seconds gauge\n"
            f"qtec_api_uptime_seconds{{environment=\"{settings.environment}\"}} {uptime:.2f}\n"
        )
        return Response(content=metrics_text, media_type="text/plain; charset=utf-8")
    else:
        # Return JSON format (default)
        metrics_data = {
            "request_count": request_count,
            "stored_data_count": len(data_store),
            "uptime_seconds": round(uptime, 2),
            "environment": settings.environment,
            "version": settings.version,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        return JSONResponse(metrics_data)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error("unhandled_exception", extra={
        "path": request.url.path,
        "method": request.method,
        "error": str(exc),
        "exception_type": type(exc).__name__,
    })
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

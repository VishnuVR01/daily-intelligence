from fastapi import APIRouter
from starlette.exceptions import HTTPException as StarletteHTTPException

router = APIRouter(prefix="/dev/error", tags=["dev-testing"])


@router.get("/400")
def trigger_400():
    """Trigger a 400 Bad Request error for testing."""
    raise StarletteHTTPException(status_code=400, detail="Development test 400 Bad Request")


@router.get("/403")
def trigger_403():
    """Trigger a 403 Forbidden error for testing."""
    raise StarletteHTTPException(status_code=403, detail="Development test 403 Forbidden")


@router.get("/429")
def trigger_429():
    """Trigger a 429 Rate Limit Exceeded error for testing."""
    raise StarletteHTTPException(status_code=429, detail="Development test 429 Rate Limit Exceeded")


@router.get("/500")
def trigger_500():
    """Trigger an unhandled internal 500 error for testing."""
    raise RuntimeError("Development test 500 Internal Server Error simulation")


@router.get("/502")
def trigger_502():
    """Trigger a 502 Bad Gateway error for testing."""
    raise StarletteHTTPException(status_code=502, detail="Development test 502 Bad Gateway")


@router.get("/503")
def trigger_503():
    """Trigger a 503 Service Unavailable error for testing."""
    raise StarletteHTTPException(status_code=503, detail="Development test 503 Service Unavailable")

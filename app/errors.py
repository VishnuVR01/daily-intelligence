import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")

SUPPORTED_ERROR_TEMPLATES = {400, 403, 404, 429, 500, 502, 503}


def is_api_request(request: Request) -> bool:
    """Determine if a request expects a JSON API response."""
    path = request.url.path
    if path.startswith("/api/"):
        return True
    accept = request.headers.get("accept", "").lower()
    if "application/json" in accept and "text/html" not in accept:
        return True
    return False


def register_error_handlers(app: FastAPI, templates: Jinja2Templates) -> None:
    """Register custom HTTP and unhandled exception handlers for FastAPI."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        status_code = exc.status_code

        if is_api_request(request):
            return JSONResponse(
                status_code=status_code,
                content={"detail": exc.detail, "status_code": status_code},
            )

        template_name = f"{status_code}.html" if status_code in SUPPORTED_ERROR_TEMPLATES else "error.html"
        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context={
                "status_code": status_code,
                "error_detail": exc.detail,
            },
            status_code=status_code,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Server-side technical logging with full traceback
        logger.exception("Unhandled server error processing request %s %s: %s", request.method, request.url.path, exc)

        if is_api_request(request):
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error", "status_code": 500},
            )

        return templates.TemplateResponse(
            request=request,
            name="500.html",
            context={
                "status_code": 500,
            },
            status_code=500,
        )

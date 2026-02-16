from fastapi import FastAPI, status
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from backend.exceptions import NotFoundError


def register_exception_handlers(app: FastAPI) -> None:
    """Wire domain exceptions to HTTP responses."""

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

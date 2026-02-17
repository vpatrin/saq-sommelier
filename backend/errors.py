from fastapi import FastAPI, status
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from loguru import logger

from backend.exceptions import ConflictError, NotFoundError


def register_exception_handlers(app: FastAPI) -> None:
    """Wire domain exceptions to HTTP responses."""

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        logger.warning("{} {} — {}", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        logger.warning("{} {} — {}", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

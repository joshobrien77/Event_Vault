from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "HTTP_ERROR", "message": str(exc.detail)}},
    )


# Common application errors
class NotFoundError(AppError):
    def __init__(self, resource: str):
        super().__init__(404, f"{resource.upper()}_NOT_FOUND", f"{resource} not found")


class ForbiddenError(AppError):
    def __init__(self):
        super().__init__(403, "FORBIDDEN", "You do not have access to this resource")


class ConflictError(AppError):
    def __init__(self, code: str, message: str):
        super().__init__(409, code, message)


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(422, "VALIDATION_ERROR", message)

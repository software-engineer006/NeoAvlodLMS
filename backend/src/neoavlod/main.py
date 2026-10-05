"""ASGI application factory: uvicorn neoavlod.main:create_app --factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from neoavlod import __version__
from neoavlod.api.admin_attendance import router as admin_attendance_router
from neoavlod.api.admin_groups import router as admin_groups_router
from neoavlod.api.admin_settings import router as admin_settings_router
from neoavlod.api.admin_staff import router as admin_staff_router
from neoavlod.api.admin_students import router as admin_students_router
from neoavlod.api.admin_subjects import router as admin_subjects_router
from neoavlod.api.auth import router as auth_router
from neoavlod.api.health import router as health_router
from neoavlod.api.teacher import router as teacher_router
from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else Settings()
    development = config.environment != "production"
    database = Database(config)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await database.close()

    app = FastAPI(
        lifespan=lifespan,
        title=config.app_name,
        version=__version__,
        debug=config.debug,
        docs_url="/api/v1/docs" if development else None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json" if development else None,
    )
    app.state.settings = config
    app.state.database = database

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, error: DomainError) -> JSONResponse:
        return JSONResponse({"detail": error.message}, status_code=error.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]
        return JSONResponse({"detail": details}, status_code=422)

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router)
    app.include_router(admin_staff_router)
    app.include_router(admin_subjects_router)
    app.include_router(admin_groups_router)
    app.include_router(admin_students_router)
    app.include_router(admin_attendance_router)
    app.include_router(admin_settings_router)
    app.include_router(teacher_router)
    return app

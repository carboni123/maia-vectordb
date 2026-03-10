"""Pydantic schemas for health check endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    status: Literal["ok", "error"] = Field(
        description="Component status: 'ok' or 'error'"
    )
    detail: str | None = Field(
        default=None, description="Additional detail if unhealthy"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"status": "ok", "detail": None},
                {"status": "error", "detail": "Connection refused"},
            ]
        }
    )


class HealthResponse(BaseModel):
    """Response body for the health check endpoint."""

    status: Literal["ok", "degraded"] = Field(
        description="Overall service status: 'ok' or 'degraded'"
    )
    version: str = Field(description="API version string")
    database: ComponentHealth = Field(description="Database connectivity status")
    openai_api_key_set: bool = Field(
        description="Whether the OpenAI API key is configured"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "ok",
                    "version": "0.1.0",
                    "database": {"status": "ok", "detail": None},
                    "openai_api_key_set": True,
                },
                {
                    "status": "degraded",
                    "version": "0.1.0",
                    "database": {
                        "status": "error",
                        "detail": "Connection refused",
                    },
                    "openai_api_key_set": False,
                },
            ]
        }
    )

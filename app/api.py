import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from azure.core.exceptions import AzureError
from azure.cosmos.aio import CosmosClient
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.agent import review_wave
from app.cosmos_repository import CosmosRepository, WaveNotFoundError
from app.fleet_rules import SourceDataError
from app.schemas import ReviewRequest, ReviewResponse
from app.settings import Settings

logger = logging.getLogger(__name__)


def error(status: int, code: str, message: str, retryable: bool = False) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "retryable": retryable}},
    )


def create_app(settings: Settings | None = None, client: CosmosClient | None = None) -> FastAPI:
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if client is not None:
            application.state.cosmos = client
            yield
        else:
            async with CosmosClient(config.endpoint, credential=config.key) as owned_client:
                application.state.cosmos = owned_client
                yield

    application = FastAPI(
        title="FleetCharge: emulator-backed CI teaching sample", lifespan=lifespan
    )
    if client is not None:
        application.state.cosmos = client

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info("Invalid review request: %s", type(exc).__name__)
        return error(422, "invalidRequest", "Supply only valid depotId and deliveryWaveId strings.")

    @application.post("/agent/review-delivery-wave", response_model=ReviewResponse)
    async def review(request: ReviewRequest) -> ReviewResponse | JSONResponse:
        repository = CosmosRepository(application.state.cosmos, config)
        try:
            result, _ = await review_wave(repository, request, config)
            return result
        except WaveNotFoundError:
            return error(404, "waveNotFound", "Requested delivery wave was not found.")
        except SourceDataError:
            return error(
                409, "sourceDataInvalid", "Required source data is invalid or unavailable."
            )
        except TimeoutError:
            return error(
                504,
                "reviewTimedOut",
                "Review deadline exceeded. A started audit write may have completed.",
                True,
            )
        except AzureError:
            return error(
                503,
                "dataStoreUnavailable",
                "Emulator operation failed. A started audit write may have completed.",
                True,
            )
        except Exception:
            logger.exception("Agent execution failed")
            return error(
                500,
                "agentExecutionFailed",
                "Agent review failed. Any acknowledged audit remains stored.",
            )

    return application


app = create_app()

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from azure.core.exceptions import AzureError
from azure.cosmos.aio import CosmosClient
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from openai import OpenAIError

from app.agent import review_wave
from app.cosmos_repository import CosmosRepository, WaveNotFoundError
from app.dispatch import ask_dispatch, ingest_dispatch
from app.fleet_rules import SourceDataError
from app.schemas import (
    DispatchAnswer,
    DispatchFeed,
    DispatchQuestion,
    DispatchUpdate,
    ReviewRequest,
    ReviewResponse,
    VehicleAnswer,
    VehicleQuestion,
)
from app.settings import Settings
from app.vehicle_questions import ask_vehicles

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
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info("Invalid review request: %s", type(exc).__name__)
        if request.url.path == "/agent/ask-vehicles":
            return error(422, "invalidRequest", "Supply valid depotId and question strings.")
        if request.url.path == "/agent/ask-dispatch":
            return error(422, "invalidRequest", "Supply valid depotId and question strings.")
        if request.url.path == "/feeds/dispatch-updates":
            return error(422, "invalidRequest", "Supply valid depotId, updateId and pickupBay.")
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
        except OpenAIError:
            logger.exception("Local model inference failed")
            return error(503, "modelUnavailable", "Local Ollama inference failed.", True)
        except Exception:
            logger.exception("Agent execution failed")
            return error(
                500,
                "agentExecutionFailed",
                "Agent review failed. Any acknowledged audit remains stored.",
            )

    @application.post("/agent/ask-vehicles", response_model=VehicleAnswer)
    async def vehicle_question(request: VehicleQuestion) -> VehicleAnswer | JSONResponse:
        repository = CosmosRepository(application.state.cosmos, config)
        try:
            return await ask_vehicles(repository, request, config)
        except SourceDataError:
            logger.exception("Invalid vehicle source data")
            return error(409, "sourceDataInvalid", "Vehicle source data is invalid.")
        except TimeoutError:
            logger.exception("Vehicle question timed out")
            return error(504, "questionTimedOut", "Vehicle question deadline exceeded.", True)
        except AzureError:
            logger.exception("Vehicle query failed")
            return error(503, "dataStoreUnavailable", "Emulator query failed.", True)
        except OpenAIError:
            logger.exception("Local model inference failed")
            return error(503, "modelUnavailable", "Local Ollama inference failed.", True)
        except Exception:
            logger.exception("Vehicle question failed")
            return error(500, "agentExecutionFailed", "Vehicle question failed validation.")

    @application.post("/feeds/dispatch-updates", response_model=DispatchUpdate)
    async def dispatch_feed(request: DispatchFeed) -> DispatchUpdate | JSONResponse:
        repository = CosmosRepository(application.state.cosmos, config)
        try:
            async with asyncio.timeout(config.timeout_seconds):
                return await ingest_dispatch(repository, request)
        except SourceDataError:
            logger.exception("Invalid dispatch acknowledgement")
            return error(409, "sourceDataInvalid", "Dispatch acknowledgement is invalid.")
        except TimeoutError:
            logger.exception("Dispatch feed timed out")
            return error(504, "feedTimedOut", "Write deadline exceeded; verify stored state.", True)
        except AzureError:
            logger.exception("Dispatch feed write failed")
            return error(
                503, "dataStoreUnavailable", "Dispatch write failed; verify stored state.", True
            )

    @application.post("/agent/ask-dispatch", response_model=DispatchAnswer)
    async def dispatch_question(request: DispatchQuestion) -> DispatchAnswer | JSONResponse:
        repository = CosmosRepository(application.state.cosmos, config)
        try:
            return await ask_dispatch(repository, request, config)
        except SourceDataError:
            logger.exception("Invalid dispatch source data")
            return error(409, "sourceDataInvalid", "Dispatch update is missing or invalid.")
        except TimeoutError:
            logger.exception("Dispatch question timed out")
            return error(504, "questionTimedOut", "Dispatch question deadline exceeded.", True)
        except AzureError:
            logger.exception("Dispatch read failed")
            return error(503, "dataStoreUnavailable", "Dispatch read failed.", True)
        except OpenAIError:
            logger.exception("Local model inference failed")
            return error(503, "modelUnavailable", "Local Ollama inference failed.", True)
        except Exception:
            logger.exception("Dispatch question failed")
            return error(500, "agentExecutionFailed", "Dispatch answer failed validation.")

    return application


app = create_app()

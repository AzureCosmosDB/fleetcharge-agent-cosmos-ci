from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from agent_framework import BaseChatClient

from app.schemas import ReviewRequest
from app.scripted_model_client import ScriptedModelClient
from app.settings import Settings


@asynccontextmanager
async def model_client(
    settings: Settings, request: ReviewRequest, supplied: BaseChatClient | None = None
) -> AsyncIterator[BaseChatClient]:
    if supplied is not None:
        yield supplied
    elif settings.mode == "scripted":
        yield ScriptedModelClient(request.depot_id, request.delivery_wave_id, settings.review_at)
    else:
        from agent_framework.openai import OpenAIChatCompletionClient
        from openai import AsyncOpenAI

        async with AsyncOpenAI(
            base_url=settings.ollama_endpoint,
            api_key="ollama-local",
            max_retries=0,
            timeout=settings.timeout_seconds,
        ) as transport:
            yield OpenAIChatCompletionClient(
                model=settings.ollama_model,
                async_client=transport,
                instruction_role="system",
                function_invocation_configuration={
                    "max_iterations": 20,
                    "max_function_calls": 7,
                    "allow_concurrent_invocation": False,
                    "terminate_on_unknown_calls": True,
                },
            )

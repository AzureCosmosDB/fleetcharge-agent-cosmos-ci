import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from agent_framework import (
    BaseChatClient,
    ChatContext,
    ChatMiddleware,
    ChatResponse,
    Content,
    FunctionTool,
    Message,
)

from app.schemas import Decision, ReviewRequest, ReviewResponse
from app.settings import Settings


class OllamaStructuredTools(ChatMiddleware):
    def __init__(self, request: ReviewRequest) -> None:
        self.request = request

    async def process(self, context: ChatContext, call_next: Callable[[], Awaitable[None]]) -> None:
        if context.stream:
            raise ValueError("The local Ollama sample supports non-streaming reviews only")
        options = dict(context.options or {})
        context.options = options
        available = options.get("tools", [])
        function: FunctionTool | None = None
        if available:
            function = available[0]
            if not isinstance(function, FunctionTool) or function.input_model is None:
                raise ValueError("Ollama requires a typed function tool")
            arguments_schema = function.input_model.model_json_schema()
            for key, value in (
                ("depotId", self.request.depot_id),
                ("deliveryWaveId", self.request.delivery_wave_id),
            ):
                if key in arguments_schema["properties"]:
                    arguments_schema["properties"][key]["enum"] = [value]
            definitions = arguments_schema.pop("$defs", {})
            if function.name == "write_charging_recommendation":
                decision_schema = Decision.model_json_schema()
                definitions.update(decision_schema.pop("$defs", {}))
                arguments_schema["properties"]["decision"] = decision_schema
            schema = {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "enum": [function.name]},
                    "arguments": arguments_schema,
                },
                "required": ["name", "arguments"],
                "additionalProperties": False,
                "$defs": definitions,
            }
            instruction = (
                f"Return a JSON tool call with name={function.name} and an arguments object "
                f"matching this schema: {json.dumps(arguments_schema, separators=(',', ':'))}. "
                f"{function.description} Derive argument values only from the original "
                "request and previous tool results. Return JSON, not a native tool call."
            )
        else:
            schema = ReviewResponse.model_json_schema()
            instruction = (
                "Return only the complete JSON object from the last tool result unchanged."
            )
        # Ollama does not reliably enforce native tool_choice; constrain model JSON instead.
        options["tools"] = []
        options["tool_choice"] = "none"
        options["response_format"] = schema
        names = {
            content.call_id: content.name
            for message in context.messages
            for content in message.contents
            if content.type == "function_call"
        }
        results = []
        for message in context.messages:
            for content in message.contents:
                if content.type != "function_result":
                    continue
                if content.exception:
                    raise ValueError("Cannot continue after a failed tool invocation")
                try:
                    result = (
                        json.loads(content.result)
                        if isinstance(content.result, str)
                        else content.result
                    )
                except json.JSONDecodeError as exc:
                    raise ValueError("The previous tool did not return valid JSON") from exc
                results.append({"tool": names[content.call_id], "result": result})
        if function is None or function.name == "write_charging_recommendation":
            expected = "find_available_chargers" if function else "write_charging_recommendation"
            if not results or results[-1]["tool"] != expected:
                raise ValueError(f"Expected the actual {expected} result before model inference")
            # These turns copy the computed decision or acknowledged write, not earlier inputs.
            results = results[-1:]
        context.messages = [
            message for message in context.messages if message.role in {"system", "user"}
        ] + [
            Message(
                "user",
                [
                    Content.from_text(
                        f"Tool results: {json.dumps(results, separators=(',', ':'))}\n{instruction}"
                    )
                ],
            )
        ]
        try:
            await call_next()
        finally:
            options["tools"] = available
        if function is not None:
            if not isinstance(context.result, ChatResponse):
                raise ValueError("Ollama did not return a chat response")
            proposal = json.loads(context.result.text)
            if (
                not isinstance(proposal, dict)
                or set(proposal) != {"name", "arguments"}
                or proposal["name"] != function.name
                or function.input_model is None
            ):
                raise ValueError("Ollama returned an invalid structured tool call")
            arguments = function.input_model.model_validate(proposal["arguments"])
            context.result = ChatResponse(
                response_id=context.result.response_id,
                model=context.result.model,
                usage_details=context.result.usage_details,
                messages=Message(
                    "assistant",
                    [
                        Content.from_function_call(
                            f"call-{uuid4().hex}",
                            function.name,
                            arguments=arguments.model_dump(mode="json", by_alias=True),
                        )
                    ],
                ),
            )


@asynccontextmanager
async def model_client(
    settings: Settings, request: ReviewRequest | None = None
) -> AsyncIterator[BaseChatClient]:
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
            middleware=[OllamaStructuredTools(request)] if request is not None else [],
            function_invocation_configuration={
                "max_iterations": 20,
                "max_function_calls": 7,
                "allow_concurrent_invocation": False,
                "terminate_on_unknown_calls": True,
            },
        )

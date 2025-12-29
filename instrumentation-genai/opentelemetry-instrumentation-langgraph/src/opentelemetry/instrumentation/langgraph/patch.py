# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Method wrappers for LangGraph instrumentation."""

from __future__ import annotations

import json
import logging
import traceback
from contextlib import contextmanager
from typing import Any, AsyncIterator, Callable, Generator, Iterator, TypeVar

from opentelemetry.trace import SpanKind, Tracer
from opentelemetry.trace.status import Status, StatusCode

# Custom semantic attributes for LangGraph
LANGGRAPH_GRAPH_NAME = "langgraph.graph.name"
LANGGRAPH_GRAPH_ID = "langgraph.graph.id"
LANGGRAPH_NODE_NAME = "langgraph.node.name"
LANGGRAPH_STEP = "langgraph.step"

# Tool-related semantic attributes
LANGGRAPH_TOOL_NAME = "langgraph.tool.name"
LANGGRAPH_TOOL_CALL_ID = "langgraph.tool.call_id"
LANGGRAPH_TOOL_COUNT = "langgraph.tool.count"
LANGGRAPH_TOOL_INPUT = "langgraph.tool.input"
LANGGRAPH_TOOL_OUTPUT = "langgraph.tool.output"

# Traceloop semantic attributes (for compatibility with LangChain instrumentation)
TRACELOOP_SPAN_KIND = "traceloop.span.kind"
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def _dont_throw(func: F) -> F:
    """Decorator that catches exceptions and logs them instead of raising.

    Args:
        func: The function to wrap.

    Returns:
        The wrapped function.
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.debug(
                "LangGraph instrumentation failed in %s: %s",
                func.__name__,
                traceback.format_exc(),
            )
            return None

    return wrapper  # type: ignore[return-value]


def _get_graph_name(instance: Any) -> str:
    """Extract graph name from Pregel instance.

    Args:
        instance: The Pregel/CompiledGraph instance.

    Returns:
        The graph name or a default.
    """
    # Try to get name from various attributes
    name = getattr(instance, "name", None)
    if name:
        return str(name)

    # Try to get from builder if available
    builder = getattr(instance, "builder", None)
    if builder:
        builder_name = getattr(builder, "name", None)
        if builder_name:
            return str(builder_name)

    # Fall back to class name
    return instance.__class__.__name__


def _get_graph_id(instance: Any) -> str:
    """Extract graph ID from Pregel instance.

    Args:
        instance: The Pregel/CompiledGraph instance.

    Returns:
        The graph ID or empty string.
    """
    graph_id = getattr(instance, "graph_id", None)
    if graph_id:
        return str(graph_id)
    return ""


@contextmanager
def _workflow_span(
    tracer: Tracer, instance: Any, input_data: Any
) -> Generator[Any, None, None]:
    """Context manager for workflow-level span.

    Args:
        tracer: The OpenTelemetry tracer.
        instance: The Pregel instance.
        input_data: The input data to the workflow.

    Yields:
        The created span.
    """
    graph_name = _get_graph_name(instance)
    graph_id = _get_graph_id(instance)

    with tracer.start_as_current_span(
        name=f"langgraph.workflow {graph_name}",
        kind=SpanKind.INTERNAL,
    ) as span:
        span.set_attribute(LANGGRAPH_GRAPH_NAME, graph_name)
        if graph_id:
            span.set_attribute(LANGGRAPH_GRAPH_ID, graph_id)

        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def create_invoke_wrapper(tracer: Tracer) -> Callable[..., Any]:
    """Create wrapper for Pregel.invoke.

    Args:
        tracer: The OpenTelemetry tracer.

    Returns:
        The wrapper function.
    """

    @_dont_throw
    def wrapper(
        wrapped: Callable[..., Any],
        instance: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        input_data = args[0] if args else kwargs.get("input")

        with _workflow_span(tracer, instance, input_data):
            result = wrapped(*args, **kwargs)
            return result

    return wrapper


def create_ainvoke_wrapper(tracer: Tracer) -> Callable[..., Any]:
    """Create wrapper for Pregel.ainvoke.

    Args:
        tracer: The OpenTelemetry tracer.

    Returns:
        The async wrapper function.
    """

    async def wrapper(
        wrapped: Callable[..., Any],
        instance: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        input_data = args[0] if args else kwargs.get("input")
        graph_name = _get_graph_name(instance)
        graph_id = _get_graph_id(instance)

        with tracer.start_as_current_span(
            name=f"langgraph.workflow {graph_name}",
            kind=SpanKind.INTERNAL,
        ) as span:
            span.set_attribute(LANGGRAPH_GRAPH_NAME, graph_name)
            if graph_id:
                span.set_attribute(LANGGRAPH_GRAPH_ID, graph_id)

            try:
                result = await wrapped(*args, **kwargs)
                span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    return wrapper


class _StreamWrapper:
    """Wrapper for streaming responses that maintains span context."""

    def __init__(
        self,
        stream: Iterator[Any],
        span: Any,
        tracer: Tracer,
        graph_name: str,
    ) -> None:
        self._stream = stream
        self._span = span
        self._tracer = tracer
        self._graph_name = graph_name
        self._step = 0

    def __iter__(self) -> "_StreamWrapper":
        return self

    def __next__(self) -> Any:
        try:
            chunk = next(self._stream)
            self._step += 1
            return chunk
        except StopIteration:
            self._span.set_status(Status(StatusCode.OK))
            self._span.end()
            raise
        except Exception as e:
            self._span.set_status(Status(StatusCode.ERROR, str(e)))
            self._span.record_exception(e)
            self._span.end()
            raise


class _AsyncStreamWrapper:
    """Wrapper for async streaming responses that maintains span context."""

    def __init__(
        self,
        stream: Any,
        span: Any,
        tracer: Tracer,
        graph_name: str,
    ) -> None:
        self._stream = stream
        self._span = span
        self._tracer = tracer
        self._graph_name = graph_name
        self._step = 0

    def __aiter__(self) -> "_AsyncStreamWrapper":
        return self

    async def __anext__(self) -> Any:
        try:
            chunk = await self._stream.__anext__()
            self._step += 1
            return chunk
        except StopAsyncIteration:
            self._span.set_status(Status(StatusCode.OK))
            self._span.end()
            raise
        except Exception as e:
            self._span.set_status(Status(StatusCode.ERROR, str(e)))
            self._span.record_exception(e)
            self._span.end()
            raise


def create_stream_wrapper(tracer: Tracer) -> Callable[..., Any]:
    """Create wrapper for Pregel.stream.

    Args:
        tracer: The OpenTelemetry tracer.

    Returns:
        The wrapper function.
    """

    @_dont_throw
    def wrapper(
        wrapped: Callable[..., Any],
        instance: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        graph_name = _get_graph_name(instance)
        graph_id = _get_graph_id(instance)

        span = tracer.start_span(
            name=f"langgraph.workflow.stream {graph_name}",
            kind=SpanKind.INTERNAL,
        )
        span.set_attribute(LANGGRAPH_GRAPH_NAME, graph_name)
        if graph_id:
            span.set_attribute(LANGGRAPH_GRAPH_ID, graph_id)

        try:
            stream = wrapped(*args, **kwargs)
            return _StreamWrapper(stream, span, tracer, graph_name)
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            span.end()
            raise

    return wrapper


def create_astream_wrapper(tracer: Tracer) -> Callable[..., Any]:
    """Create wrapper for Pregel.astream.

    Args:
        tracer: The OpenTelemetry tracer.

    Returns:
        The async wrapper function.
    """

    async def wrapper(
        wrapped: Callable[..., Any],
        instance: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        graph_name = _get_graph_name(instance)
        graph_id = _get_graph_id(instance)

        span = tracer.start_span(
            name=f"langgraph.workflow.stream {graph_name}",
            kind=SpanKind.INTERNAL,
        )
        span.set_attribute(LANGGRAPH_GRAPH_NAME, graph_name)
        if graph_id:
            span.set_attribute(LANGGRAPH_GRAPH_ID, graph_id)

        try:
            stream = await wrapped(*args, **kwargs)
            return _AsyncStreamWrapper(stream, span, tracer, graph_name)
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            span.end()
            raise

    return wrapper


def _safe_json_serialize(obj: Any) -> str:
    """Safely serialize an object to JSON string.

    Args:
        obj: The object to serialize.

    Returns:
        JSON string representation, or str(obj) if serialization fails.
    """
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        return str(obj)


def _get_tool_name(tool_call: Any) -> str:
    """Extract tool name from a tool call.

    Args:
        tool_call: The tool call object (ToolCall or dict).

    Returns:
        The tool name.
    """
    if hasattr(tool_call, "name"):
        return str(tool_call.name)
    if isinstance(tool_call, dict):
        return str(tool_call.get("name", "unknown"))
    return "unknown"


def _get_tool_call_id(tool_call: Any) -> str:
    """Extract tool call ID from a tool call.

    Args:
        tool_call: The tool call object (ToolCall or dict).

    Returns:
        The tool call ID.
    """
    if hasattr(tool_call, "id"):
        return str(tool_call.id) if tool_call.id else ""
    if isinstance(tool_call, dict):
        return str(tool_call.get("id", ""))
    return ""


def _get_tool_args(tool_call: Any) -> Any:
    """Extract tool arguments from a tool call.

    Args:
        tool_call: The tool call object (ToolCall or dict).

    Returns:
        The tool arguments.
    """
    if hasattr(tool_call, "args"):
        return tool_call.args
    if isinstance(tool_call, dict):
        return tool_call.get("args", {})
    return {}


def create_tool_node_wrapper(tracer: Tracer) -> Callable[..., Any]:
    """Create wrapper for ToolNode._func (sync execution).

    This wrapper creates spans for tool node execution and individual
    tool invocations within the node.

    Args:
        tracer: The OpenTelemetry tracer.

    Returns:
        The wrapper function.
    """

    @_dont_throw
    def wrapper(
        wrapped: Callable[..., Any],
        instance: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        # Get input data
        input_data = args[0] if args else kwargs.get("input")

        # Try to get tool calls from input using instance's parse method
        tool_calls = []
        try:
            if hasattr(instance, "_parse_input"):
                parsed = instance._parse_input(input_data)
                if isinstance(parsed, tuple) and len(parsed) >= 1:
                    tool_calls = parsed[0] if parsed[0] else []
        except Exception:
            pass

        # Create parent span for ToolNode execution
        with tracer.start_as_current_span(
            name="langgraph.tool_node",
            kind=SpanKind.INTERNAL,
        ) as node_span:
            node_span.set_attribute(LANGGRAPH_NODE_NAME, "tools")
            node_span.set_attribute(LANGGRAPH_TOOL_COUNT, len(tool_calls))
            node_span.set_attribute(TRACELOOP_SPAN_KIND, "task")

            try:
                # Execute the original function
                result = wrapped(*args, **kwargs)

                # Try to create spans for individual tools after execution
                # Since tools may run in parallel, we create spans post-hoc
                if tool_calls:
                    _record_tool_spans(tracer, tool_calls, result)

                node_span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                node_span.set_status(Status(StatusCode.ERROR, str(e)))
                node_span.record_exception(e)
                raise

    return wrapper


def create_async_tool_node_wrapper(tracer: Tracer) -> Callable[..., Any]:
    """Create wrapper for ToolNode._afunc (async execution).

    This wrapper creates spans for async tool node execution and individual
    tool invocations within the node.

    Args:
        tracer: The OpenTelemetry tracer.

    Returns:
        The async wrapper function.
    """

    async def wrapper(
        wrapped: Callable[..., Any],
        instance: Any,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> Any:
        # Get input data
        input_data = args[0] if args else kwargs.get("input")

        # Try to get tool calls from input using instance's parse method
        tool_calls = []
        try:
            if hasattr(instance, "_parse_input"):
                parsed = instance._parse_input(input_data)
                if isinstance(parsed, tuple) and len(parsed) >= 1:
                    tool_calls = parsed[0] if parsed[0] else []
        except Exception:
            pass

        # Create parent span for ToolNode execution
        with tracer.start_as_current_span(
            name="langgraph.tool_node",
            kind=SpanKind.INTERNAL,
        ) as node_span:
            node_span.set_attribute(LANGGRAPH_NODE_NAME, "tools")
            node_span.set_attribute(LANGGRAPH_TOOL_COUNT, len(tool_calls))
            node_span.set_attribute(TRACELOOP_SPAN_KIND, "task")

            try:
                # Execute the original function
                result = await wrapped(*args, **kwargs)

                # Try to create spans for individual tools after execution
                if tool_calls:
                    _record_tool_spans(tracer, tool_calls, result)

                node_span.set_status(Status(StatusCode.OK))
                return result
            except Exception as e:
                node_span.set_status(Status(StatusCode.ERROR, str(e)))
                node_span.record_exception(e)
                raise

    return wrapper


def _record_tool_spans(
    tracer: Tracer,
    tool_calls: list[Any],
    results: Any,
) -> None:
    """Record individual tool execution spans.

    This function creates spans for each tool that was executed,
    capturing the tool name, call ID, input arguments, and output.

    Args:
        tracer: The OpenTelemetry tracer.
        tool_calls: List of tool calls that were executed.
        results: The results from tool execution (list of ToolMessages or similar).
    """
    # Convert results to list if not already
    result_list = []
    if isinstance(results, dict):
        # Results may be in a dict like {"messages": [...]}
        messages = results.get("messages", [])
        if isinstance(messages, list):
            result_list = messages
    elif isinstance(results, list):
        result_list = results
    else:
        result_list = [results] if results else []

    for i, tool_call in enumerate(tool_calls):
        tool_name = _get_tool_name(tool_call)
        tool_call_id = _get_tool_call_id(tool_call)
        tool_args = _get_tool_args(tool_call)

        # Try to find matching result
        tool_output = None
        for result in result_list:
            if hasattr(result, "tool_call_id"):
                if result.tool_call_id == tool_call_id:
                    tool_output = (
                        result.content
                        if hasattr(result, "content")
                        else str(result)
                    )
                    break
            elif hasattr(result, "id"):
                if result.id == tool_call_id:
                    tool_output = (
                        result.content
                        if hasattr(result, "content")
                        else str(result)
                    )
                    break

        # If no match found by ID, try to match by index
        if tool_output is None and i < len(result_list):
            result = result_list[i]
            tool_output = (
                result.content if hasattr(result, "content") else str(result)
            )

        # Create span for this tool execution
        with tracer.start_as_current_span(
            name=f"{tool_name}.tool",
            kind=SpanKind.INTERNAL,
        ) as tool_span:
            tool_span.set_attribute(LANGGRAPH_TOOL_NAME, tool_name)
            tool_span.set_attribute(TRACELOOP_SPAN_KIND, "tool")
            tool_span.set_attribute(GEN_AI_OPERATION_NAME, "execute_tool")

            if tool_call_id:
                tool_span.set_attribute(LANGGRAPH_TOOL_CALL_ID, tool_call_id)

            # Capture input arguments
            if tool_args:
                tool_span.set_attribute(
                    LANGGRAPH_TOOL_INPUT, _safe_json_serialize(tool_args)
                )

            # Capture output
            if tool_output is not None:
                tool_span.set_attribute(
                    LANGGRAPH_TOOL_OUTPUT, _safe_json_serialize(tool_output)
                )

            tool_span.set_status(Status(StatusCode.OK))

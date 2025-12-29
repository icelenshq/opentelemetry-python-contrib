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

"""
LangGraph instrumentation for OpenTelemetry.

This instrumentation provides automatic tracing of LangGraph workflow executions,
including:
- Graph invocations (invoke/ainvoke)
- Streaming operations (stream/astream)

This is a standalone instrumentation that works independently of LangChain
instrumentation. It directly wraps LangGraph's Pregel execution engine.

Usage
-----
.. code:: python

    from opentelemetry.instrumentation.langgraph import LangGraphInstrumentor
    from langgraph.graph import StateGraph, START, END
    from typing import TypedDict

    LangGraphInstrumentor().instrument()

    class State(TypedDict):
        value: str

    def my_node(state: State) -> dict:
        return {"value": state["value"] + " processed"}

    graph = StateGraph(State)
    graph.add_node("process", my_node)
    graph.add_edge(START, "process")
    graph.add_edge("process", END)

    compiled = graph.compile()
    result = compiled.invoke({"value": "hello"})

    LangGraphInstrumentor().uninstrument()

API
---
"""

from typing import Any, Collection

from wrapt import wrap_function_wrapper  # type: ignore[import-untyped]

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.langgraph.package import _instruments
from opentelemetry.instrumentation.langgraph.patch import (
    create_ainvoke_wrapper,
    create_astream_wrapper,
    create_async_tool_node_wrapper,
    create_invoke_wrapper,
    create_stream_wrapper,
    create_tool_node_wrapper,
)
from opentelemetry.instrumentation.langgraph.version import __version__
from opentelemetry.instrumentation.utils import unwrap
from opentelemetry.semconv.schemas import Schemas
from opentelemetry.trace import get_tracer


class LangGraphInstrumentor(BaseInstrumentor):
    """OpenTelemetry instrumentor for LangGraph.

    This instrumentor wraps LangGraph's Pregel execution engine to capture
    telemetry for workflow executions.

    Features:
        - Automatic span creation for graph invocations
        - Support for sync and async operations
        - Streaming operation support
        - Graph name and ID capture

    Example:
        >>> from opentelemetry.instrumentation.langgraph import LangGraphInstrumentor
        >>> instrumentor = LangGraphInstrumentor()
        >>> instrumentor.instrument()
        >>> # Use LangGraph as normal
        >>> instrumentor.uninstrument()

    Note:
        This instrumentation is independent of LangChain instrumentation.
        If both are enabled, you may see overlapping spans for LangGraph
        operations that also trigger LangChain callbacks.
    """

    def __init__(self) -> None:
        """Initialize the LangGraph instrumentor."""
        super().__init__()

    def instrumentation_dependencies(self) -> Collection[str]:
        """Return the instrumented package dependencies."""
        return _instruments

    def _instrument(self, **kwargs: Any) -> None:
        """Enable LangGraph instrumentation.

        Args:
            **kwargs: Additional configuration options.
                - tracer_provider: Custom TracerProvider
        """
        tracer_provider = kwargs.get("tracer_provider")

        tracer = get_tracer(
            __name__,
            __version__,
            tracer_provider,
            schema_url=Schemas.V1_28_0.value,
        )

        # Wrap Pregel methods
        wrap_function_wrapper(
            module="langgraph.pregel",
            name="Pregel.invoke",
            wrapper=create_invoke_wrapper(tracer),
        )

        wrap_function_wrapper(
            module="langgraph.pregel",
            name="Pregel.ainvoke",
            wrapper=create_ainvoke_wrapper(tracer),
        )

        wrap_function_wrapper(
            module="langgraph.pregel",
            name="Pregel.stream",
            wrapper=create_stream_wrapper(tracer),
        )

        wrap_function_wrapper(
            module="langgraph.pregel",
            name="Pregel.astream",
            wrapper=create_astream_wrapper(tracer),
        )

        # Wrap ToolNode methods for tool call tracing
        wrap_function_wrapper(
            module="langgraph.prebuilt.tool_node",
            name="ToolNode._func",
            wrapper=create_tool_node_wrapper(tracer),
        )

        wrap_function_wrapper(
            module="langgraph.prebuilt.tool_node",
            name="ToolNode._afunc",
            wrapper=create_async_tool_node_wrapper(tracer),
        )

    def _uninstrument(self, **kwargs: Any) -> None:
        """Disable LangGraph instrumentation."""
        import langgraph.pregel  # type: ignore[import-untyped]
        from langgraph.prebuilt import tool_node  # type: ignore[import-untyped]

        unwrap(langgraph.pregel.Pregel, "invoke")
        unwrap(langgraph.pregel.Pregel, "ainvoke")
        unwrap(langgraph.pregel.Pregel, "stream")
        unwrap(langgraph.pregel.Pregel, "astream")

        # Unwrap ToolNode methods
        unwrap(tool_node.ToolNode, "_func")
        unwrap(tool_node.ToolNode, "_afunc")

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

"""Local semantic conventions for LangChain instrumentation.

These are custom attributes used for LangChain-specific telemetry that
extend the standard OpenTelemetry GenAI semantic conventions.
"""

from __future__ import annotations

from enum import Enum


class TraceloopSpanKindValues(str, Enum):
    """Values for the traceloop.span.kind attribute."""

    WORKFLOW = "workflow"
    TASK = "task"
    TOOL = "tool"
    AGENT = "agent"
    UNKNOWN = "unknown"


class LLMRequestTypeValues(str, Enum):
    """Values for the llm.request_type attribute."""

    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    RERANK = "rerank"
    UNKNOWN = "unknown"


# Custom span attributes for LangChain instrumentation
class SpanAttributes:
    """Custom span attributes for LangChain instrumentation."""

    # Traceloop span kind (workflow, task, tool, agent)
    TRACELOOP_SPAN_KIND = "traceloop.span.kind"

    # Entity identification
    TRACELOOP_ENTITY_NAME = "traceloop.entity.name"
    TRACELOOP_ENTITY_PATH = "traceloop.entity.path"
    TRACELOOP_WORKFLOW_NAME = "traceloop.workflow.name"

    # Association properties prefix
    TRACELOOP_ASSOCIATION_PROPERTIES = "traceloop.association.properties"

    # LLM request type
    LLM_REQUEST_TYPE = "llm.request_type"

    # LLM request functions (for tool/function calling)
    LLM_REQUEST_FUNCTIONS = "llm.request.functions"

    # Token usage (legacy attributes)
    LLM_USAGE_TOTAL_TOKENS = "llm.usage.total_tokens"
    LLM_USAGE_CACHE_READ_INPUT_TOKENS = "llm.usage.cache_read_input_tokens"


# Meter names for metrics
class MeterNames:
    """Metric names for LangChain instrumentation."""

    LLM_OPERATION_DURATION = "gen_ai.client.operation.duration"
    LLM_TOKEN_USAGE = "gen_ai.client.token.usage"

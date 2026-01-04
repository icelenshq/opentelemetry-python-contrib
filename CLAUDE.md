# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

OpenTelemetry Python Contrib is a monorepo containing 50+ auto-instrumentation libraries for OpenTelemetry in Python. It includes instrumentations for popular libraries (Flask, Django, requests, boto3, Redis, etc.), GenAI instrumentations (OpenAI, Anthropic, VertexAI), exporters, propagators, and resource detectors.

## Build and Development Commands

### Setup
```bash
pip install tox tox-uv      # Install tox with uv support
uv sync                      # Create .venv with all dependencies (alternative)
pre-commit install           # Install pre-commit hooks (recommended)
```

### Running Tests
```bash
# Run all tests (slow - runs across all packages and Python versions)
tox

# Run tests for a specific instrumentation
tox -e py312-test-instrumentation-requests

# Fast re-run using existing tox environment (skip dependency install)
.tox/py312-test-instrumentation-requests/bin/pytest instrumentation/opentelemetry-instrumentation-requests

# Run benchmarks
tox -f benchmark
```

### Linting and Code Quality
```bash
tox -e ruff                  # Run ruff linter and formatter
tox -e lint-some-package     # Lint a specific package
tox -e precommit             # Run all pre-commit checks
tox -e pyright               # Type checking (strict mode on select packages)
tox -e spellcheck            # Spellcheck
```

### Documentation
```bash
tox -e docs                  # Build documentation
```

### Code Generation
```bash
tox -e generate              # Regenerate bootstrap and other generated files
tox -e generate-workflows    # Regenerate CI workflows after tox.ini changes
python scripts/generate_instrumentation_bootstrap.py  # After adding new instrumentation
```

### Testing Against Different Core Repo Versions
```bash
CORE_REPO_SHA=<commit-hash> tox  # Test against specific commit
```

## Architecture

### Package Structure
- `instrumentation/` - Main instrumentation packages (50+)
- `instrumentation-genai/` - GenAI-specific instrumentations organized by category:
  - `llm-clients/` - LLM provider clients (OpenAI, Anthropic, VertexAI, Bedrock, Cohere, Groq, etc.)
  - `frameworks/` - AI frameworks (LangChain, LangGraph, CrewAI, Haystack, LlamaIndex, etc.)
  - `vector-dbs/` - Vector databases (ChromaDB, Pinecone, Milvus, Qdrant, Weaviate, etc.)
  - `protocols/` - Protocol instrumentations (MCP)
- `opentelemetry-instrumentation/` - Base instrumentation framework with `BaseInstrumentor`
- `exporter/` - Exporters (Prometheus remote-write, RichConsole)
- `propagator/` - Context propagators (AWS X-Ray, OT Trace)
- `resource/` - Resource detectors (Azure, Container ID)
- `util/` - Shared utilities (opentelemetry-util-http, opentelemetry-util-genai)

### Standard Instrumentation Package Layout
```
instrumentation/opentelemetry-instrumentation-{library}/
├── src/opentelemetry/instrumentation/{library}/
│   ├── __init__.py      # Main instrumentor class (extends BaseInstrumentor)
│   ├── version.py       # Version (dynamically read by hatchling)
│   └── package.py       # _instruments dependency definitions
├── tests/
├── pyproject.toml       # Entry points, dependencies, instruments list
└── test-requirements.txt
```

### Key Dependencies
- Packages depend on `opentelemetry-api ~= 1.12` from the core repo
- Core repo packages (api, sdk, semantic-conventions, test-utils) are sourced from `https://github.com/open-telemetry/opentelemetry-python` main branch

### Build Order
Packages must be built in dependency order (defined in `eachdist.ini`):
1. `opentelemetry-instrumentation` (base)
2. `util/opentelemetry-util-http`
3. `instrumentation/opentelemetry-instrumentation-wsgi`
4. `instrumentation/opentelemetry-instrumentation-dbapi`
5. `instrumentation/opentelemetry-instrumentation-asgi`
6. Other instrumentations...

## Code Style

- **Line length**: 79 characters
- **Python version**: 3.9+ minimum
- **Docstrings**: Google style
- **Formatter/Linter**: Ruff (configured in pyproject.toml)
- **Type checking**: Pyright strict mode (progressively enabled)

## Adding New Instrumentation

1. Create package in `instrumentation/opentelemetry-instrumentation-{name}/`
2. Extend from `BaseInstrumentor` class
3. Add entry point in `pyproject.toml`:
   ```toml
   [project.entry-points.opentelemetry_instrumentor]
   library_name = "opentelemetry.instrumentation.library:LibraryInstrumentor"
   ```
4. Run `python scripts/generate_instrumentation_bootstrap.py`
5. Add test environment to `tox.ini`
6. Run `tox -e generate-workflows`
7. Add doc entry in `docs/instrumentation/{name}/{name}.rst`

### Required Instrumentation Features
- Follow semantic conventions (prefer STABLE status)
- Support auto-instrumentation via entry points
- Implement `suppress_instrumentation` functionality
- HTTP instrumentations: `exclude_urls`, `url_filter`, request/response hooks
- Use `is_recording()` optimization on non-sampled spans
- Isolate sync and async tests (use `IsolatedAsyncioTestCase` for async)

## Updating Instrumentation Package Versions

1. Update `pyproject.toml`: modify `instruments` in `[project.optional-dependencies]`
2. Update `package.py`: modify `_instruments` variable
3. Run `tox -e generate` at repo root
4. If adding new version tests: add test-requirements.txt and update tox.ini

## Version Management

- **Stable packages**: version 1.40.0.dev
- **Pre-release packages**: version 0.61b0.dev
- GenAI instrumentations and some AWS/Azure packages have separate release cycles (excluded from main release)

## GenAI Instrumentation Semantic Conventions

GenAI instrumentations in `instrumentation-genai/` MUST follow OpenTelemetry GenAI semantic conventions strictly.

### Required Practices

1. **Use `gen_ai.*` namespace** for all custom attributes:
   - Standard attributes: Use `opentelemetry.semconv._incubating.attributes.gen_ai_attributes`
   - Package-specific attributes: Use `gen_ai.{package_name}.*` (e.g., `gen_ai.langchain.entity.name`, `gen_ai.langgraph.graph.name`)

2. **NEVER use third-party attribute namespaces** like `traceloop.*`, `langsmith.*`, etc.
   - These are vendor-specific and not part of OTel standards
   - If porting from OpenLLMetry or similar, replace all such attributes

3. **Environment variables** must use standard OTel naming:
   - **Capture mode** (preferred): `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MODE` with values `metadata` or `all`
   - **Per-package capture mode**: `OTEL_INSTRUMENTATION_{PACKAGE}_CAPTURE_MODE` (e.g., `OTEL_INSTRUMENTATION_OPENAI_CAPTURE_MODE`)
   - **Legacy content capture**: `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` (default: `false`)
   - NOT: `TRACELOOP_TRACE_CONTENT` or other vendor-specific names

   **Resolution order**: Package-specific → Global → Legacy → Package default

4. **Metric names** must follow `gen_ai.*` pattern:
   - `gen_ai.client.operation.duration`
   - `gen_ai.client.token.usage`
   - `gen_ai.{package}.workflow.duration` for package-specific metrics

5. **Operation names** use `gen_ai.operation.name` attribute with values:
   - Standard: `chat`, `text_completion`, `embeddings`
   - Extended: `workflow`, `task`, `execute_tool`, `agent`, `create_agent`

### Capture Modes

GenAI instrumentations support two capture modes:

| Mode | Description | Tool Attributes |
|------|-------------|-----------------|
| `metadata` | Only metadata (token counts, model, finish reasons). Default for LLM clients. | `gen_ai.request.available_tools` (list of names) |
| `all` | Everything including message content and log events. Default for frameworks. | Full details: `gen_ai.request.tools.{i}.name/description/parameters` |

**Package defaults:**
- LLM clients (openai, anthropic, etc.): `metadata`
- Frameworks (langchain, langgraph, etc.): `all`

### Reference Implementation

See `opentelemetry-instrumentation-openai-v2` in `instrumentation-genai/llm-clients/` for the canonical example of proper semantic convention usage.

## Vector Database Instrumentation Standards

Vector database instrumentations in `instrumentation-genai/` follow specific patterns distinct from LLM instrumentations.

### Implemented Vector Database Packages

| Package | Client Library | Methods Instrumented |
|---------|---------------|---------------------|
| `opentelemetry-instrumentation-chromadb` | `chromadb >= 0.3.0` | add, get, peek, query, modify, update, upsert, delete |
| `opentelemetry-instrumentation-weaviate` | `weaviate-client >= 4.4.0` | collections, queries, batch operations |
| `opentelemetry-instrumentation-lancedb` | `lancedb >= 0.9.0` | add, search, delete |
| `opentelemetry-instrumentation-marqo` | `marqo >= 3.5.1` | add_documents, search, delete_documents |
| `opentelemetry-instrumentation-pinecone` | `pinecone-client >= 2.2.2, <6` | query, upsert, delete (Index + GRPCIndex) |
| `opentelemetry-instrumentation-milvus` | `pymilvus >= 2.4.1` | create_collection, insert, upsert, delete, search, get, query, hybrid_search |
| `opentelemetry-instrumentation-qdrant` | `qdrant-client >= 1.7` | 23+ methods (sync + async clients) |

### Semantic Conventions for Vector DBs

1. **Use `db.{vendor}.*` namespace** for vector database attributes:
   - `db.chromadb.query.n_results`
   - `db.pinecone.query.top_k`
   - `db.milvus.search.collection_name`
   - `db.qdrant.upsert.points_count`

2. **Standard span attributes**:
   - `db.system` = vendor name (e.g., "chromadb", "pinecone", "milvus")
   - `db.operation` = method name

3. **Event naming**:
   - `db.query.result` - Query result events
   - `db.search.result` - Search result events
   - `db.query.embeddings` - Query embedding events

### Vector DB Package Structure

```
instrumentation-genai/vector-dbs/opentelemetry-instrumentation-{name}/
├── src/opentelemetry/instrumentation/{name}/
│   ├── __init__.py      # Main Instrumentor class (extends BaseInstrumentor)
│   ├── version.py       # Version "2.0b0.dev"
│   ├── package.py       # _instruments tuple
│   ├── utils.py         # dont_throw decorator, Config class, utilities
│   ├── wrapper.py       # Sync wrapper functions
│   ├── async_wrapper.py # Async wrapper functions (if applicable)
│   ├── semconv.py       # Local semantic conventions (db.{vendor}.*)
│   └── instruments.py   # Metrics definitions (if applicable)
├── tests/
│   └── __init__.py
├── pyproject.toml       # Hatchling build, entry points
└── README.rst
```

### Key Patterns

1. **Wrapper pattern**: Use `create_wrapper()` function that returns a closure
2. **Suppression**: Check `_SUPPRESS_INSTRUMENTATION_KEY` before tracing
3. **Error isolation**: Use `@dont_throw` decorator on attribute setters
4. **Metrics**: Enable via `OTEL_INSTRUMENTATION_GENAI_METRICS_ENABLED` env var
5. **Schema URL**: Use `Schemas.V1_28_0.value` for tracer creation

### Example Wrapper Implementation

```python
def create_wrapper(tracer: Tracer, method_name: str, span_name: str) -> Callable:
    def wrapper(wrapped, instance, args, kwargs):
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return wrapped(*args, **kwargs)

        with tracer.start_as_current_span(
            span_name,
            kind=SpanKind.CLIENT,
            attributes={
                SpanAttributes.DB_SYSTEM: "vendor_name",
                SpanAttributes.DB_OPERATION: method_name,
            },
        ) as span:
            # Set method-specific attributes
            _set_attributes(span, kwargs)

            result = wrapped(*args, **kwargs)
            return result

    return wrapper
```

### Porting from OpenLLMetry

When porting vector DB instrumentations from OpenLLMetry:

| OpenLLMetry | instrumentation-genai |
|-------------|----------------------|
| Poetry (`pyproject.toml`) | Hatchling |
| `opentelemetry-semantic-conventions-ai` | Local `semconv.py` |
| `TRACELOOP_METRICS_ENABLED` | `OTEL_INSTRUMENTATION_GENAI_METRICS_ENABLED` |
| `SpanAttributes.VECTOR_DB_VENDOR` | `SpanAttributes.DB_SYSTEM` |
| JSON method configs | Python `methods.py` module |
| Traceloop license headers | OpenTelemetry Authors headers |

## AI Agent Framework Instrumentations

The following AI agent framework instrumentations are available in `instrumentation-genai/`:

### Available Frameworks

| Package | Framework | Min Version | Entry Point |
|---------|-----------|-------------|-------------|
| `opentelemetry-instrumentation-crewai` | CrewAI | 0.70.0 | `CrewAIInstrumentor` |
| `opentelemetry-instrumentation-haystack` | Haystack | 2.0.0 | `HaystackInstrumentor` |
| `opentelemetry-instrumentation-agno` | Agno | 1.0.0 | `AgnoInstrumentor` |
| `opentelemetry-instrumentation-llamaindex` | LlamaIndex | 0.10.0 | `LlamaIndexInstrumentor` |
| `opentelemetry-instrumentation-langchain` | LangChain | 0.1.0 | `LangChainInstrumentor` |
| `opentelemetry-instrumentation-langgraph` | LangGraph | 0.2.0 | `LangGraphInstrumentor` |

### Framework-Specific Implementation Details

#### CrewAI
- **Instrumented methods**: `Crew.kickoff`, `Agent.execute_task`, `Task.execute_sync`, `LLM.call`
- **Span hierarchy**: `crewai.workflow` → `{agent_role}.agent` → `{task_desc}.task` → `{model}.llm`
- **Attributes**: `gen_ai.crewai.crew.*`, `gen_ai.crewai.agent.*`, `gen_ai.crewai.task.*`

#### Haystack
- **Instrumented methods**: `Pipeline.run`, `OpenAIGenerator.run`, `OpenAIChatGenerator.run`
- **Span hierarchy**: `haystack_pipeline.workflow` → `haystack.openai.{completion|chat}`
- **Attributes**: `gen_ai.haystack.entity.*`, `gen_ai.haystack.pipeline.*`

#### Agno
- **Instrumented methods**: `Agent.run/arun`, `Team.run/arun`, `FunctionCall.execute/aexecute`
- **Span hierarchy**: `{team_name}.team` → `{agent_name}.agent` → `{tool_name}.tool`
- **Attributes**: `gen_ai.agno.agent.*`, `gen_ai.agno.team.*`, `gen_ai.agno.tool.*`
- **Features**: Full async support, streaming response handling

#### LlamaIndex
- **Architecture**: Uses LlamaIndex's native dispatcher pattern (0.10.20+)
- **Components**: `OpenTelemetrySpanHandler`, `OpenTelemetryEventHandler`
- **Instrumented operations**: Retrievers, synthesizers, embeddings, agents, tools, query pipelines
- **Attributes**: `gen_ai.llamaindex.entity.*`, `gen_ai.llamaindex.retriever.*`, `gen_ai.llamaindex.embedding.*`

### Attribute Conversion Reference (OpenLLMetry → OTel)

When porting from OpenLLMetry, use these conversions:

| OpenLLMetry Attribute | OTel Standard Attribute |
|-----------------------|-------------------------|
| `traceloop.span.kind` | `gen_ai.operation.name` |
| `traceloop.entity.name` | `gen_ai.{framework}.entity.name` |
| `traceloop.entity.input` | `gen_ai.{framework}.entity.input` |
| `traceloop.entity.output` | `gen_ai.{framework}.entity.output` |
| `traceloop.workflow.name` | `gen_ai.{framework}.workflow.name` |
| `TRACELOOP_TRACE_CONTENT` | `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` |

### Standard Package Structure for Agent Frameworks

```
instrumentation-genai/frameworks/opentelemetry-instrumentation-{framework}/
├── src/opentelemetry/instrumentation/{framework}/
│   ├── __init__.py      # Main {Framework}Instrumentor class
│   ├── version.py       # __version__ = "0.1b0"
│   ├── package.py       # _instruments = ("{framework} >= X.X.X",)
│   ├── patch.py         # Wrapper functions using wrapt
│   ├── utils.py         # Helpers (should_capture_content, safe_json_dumps)
│   └── streaming.py     # Stream wrappers (if applicable)
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_{framework}.py
├── pyproject.toml       # Entry points under [project.entry-points.opentelemetry_instrumentor]
└── README.rst
```

### Common Utility Functions

All agent framework instrumentations should implement these utilities in `utils.py`:

```python
def should_capture_content() -> bool:
    """Check if content capture is enabled via OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT."""

def safe_json_dumps(obj: Any) -> Optional[str]:
    """Safely serialize objects to JSON, handling non-serializable types."""

def get_operation_name(method_name: str) -> str:
    """Map method names to gen_ai.operation.name values (workflow, task, agent, execute_tool, embeddings)."""
```

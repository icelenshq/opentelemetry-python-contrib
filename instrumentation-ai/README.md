# OpenTelemetry AI Instrumentation

This directory contains OpenTelemetry instrumentation packages for AI/ML libraries, organized by category.

## Categories

### LLM Providers (`llm-providers/`)
Direct API clients for Large Language Model providers:

| Instrumentation | Supported Packages | Metrics support | Semconv status |
| --------------- | ------------------ | --------------- | -------------- |
| [opentelemetry-instrumentation-anthropic](./llm-providers/opentelemetry-instrumentation-anthropic) | anthropic >= 0.3.0 | No | development |
| [opentelemetry-instrumentation-google-genai](./llm-providers/opentelemetry-instrumentation-google-genai) | google-genai >= 1.0.0 | No | development |
| [opentelemetry-instrumentation-openai-v2](./llm-providers/opentelemetry-instrumentation-openai-v2) | openai >= 1.26.0 | Yes | development |
| [opentelemetry-instrumentation-vertexai](./llm-providers/opentelemetry-instrumentation-vertexai) | google-cloud-aiplatform >= 1.64 | No | development |

### Frameworks (`frameworks/`)
AI orchestration and chain frameworks:

| Instrumentation | Supported Packages | Metrics support | Semconv status |
| --------------- | ------------------ | --------------- | -------------- |
| [opentelemetry-instrumentation-langchain](./frameworks/opentelemetry-instrumentation-langchain) | langchain >= 0.3.21 | No | development |

### Vector Databases (`vectordb/`)
Vector database clients for embeddings and similarity search:

| Instrumentation | Supported Packages | Metrics support | Semconv status |
| --------------- | ------------------ | --------------- | -------------- |
| [opentelemetry-instrumentation-weaviate](./vectordb/opentelemetry-instrumentation-weaviate) | weaviate-client >= 3.0.0,<5.0.0 | No | development |

### Agents (`agents/`)
Agent frameworks and autonomous AI systems:

| Instrumentation | Supported Packages | Metrics support | Semconv status |
| --------------- | ------------------ | --------------- | -------------- |
| [opentelemetry-instrumentation-openai-agents-v2](./agents/opentelemetry-instrumentation-openai-agents-v2) | openai-agents >= 0.3.3 | No | development |

## Installation

Each instrumentation package can be installed individually:

```bash
pip install opentelemetry-instrumentation-openai-v2
pip install opentelemetry-instrumentation-anthropic
pip install opentelemetry-instrumentation-langchain
# etc.
```

## Usage

For zero-code instrumentation:

```bash
opentelemetry-instrument python your_app.py
```

For programmatic instrumentation, see individual package documentation.

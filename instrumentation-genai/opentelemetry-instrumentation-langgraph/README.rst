OpenTelemetry LangGraph Instrumentation
=======================================

|pypi|

.. |pypi| image:: https://badge.fury.io/py/opentelemetry-instrumentation-langgraph.svg
   :target: https://pypi.org/project/opentelemetry-instrumentation-langgraph/

This library allows tracing LangGraph workflow executions with OpenTelemetry.

Installation
------------

::

    pip install opentelemetry-instrumentation-langgraph

Usage
-----

Manual Instrumentation
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from opentelemetry.instrumentation.langgraph import LangGraphInstrumentor
    from langgraph.graph import StateGraph, START, END
    from typing import TypedDict

    # Enable instrumentation
    LangGraphInstrumentor().instrument()

    # Define your graph
    class State(TypedDict):
        value: str

    def process_node(state: State) -> dict:
        return {"value": state["value"] + " processed"}

    graph = StateGraph(State)
    graph.add_node("process", process_node)
    graph.add_edge(START, "process")
    graph.add_edge("process", END)

    # Use your graph
    compiled = graph.compile()
    result = compiled.invoke({"value": "hello"})

    # Disable instrumentation
    LangGraphInstrumentor().uninstrument()

Zero-Code Instrumentation
~~~~~~~~~~~~~~~~~~~~~~~~~

Run your application with the ``opentelemetry-instrument`` command:

::

    opentelemetry-instrument python your_app.py

Features
--------

- Automatic span creation for workflow invocations
- Support for sync (``invoke``) and async (``ainvoke``) operations
- Streaming support (``stream`` and ``astream``)
- Graph name and ID capture in span attributes

Span Attributes
---------------

The instrumentation captures the following span attributes:

- ``langgraph.graph.name``: The name of the graph being executed
- ``langgraph.graph.id``: The graph ID (if available)

References
----------

* `OpenTelemetry LangGraph Instrumentation <https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/langgraph/langgraph.html>`_
* `OpenTelemetry Project <https://opentelemetry.io/>`_
* `LangGraph Documentation <https://langchain-ai.github.io/langgraph/>`_

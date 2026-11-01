"""Lesson 10, step 2: one question, asked twice — without the docs, then with the passage that answers it.

    uv run python experiments/rag_by_hand.py
"""

import ollama


QUESTION = "Which environment variable turns on FastAPI's automatic OpenTelemetry exporter setup?"

# Copied from advanced/opentelemetry.md in FastAPI 0.162.0, section "Other monitoring services".
PASSAGE = """\
To send telemetry to another monitoring service, configure an endpoint that accepts OTLP, the
OpenTelemetry protocol for sending telemetry. Set these environment variables:

export FASTAPI_OTEL_AUTO_CONFIGURE=true
export OTEL_SERVICE_NAME=my-api
export OTEL_EXPORTER_OTLP_ENDPOINT=https://collector.example.com

FASTAPI_OTEL_AUTO_CONFIGURE=true enables FastAPI's automatic exporter setup."""


PROMPTS = {
    "without the docs": QUESTION,
    "with the passage": f"Answer using only this passage from the FastAPI docs.\n\n{PASSAGE}\n\nQuestion: {QUESTION}",
}

for label, prompt in PROMPTS.items():
    response = ollama.chat(
        model='qwen3:8b',
        messages=[
            {"role": "user", "content": prompt}
        ],
        think=False,
        options={"temperature": 0, "num_predict": 400}
    )

    print(f"--- {label} . {response.eval_count}\n")
    print(response.message.content)
    print("****************")
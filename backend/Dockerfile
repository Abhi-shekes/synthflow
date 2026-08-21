FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

# Which optional extras to install (see pyproject.toml and
# app/services/install.py). Empty = core only, which genuinely leaves
# aiokafka/aiomqtt off the image rather than installing them and not
# using them. `synthflow init` writes this into .env; docker-compose.yml
# passes it through as a build arg.
ARG SYNTHFLOW_EXTRAS=""

COPY pyproject.toml ./
RUN if [ -n "$SYNTHFLOW_EXTRAS" ]; then \
        uv pip install --system --no-cache -e ".[$SYNTHFLOW_EXTRAS]"; \
    else \
        uv pip install --system --no-cache -e .; \
    fi

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

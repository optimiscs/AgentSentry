FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends python3 libseccomp2 git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY src ./src
COPY policies ./policies
COPY docs/evidence ./docs/evidence
RUN pip install --no-cache-dir --no-deps .
ENV AGENTSENTRY_ROOT=/app AGENTSENTRY_STATE_DIR=/state
VOLUME ["/state"]
EXPOSE 8080
# Production container listen is explicit; host publish remains loopback-only.
CMD ["python", "-m", "uvicorn", "agentsentry.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]

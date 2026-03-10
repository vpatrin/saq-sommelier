FROM python:3.12-slim AS builder

ARG POETRY_VERSION=2.3.2
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}
WORKDIR /build

# Copy core package (path dependency)
COPY core/ core/

# Copy bot dependency files + install into a virtualenv
COPY bot/pyproject.toml bot/poetry.lock bot/
WORKDIR /build/bot
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN poetry install --only main --no-interaction \
    && pip install --no-cache-dir --no-deps --force-reinstall /build/core

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy only the virtualenv — no pip/setuptools/poetry leak
COPY --from=builder /opt/venv /opt/venv
# Strip pip from venv and base image (not needed at runtime, avoids Trivy CVEs)
RUN pip uninstall pip -y && rm -rf /usr/local/lib/python3.12/site-packages/pip*

# Copy bot code
COPY bot/bot/ bot/bot/

RUN useradd --no-create-home --uid 1000 appuser
USER appuser

WORKDIR /app/bot

CMD ["python", "-m", "bot"]

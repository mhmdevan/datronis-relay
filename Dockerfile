# syntax=docker/dockerfile:1.7

# ---- builder ----------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build
RUN pip install --no-cache-dir --upgrade pip build

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip wheel --no-deps --wheel-dir /wheels .

# ---- runtime ----------------------------------------------------------------
FROM python:3.11-slim AS runtime

RUN useradd --system --create-home --uid 10001 relay

WORKDIR /home/relay

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

USER relay

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["datronis-relay"]

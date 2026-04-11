# syntax=docker/dockerfile:1.7

# =============================================================================
# datronis-relay container image
#
# The `claude-agent-sdk` Python package wraps the Claude Code CLI (Node.js)
# and spawns it as a subprocess. That means this image needs BOTH:
#   - Python 3.11 + the datronis-relay wheel
#   - Node.js 20 + @anthropic-ai/claude-code installed globally
#
# Authentication with Claude supports two mutually-exclusive modes:
#   1) `claude login` (recommended) — OAuth against a Claude.ai subscription.
#      Credentials land in /home/relay/.claude and persist via a named
#      volume in docker-compose.yml. Run this ONCE before starting the bot:
#        docker compose run --rm --entrypoint claude relay login
#   2) ANTHROPIC_API_KEY (optional fallback) — pay-per-token via the Anthropic
#      Console. Set DATRONIS-side via docker-compose.yml's env block.
# =============================================================================

# ---- builder ----------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build
RUN pip install --no-cache-dir --upgrade pip build

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip wheel --no-deps --wheel-dir /wheels .

# ---- runtime ----------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Install Node.js 20 + Claude Code CLI. The SDK spawns `claude` as a
# subprocess, so it MUST be on PATH at runtime.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g @anthropic-ai/claude-code \
 && apt-get purge -y --auto-remove gnupg \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/* /root/.npm

# Service user with a real home directory — `claude login` writes OAuth
# credentials to $HOME/.claude, so the user needs a writable home.
RUN useradd --system --create-home --home-dir /home/relay \
            --shell /bin/bash --uid 10001 relay

WORKDIR /home/relay

# Install the Python package globally (the console script lands in
# /usr/local/bin/datronis-relay, reachable by every user).
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

USER relay

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/relay \
    PATH=/usr/local/bin:/usr/bin:/bin

# Persist Claude Code OAuth credentials across container rebuilds.
# docker-compose.yml mounts the `claude_credentials` named volume here.
VOLUME ["/home/relay/.claude"]

ENTRYPOINT ["datronis-relay"]

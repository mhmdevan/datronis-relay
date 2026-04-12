# syntax=docker/dockerfile:1.7

# =============================================================================
# datronis-relay container image
#
# The `claude-agent-sdk` Python package wraps the Claude Code CLI and spawns
# it as a subprocess. Claude Code is installed via Anthropic's native
# installer (the npm package is deprecated).
#
# Authentication with Claude supports two mutually-exclusive modes:
#   1) `claude login` (recommended) — OAuth against a Claude.ai subscription.
#      Credentials land in /home/relay/.claude and persist via a named
#      volume in docker-compose.yml. Run this ONCE before starting the bot:
#        docker compose run --rm --entrypoint claude relay login
#   2) ANTHROPIC_API_KEY (optional fallback) — pay-per-token via the Anthropic
#      Console. Set via docker-compose.yml's env block.
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

# Install curl (needed for the Claude Code native installer) and ca-certs.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Service user with a real home directory — `claude login` writes OAuth
# credentials to $HOME/.claude, so the user needs a writable home.
RUN useradd --system --create-home --home-dir /home/relay \
            --shell /bin/bash --uid 10001 relay

WORKDIR /home/relay

# Install the Python package globally.
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

# Install Claude Code CLI via Anthropic's native installer.
# The installer may put it in ~/.local/bin — we add that to PATH above.
# Install bash if not present (slim images may only have dash as /bin/sh).
RUN apt-get update \
 && apt-get install -y --no-install-recommends bash \
 && apt-get clean && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL https://claude.ai/install.sh | bash \
 && export PATH="/root/.local/bin:$PATH" \
 && claude --version

USER relay

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/relay \
    PATH=/home/relay/.local/bin:/home/relay/.claude/bin:/usr/local/bin:/usr/bin:/bin

# Persist Claude Code OAuth credentials across container rebuilds.
VOLUME ["/home/relay/.claude"]

ENTRYPOINT ["datronis-relay"]

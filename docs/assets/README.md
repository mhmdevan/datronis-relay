# Demo media

This directory holds the screencasts, screenshots, and any other binary
assets the README and the live docs site link to.

## What's expected here

| File | Used by | What to record |
|---|---|---|
| `demo.gif` | top of `README.md` | A 20–30 second screencast: open Telegram → type *"explain the last 50 lines of nginx access log on web-1"* → bot streams a formatted reply. Loops cleanly. ≤ 4 MB if possible (GitHub renders inline). |
| `dashboard.png` | `docs/web-dashboard.md` | A 1440 × 900 light-mode screenshot of the Cost Explorer page (the chart + per-user table is the most visual). |
| `dashboard-dark.png` | `docs/web-dashboard.md` | Same shot in dark mode. |
| `setup-wizard.gif` | `docs/installation.md` | The `datronis-relay setup` flow — especially the QR-coded `claude login` step, which is visually striking. |

## How to record

**Demo GIF (Telegram → Claude reply):**

1. Pre-stage a Telegram chat with the bot and the relay running locally.
2. Use `peek` (Linux) / `Kap` (macOS) / `ScreenToGif` (Windows). Capture only the Telegram window at ~600 × 800.
3. Trim to ≤ 30 seconds.
4. Compress: `ffmpeg -i raw.mp4 -vf "fps=15,scale=600:-1:flags=lanczos,palettegen" palette.png && ffmpeg -i raw.mp4 -i palette.png -lavfi "fps=15,scale=600:-1:flags=lanczos[v];[v][1:v]paletteuse" demo.gif`
5. Aim for under 4 MB so GitHub renders it inline without "Click to view" gating.

**Dashboard screenshots:**

1. Run `cd ui && pnpm dev` (the UI is on `http://localhost:3210`).
2. Seed the local SQLite with mock cost data (`scripts/seed_demo_data.py`, planned).
3. Take a window screenshot at 1440 × 900 with the browser zoom at 100 %.

Drop the files in this directory and the README + docs site will pick them
up automatically on the next push.

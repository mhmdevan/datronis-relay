# Markdown fixtures

Each numbered `.md` file is an **input fixture** — a representative
chunk of Claude-style markdown output covering one or more CommonMark /
GFM elements.

## Layout

```
NN_short_name.md              ← input (CommonMark / GFM)
NN_short_name.telegram.html   ← expected Telegram HTML output   (Phase M-1)
NN_short_name.slack.txt       ← expected Slack mrkdwn output    (Phase M-2)
```

## How they're used today (Phase M-0)

`tests/unit/test_formatting_fixtures.py` walks every `*.md` file here,
parses it through `markdown_ast.parse()`, and asserts:

- the parse succeeds (non-empty AST), and
- no token in the AST has an unknown `type` field
  (the returned token graph is well-formed).

There is no Telegram / Slack assertion yet because no renderer exists
to produce output.

## How they're used in Phase M-1 / M-2

When `TelegramHtmlFormatter` / `SlackMrkdwnFormatter` land, the same test
file will:

1. Render each input through the new formatter.
2. Compare against `NN_short_name.telegram.html` / `NN_short_name.slack.txt`
   byte-for-byte.
3. Fail the test if the rendered output drifts.

## Adding a new fixture

1. Pick the next `NN_` number.
2. Create `NN_short_name.md` with a *minimal* example of the element
   you're adding coverage for — small enough that a reviewer can hold
   the whole expected output in their head.
3. Run `pytest tests/unit/test_formatting_fixtures.py` — it should pass
   as a parse-smoke check with only the new input file.
4. When M-1/M-2 lands, add the expected `.telegram.html` / `.slack.txt`
   side files.

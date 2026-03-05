# Tool Results and LLM Context

## The Problem

When a tool runs, its result needs to end up in two places:

1. **The Board** — for display/notification routing (show on terminal, speak to user, etc.)
2. **The LLM context** — so the agent *remembers* what happened in prior turns

These are independent concerns. A tool with `display="board"` should still have its result stored in the LLM conversation history, even if the agent doesn't speak about it immediately. Otherwise the agent has no memory of prior tool calls and will re-run them when asked about old results.

## How Pipecat's result_callback Works

When a tool handler calls `params.result_callback(value)`, Pipecat:
- Adds the tool result as a message in the conversation context (assistant tool_call + tool result pair)
- Optionally triggers a follow-up LLM completion (`run_llm=True`, the default)

The `FunctionCallResultProperties` has a `run_llm` flag:
- `run_llm=True` (default) — after storing the result, prompt the LLM to generate a response about it
- `run_llm=False` — store the result silently, no follow-up LLM call

## Our Approach

We always pass results back via `result_callback` with default settings (`run_llm=True`). The system prompt handles the rest — it tells the agent not to describe board results unless asked. This way:

- Results are always in the conversation history (memory works)
- The agent can reference old results when the user asks
- The agent stays quiet about board-displayed results because the prompt says to, not because it never saw them

## What NOT to Do

Don't use `run_llm=False` for board-only tools thinking it avoids unnecessary speech. It does, but it also means the LLM never processes the result at all, so it can't answer follow-up questions about it. Let the prompt control verbosity, not the pipeline.

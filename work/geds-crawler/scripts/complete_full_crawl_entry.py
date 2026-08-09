"""Scheduler entrypoint that reports terminal crawl errors instead of looping."""

from __future__ import annotations

from complete_full_crawl import main as completion_main
import complete_full_crawl as completion


original_read_state = completion.read_state


def read_state_without_terminal_error_loop():
    state = original_read_state()
    if state["run"][0] != "running":
        state["queue"].pop("error", None)
    return state


completion.read_state = read_state_without_terminal_error_loop
raise SystemExit(completion_main())

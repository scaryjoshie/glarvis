"""Example tools to demonstrate the GlarvisTool pattern."""

import asyncio
import os

from glarvis.tool import GlarvisTool, TaskResult


class GetTime(GlarvisTool):
    """Simple synchronous tool — returns immediately, agent speaks the answer."""

    name = "get_time"
    description = "Get the current date and time."
    parameters = {}
    required = []

    notification = "silent"
    display = "none"

    async def run(self, **kwargs) -> TaskResult:
        from datetime import datetime

        now = datetime.now().strftime("%I:%M %p on %A, %B %d")
        return TaskResult(value=now)


class SearchFiles(GlarvisTool):
    """Background tool — runs async, posts results to the board."""

    name = "search_files"
    description = (
        "Search for files in the current project by name pattern. "
        "Results will be displayed on the board."
    )
    parameters = {
        "pattern": {"type": "string", "description": "Filename pattern to search for (e.g. '*.py', 'auth')"}
    }
    required = ["pattern"]

    notification = "notify"
    display = "board"
    ttl = 15

    async def run(self, pattern: str = "", **kwargs) -> TaskResult:
        import glob

        matches = glob.glob(f"**/*{pattern}*", recursive=True)
        # Simulate some work for demo purposes
        await asyncio.sleep(1)
        return TaskResult(
            value=matches,
            display_text="\n".join(matches[:20]) if matches else "No files found",
            speak_text=f"Found {len(matches)} files matching {pattern}",
        )

    def board_status(self, elapsed: float) -> str:
        return f"search_files (searching, {elapsed:.1f}s)"


class ListDirectory(GlarvisTool):
    """Quick tool — lists files in a directory, displays on board."""

    name = "list_directory"
    description = (
        "List files in a directory. Results display on the board, "
        "don't read them out loud."
    )
    parameters = {
        "path": {"type": "string", "description": "Directory path to list (default: current directory)"}
    }
    required = []

    notification = "silent"
    display = "board"

    async def run(self, path: str = ".", **kwargs) -> TaskResult:
        try:
            entries = os.listdir(path)
            listing = "\n".join(sorted(entries))
            return TaskResult(
                value=entries,
                display_text=listing,
            )
        except OSError as e:
            return TaskResult(value=None, display_text=f"Error: {e}")

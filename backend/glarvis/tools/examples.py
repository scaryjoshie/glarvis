"""Example tools to demonstrate the tool type system."""

import asyncio
import os

from glarvis.tool import AsyncTool, InlineTool, TaskResult


class GetTime(InlineTool):
    """Returns the current time. Runs inline, agent speaks the answer."""

    name = "get_time"
    description = "Get the current date and time."

    async def run(self, **kwargs) -> TaskResult:
        from datetime import datetime

        now = datetime.now().strftime("%I:%M %p on %A, %B %d")
        return TaskResult(result=now, guide=f"It's {now}")


class SearchFiles(AsyncTool):
    """Searches files by pattern. Runs async, posts results to the board."""

    name = "search_files"
    description = (
        "Search for files in the current project by name pattern. "
        "Results will be displayed on the board."
    )
    parameters = {
        "pattern": {"type": "string", "description": "Filename pattern to search for (e.g. '*.py', 'auth')"}
    }
    required = ["pattern"]
    ttl = 15

    async def run(self, pattern: str = "", **kwargs) -> TaskResult:
        import glob

        matches = glob.glob(f"**/*{pattern}*", recursive=True)
        await asyncio.sleep(1)
        return TaskResult(
            result=matches,
            guide=f"Found {len(matches)} files matching {pattern}",
            board_content="\n".join(matches[:20]) if matches else "No files found",
        )

    def task_display_status(self, elapsed: float) -> str:
        return f"search_files (searching, {elapsed:.1f}s)"


class ListDirectory(InlineTool):
    """Lists files in a directory. Runs inline, posts to board."""

    name = "list_directory"
    description = (
        "List files in a directory. Results display on the board, "
        "don't read them out loud."
    )
    parameters = {
        "path": {"type": "string", "description": "Directory path to list (default: current directory)"}
    }
    display = "board"

    async def run(self, path: str = ".", **kwargs) -> TaskResult:
        try:
            entries = os.listdir(path)
            listing = "\n".join(sorted(entries))
            return TaskResult(
                result=entries,
                guide=f"Listed {len(entries)} items in {path}",
                board_content=listing,
            )
        except OSError as e:
            return TaskResult(result=None, guide=f"Error listing directory: {e}")

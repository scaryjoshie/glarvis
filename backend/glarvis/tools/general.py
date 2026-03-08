"""General-purpose tools — time, files, programs, windows."""

from __future__ import annotations

import asyncio
import os

from glarvis.tool import AsyncTool, Intercept, InlineTool, Keyword, TaskResult


class GetTime(InlineTool):
    name = "get_time"
    description = "Get the current date and time."

    async def run(self, **kwargs) -> TaskResult:
        from datetime import datetime

        now = datetime.now().strftime("%I:%M %p on %A, %B %d")
        return TaskResult(result=now, guide=f"It's {now}")


class WriteBoard(InlineTool):
    name = "write_board"
    description = "Write markdown or text content to the board display. Use this to show explanations, notes, summaries, code, or any visual content to the user."
    parameters = {
        "content": {"type": "string", "description": "Markdown content to display on the board"},
        "title": {"type": "string", "description": "Optional title for the board post"},
    }
    required = ["content"]
    display = "board"

    async def run(self, content: str = "", title: str = "", **kwargs) -> TaskResult:
        if title:
            md = f"# {title}\n\n{content}"
        else:
            md = content
        return TaskResult(
            result="Posted to board",
            board_content=md,
            notify=True,
        )


class ListDirectory(InlineTool):
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
                notify=True,
            )
        except OSError as e:
            return TaskResult(result=None, guide=f"Error listing directory: {e}")


class SearchFiles(AsyncTool):
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
        return TaskResult(
            result=matches,
            guide=f"Found {len(matches)} files matching {pattern}",
            board_content="\n".join(matches[:20]) if matches else "No files found",
            notify=True,
        )

    def task_display_status(self, elapsed: float) -> str:
        return f"search_files (searching, {elapsed:.1f}s)"


class ReadFile(InlineTool):
    name = "read_file"
    description = (
        "Read a file's contents and display them on the board. "
        "Don't read the contents aloud — just say it's on the board."
    )
    parameters = {
        "path": {"type": "string", "description": "File path to read"},
    }
    required = ["path"]
    display = "board"

    async def run(self, path: str = "", **kwargs) -> TaskResult:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(50_000)
            ext = path.rsplit(".", 1)[-1] if "." in path else ""
            md = f"## {path}\n\n```{ext}\n{content}\n```"
            return TaskResult(
                result=f"Read {len(content)} chars from {path}",
                guide="It's on the board",
                board_content=md,
                notify=True,
            )
        except OSError as e:
            return TaskResult(result=f"Error: {e}", guide=f"Couldn't read {path}: {e}")


class SwitchWindow(InlineTool):
    name = "switch_window"
    description = (
        "Show a popup with all open windows to switch to. "
        "Use when the user says 'switch' without specifying a window."
    )

    def get_intercepts(self) -> list[Intercept]:
        return [Keyword("switch", self.run)]

    async def run(self, **kwargs) -> TaskResult:
        if not self.system or not self.system.state.windows:
            return TaskResult(result="No windows detected", guide="No windows open")

        options = []
        for w in self.system.state.windows:
            label = f"{w.title} ({w.app})" if w.app else w.title
            if w.id == self.system.state.foreground_id:
                label += " *"
            opt = {
                "text": label,
                "action": {"tool": "focus_window", "args": {"id": w.id}},
            }
            icon = self.system.get_window_icon(w.id)
            if icon:
                opt["icon"] = icon
            options.append(opt)

        return await self.handle.execute_tool(
            "show_choices", options=options, prompt="Switch to:",
        )


class FocusWindow(InlineTool):
    name = "focus_window"
    description = (
        "Focus a window by its ID number from the System State window list. "
        "Use this when the user says 'go to', 'switch to', 'open' (if already open), or 'focus'."
    )
    parameters = {
        "id": {"type": "integer", "description": "Window ID from the System State list"},
    }
    required = ["id"]

    async def run(self, id: int = 0, **kwargs) -> TaskResult:
        win = next((w for w in self.system.state.windows if w.id == id), None)
        if not win:
            return TaskResult(result=f"Window {id} not found", guide=f"Couldn't find window {id}")
        if self.system.focus_window(id):
            return TaskResult(result=f"Focused {win.title}", guide=f"Switched to {win.title}")
        return TaskResult(result=f"Failed to focus {win.title}", guide=f"Couldn't bring {win.title} to front")


class SearchPrograms(InlineTool):
    name = "search_programs"
    description = (
        "Search installed programs by name. Returns matching program names. "
        "Use this before open_program to find the correct program name. "
        "If there's one match, you can go ahead and open it. "
        "If there are multiple matches, ask the user which one (use multi_choice if helpful)."
    )
    parameters = {
        "query": {"type": "string", "description": "Program name to search for (e.g. 'minecraft', 'chrome', 'code')"},
    }
    required = ["query"]

    async def run(self, query: str = "", **kwargs) -> TaskResult:
        matches = self.system.search_programs(query)
        if not matches:
            return TaskResult(
                result={"matches": [], "query": query},
                guide=f"No programs found matching '{query}'",
            )
        names = [m.name for m in matches]
        if len(names) == 1:
            return TaskResult(
                result={"matches": names, "query": query},
                guide=f"Found {names[0]}",
            )
        return TaskResult(
            result={"matches": names, "query": query},
            guide=f"Found {len(names)} programs matching '{query}': {', '.join(names[:10])}",
            board_content="## Program Search\n" + "\n".join(f"- {n}" for n in names),
            notify=True,
        )


class OpenProgram(InlineTool):
    name = "open_program"
    description = (
        "Launch a program by its exact name (as returned by search_programs). "
        "Always use search_programs first to find the correct name. "
        "Before opening, check the System State window list — if the app "
        "is already open, use focus_window instead."
    )
    parameters = {
        "name": {"type": "string", "description": "Exact program name from search_programs results"},
    }
    required = ["name"]

    async def run(self, name: str = "", **kwargs) -> TaskResult:
        program = next((p for p in self.system.programs if p.name == name), None)
        if not program:
            program = next((p for p in self.system.programs if p.name.lower() == name.lower()), None)
        if not program:
            return TaskResult(
                result=f"Program '{name}' not found",
                guide=f"Couldn't find '{name}'. Try search_programs first.",
            )
        if self.system.launch_program(program.app_id):
            return TaskResult(result=f"Launched {program.name}", guide=f"Opening {program.name}")
        return TaskResult(result=f"Failed to launch {program.name}", guide=f"Couldn't launch {program.name}")

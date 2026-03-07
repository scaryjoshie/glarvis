"""System tools — window management, program launching, file reading."""

from __future__ import annotations

from typing import TYPE_CHECKING

from glarvis.tool import AsyncTool, InlineTool, TaskResult

if TYPE_CHECKING:
    from glarvis.system.monitor import SystemMonitor


class FocusWindow(InlineTool):
    """Bring a window to the foreground by its stable ID."""

    name = "focus_window"
    description = (
        "Focus a window by its ID number from the System State window list. "
        "Use this when the user says 'go to', 'switch to', 'open' (if already open), or 'focus'."
    )
    parameters = {
        "id": {"type": "integer", "description": "Window ID from the System State list"},
    }
    required = ["id"]

    def __init__(self, monitor: SystemMonitor):
        self._monitor = monitor

    async def run(self, id: int = 0, **kwargs) -> TaskResult:
        if self._monitor.focus_window(id):
            win = next((w for w in self._monitor.state.windows if w.id == id), None)
            title = win.title if win else f"window {id}"
            return TaskResult(result=f"Focused {title}", guide=f"Switched to {title}")
        return TaskResult(result=f"Window {id} not found", guide=f"Couldn't find window {id}")


class SearchPrograms(InlineTool):
    """Search installed programs by name."""

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

    def __init__(self, monitor: SystemMonitor):
        self._monitor = monitor

    async def run(self, query: str = "", **kwargs) -> TaskResult:
        matches = self._monitor.search_programs(query)
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
        )


class OpenProgram(InlineTool):
    """Launch a program by its exact name from search_programs."""

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

    def __init__(self, monitor: SystemMonitor):
        self._monitor = monitor

    async def run(self, name: str = "", **kwargs) -> TaskResult:
        # Find exact match in program list
        program = next((p for p in self._monitor.programs if p.name == name), None)
        if not program:
            # Try case-insensitive
            program = next((p for p in self._monitor.programs if p.name.lower() == name.lower()), None)
        if not program:
            return TaskResult(
                result=f"Program '{name}' not found",
                guide=f"Couldn't find '{name}'. Try search_programs first.",
            )
        if self._monitor.launch_program(program.app_id):
            return TaskResult(result=f"Launched {program.name}", guide=f"Opening {program.name}")
        return TaskResult(result=f"Failed to launch {program.name}", guide=f"Couldn't launch {program.name}")


class ReadFile(InlineTool):
    """Read a file and post its contents to the board."""

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
                content = f.read(50_000)  # cap at 50KB
            ext = path.rsplit(".", 1)[-1] if "." in path else ""
            md = f"## {path}\n\n```{ext}\n{content}\n```"
            return TaskResult(
                result=f"Read {len(content)} chars from {path}",
                guide="It's on the board",
                board_content=md,
            )
        except OSError as e:
            return TaskResult(result=f"Error: {e}", guide=f"Couldn't read {path}: {e}")

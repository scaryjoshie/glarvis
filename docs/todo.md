# TODO — Current Work in Progress

## Actively in progress (was doing when paused to write docs)

### Update all files to match new tool type system
The tool types (BaseTool, InlineTool, AsyncTool, SessionTool) have been defined in `glarvis/tool.py` but the rest of the codebase still references the old types. Need to update:

1. **`glarvis/task_manager.py`**:
   - Change `tool: Tool` → `tool: AsyncTool` in TaskState (DONE)
   - Change `spawn(self, tool: Tool, ...)` → `spawn(self, tool: AsyncTool, ...)` (DONE)
   - Fix stale `TaskResult` fields: `value` → `result`, `display_text` → `guide`, `speak_text` → `guide`
   - The line `TaskResult(value=None, display_text=f"Error: {e}")` needs to become `TaskResult(result=None, guide=f"Error: {e}")`
   - Fix `board_status()` references → `task_display_status()`
   - Fix snapshot() references to `result.display_text` → `result.guide` or `result.board_content`
   - Fix `to_ui_list()` references to `result.display_text`
   - Remove `DisplayMode` import if no longer needed directly

2. **`glarvis/orchestrator.py`**:
   - Change `self._tools: dict[str, Tool]` → `dict[str, BaseTool]`
   - Change `register(self, tool: Tool)` → `register(self, tool: BaseTool)`
   - Change `_execute_tool(self, tool: Tool, ...)` → `_execute_tool(self, tool: BaseTool, ...)`
   - Update routing logic: replace `if tool.ttl or tool.notification != "silent"` with `isinstance(tool, AsyncTool)`
   - Remove `tool.on_start()` / `tool.on_complete()` calls from inline path (InlineTool doesn't have these)
   - Fix `TaskResult(value=..., display_text=...)` → `TaskResult(result=..., guide=...)`
   - Update result_callback to use `result.result` instead of `result.value`

3. **`glarvis/tools/examples.py`**:
   - `GetTime` → subclass `InlineTool` instead of `Tool`
   - `ListDirectory` → subclass `InlineTool` (it's silent/board, runs inline)
   - `SearchFiles` → subclass `AsyncTool` (it has TTL, notification=notify)
   - Fix all `TaskResult` field names
   - Remove old metadata that's now handled by the class type (notification/display defaults)

4. **`server.py` and `main.py`**:
   - These just import tools from examples.py, so they should work once examples.py is fixed
   - But verify imports still resolve

5. **`glarvis/task_manager.py` _handle_completion()**:
   - Uses `tool.display`, `result.display_text`, `result.speak_text` — all need updating
   - `display_text` → use `result.board_content` for board display
   - `speak_text` → use `result.guide` for notification message
   - The `tool.display` field still exists on AsyncTool, so that's fine

## After the type system update

### Wire up Board display to frontend
- TaskManager._handle_completion() currently print()s to terminal for board display
- Need to broadcast `board_post` WebSocket message instead
- Need to create Board stream data model (list of items with author, timestamp, content)
- Frontend Board component needs to receive and render these

### Build system utility libraries
```
glarvis/system/
  __init__.py
  windows.py    # list_windows(), focus_window(), open_program()
  processes.py  # list_processes(), kill_process()
  time_utils.py # current_time(), formatted time
  clipboard.py  # get/set clipboard
```
These are imported by tools AND by the context injector for ambient state.

### Expand context injection
- Currently only injects task state snapshot
- Add ambient system state (time, active windows, system resources)
- Uses the system utility libraries above

### Build first real tools
Suggested order:
1. `open_program` (InlineTool) — opens a program by name
2. `focus_window` (InlineTool) — brings a window to front
3. `read_file` (InlineTool) — reads a file, posts content to Board
4. `search_codebase` (AsyncTool) — searches files, posts results to Board
5. `list_processes` (InlineTool) — lists running processes

### Frontend improvements
- Task chips in TaskDisplay (currently just a list)
- Board stream sidebar
- Click task to expand in Board main area
- Task hover for details
- Proper styling pass

### Future (not now)
- SessionTool orchestrator routing (on_input)
- Claude Code bridge (SessionTool)
- Browser automation (SessionTool)
- Process discovery (external process scanning)
- Agent memory system
- Avatar overlay / toast notifications outside tab
- Task context mode (click task, agent knows you're focused on it)

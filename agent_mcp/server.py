"""Stdio MCP interface between the master agent and sub-agents."""

from mcp.server.fastmcp import FastMCP

from orchestration import result, start, status
from task import Task, TaskRequest, TaskResult

mcp = FastMCP("agent-communication")


@mcp.tool()
def start_task(task: TaskRequest) -> Task:
    """Launch an isolated worker and return its task_id and host process pid."""
    return start(task)


@mcp.tool()
def get_task_status(task: Task) -> dict:
    """Get execution state and available exit/error details for a task ID."""
    return status(task)


@mcp.tool()
def get_task_result(task: Task) -> TaskResult:
    """Retrieve a finished worker's delivery files and return their local location."""
    return result(task)


if __name__ == "__main__":
    mcp.run(transport="stdio")

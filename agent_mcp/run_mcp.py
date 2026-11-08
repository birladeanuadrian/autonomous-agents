import argparse
import asyncio
import json
import sys
from datetime import timedelta
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def tool_payload(result) -> dict:
    if result.isError:
        raise RuntimeError(result.model_dump_json(indent=2))
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(next(item.text for item in result.content if item.type == "text"))


async def main(model: str, reasoning_effort: str | None = None):
    server = Path(__file__).with_name("server.py").resolve()
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server)],
    )
    async with stdio_client(params) as streams:
        async with ClientSession(
            *streams,
            read_timeout_seconds=timedelta(minutes=10),
        ) as session:
            await session.initialize()
            result = await session.call_tool(
                "start_task",
                {
                    "task": {"task": (
                        "Configure the unit tests so that they output a junit xml file and a coverage xml file "
                        "Add in task outputs the generated xml files"
                    ), "model": model, "reasoning_effort": reasoning_effort}
                },
            )
            print(result.model_dump_json(indent=2))
            task = tool_payload(result)
            while True:
                await asyncio.sleep(120)
                result = await session.call_tool("get_task_status", {"task": task})
                print(result.model_dump_json(indent=2), flush=True)
                status = tool_payload(result)
                if status["state"] in {"completed", "failed"}:
                    break
            result = await session.call_tool("get_task_result", {"task": task})
            print(result.model_dump_json(indent=2), flush=True)
            tool_payload(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    asyncio.run(main("gpt-6.1-terra", "medium"))

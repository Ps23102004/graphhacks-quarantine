#!/usr/bin/env python3
"""CLI bridge to list and call MCP tools over stdio.

Usage:
    scripts/mcp_inspect.py list
    scripts/mcp_inspect.py call <tool_name> [json_arguments]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client


async def _run_mcp(action: str, tool_name: str | None = None, tool_args: dict | None = None):
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "quarantine.mcp_server"],
        env=os.environ.copy(),
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            if action == "list":
                tools_result = await session.list_tools()
                tools_data = [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.inputSchema,
                    }
                    for t in tools_result.tools
                ]
                return tools_data
            elif action == "call":
                if not tool_name:
                    raise ValueError("Tool name is required for 'call'")
                res = await session.call_tool(tool_name, tool_args or {})
                # Extract output content
                out_data = None
                if res.structuredContent:
                    out_data = res.structuredContent.get("result", res.structuredContent)
                elif res.content:
                    first = res.content[0]
                    text = getattr(first, "text", "")
                    try:
                        out_data = json.loads(text)
                    except Exception:
                        out_data = text
                else:
                    out_data = {}
                if res.isError:
                    raise RuntimeError(f"Tool {tool_name} returned error: {out_data}")
                return out_data
            else:
                raise ValueError(f"Unknown action: {action}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Quarantine MCP CLI inspection bridge")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    subparsers.add_parser("list", help="List available MCP tools")

    call_parser = subparsers.add_parser("call", help="Call an MCP tool with JSON arguments")
    call_parser.add_argument("tool", help="Name of the MCP tool to call")
    call_parser.add_argument("args", nargs="?", default="{}", help="JSON arguments dictionary")

    args = parser.parse_args()

    try:
        if args.subcommand == "list":
            data = asyncio.run(_run_mcp("list"))
            print(json.dumps(data, indent=2))
            return 0
        elif args.subcommand == "call":
            try:
                tool_args = json.loads(args.args)
                if not isinstance(tool_args, dict):
                    raise ValueError("Arguments must be a JSON object")
            except Exception as e:
                sys.stderr.write(f"Invalid JSON arguments: {e}\n")
                return 2

            data = asyncio.run(_run_mcp("call", tool_name=args.tool, tool_args=tool_args))
            print(json.dumps(data, indent=2))
            return 0
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

import asyncio
import os
import json
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

# Configuration for our Dockerized MCP servers
# We run them via `docker run -i` so they can communicate via stdio.
MCP_SERVERS = {
    "github": StdioServerParameters(
        command="docker",
        args=[
            "run", "-i", "--rm",
            "-e", f"GITHUB_PERSONAL_ACCESS_TOKEN={os.environ.get('GITHUB_TOKEN', '')}",
            "node:20",
            "npx", "-y", "@modelcontextprotocol/server-github"
        ],
        env=None
    ),
    "kali-tools": StdioServerParameters(
        command="docker",
        args=[
            "run", "-i", "--rm",
            "durkdiggler/kali-mcp:latest"  # Example image from research
        ],
        env=None
    ),
    "shodan": StdioServerParameters(
        command="docker",
        args=[
            "run", "-i", "--rm",
            "-e", f"SHODAN_API_KEY={os.environ.get('SHODAN_API_KEY', '')}",
            "python:3.11",
            "sh", "-c", "pip install mcp-server-shodan && python -m mcp_server_shodan"
        ],
        env=None
    )
}

async def execute_mcp_tool(server_name: str, tool_name: str, arguments: dict):
    """
    Connects to the specified MCP server (via Docker), executes a tool, and returns the result.
    """
    if server_name not in MCP_SERVERS:
        return f"[ERROR] Unknown MCP Server: {server_name}"

    server_params = MCP_SERVERS[server_name]
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Execute the tool
                result = await session.call_tool(tool_name, arguments=arguments)
                
                # Format the result 
                output = []
                for content in result.content:
                    if content.type == "text":
                        output.append(content.text)
                    else:
                        output.append(str(content))
                
                return "\n".join(output)
                
    except Exception as e:
        return f"[MCP EXECUTION ERROR] Failed to run {tool_name} on {server_name}: {e}"

async def get_mcp_tools(server_name: str):
    """
    Connects to the specified MCP server and returns the available tools.
    """
    if server_name not in MCP_SERVERS:
        return []

    server_params = MCP_SERVERS[server_name]
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # List tools
                result = await session.list_tools()
                return [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    }
                    for tool in result.tools
                ]
    except Exception as e:
        print(f"[MCP DISCOVERY ERROR] Failed to list tools on {server_name}: {e}")
        return []

def run_mcp_tool_sync(server_name: str, tool_name: str, arguments: dict):
    """
    Synchronous wrapper for execute_mcp_tool.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(execute_mcp_tool(server_name, tool_name, arguments))

def get_mcp_tools_sync(server_name: str):
    """
    Synchronous wrapper for get_mcp_tools.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(get_mcp_tools(server_name))

if __name__ == "__main__":
    # Simple test
    print("Testing MCP Gateway...")
    print("This will hang if Docker is not running or image cannot be pulled.")

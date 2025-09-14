from fastmcp import FastMCP
from rich import print

mcp = FastMCP("piano-club-assistant")

@mcp.tool()
async def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

@mcp.tool()
async def print_message(message: str) -> None:
    """Print a message to the console."""
    print(message)
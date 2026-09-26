from fastmcp import FastMCP
import random

# Create MCP server
mcp = FastMCP("SimpleMathServer")


# Tool 1: Add two numbers
@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


# Tool 2: Generate random number
@mcp.tool()
def random_number(min_value: int, max_value: int) -> int:
    """Generate a random integer between two numbers."""

    if min_value > max_value:
        raise ValueError("min_value must be less than or equal to max_value")

    return random.randint(min_value, max_value)


# Resource: Server information
@mcp.resource("info://server")
def server_info() -> str:
    """Return information about this MCP server."""

    return """
Simple Math MCP Server

Name: SimpleMathServer

Tools:
1. add_numbers
   - Adds two numbers.

2. random_number
   - Generates a random integer between two numbers.

Resource:
info://server
   - Provides information about this MCP server.

Created using FastMCP and Python.
"""


# Start the server
if __name__ == "__main__":
    mcp.run(transport='http',host='0.0.0.0',port=8000)
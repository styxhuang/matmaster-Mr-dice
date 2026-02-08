"""
Main entry point for MrDice server.
This file provides backward compatibility and redirects to the new structure.
"""
from .core.server import mcp, structure_search_agent

__all__ = ["mcp", "structure_search_agent"]

if __name__ == "__main__":
    from .core.server import mcp, print_startup_env
    import logging

    print_startup_env()
    logging.info("Starting MrDice Unified MCP Server...")
    mcp.run(transport="sse")


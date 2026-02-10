"""
Main entry point for MrDice server.
This file provides backward compatibility and redirects to the new structure.
"""
from .core.server import mcp, fetch_structures_from_db

__all__ = ["mcp", "fetch_structures_from_db"]

if __name__ == "__main__":
    from .core.server import mcp, print_startup_env
    import logging

    print_startup_env()
    logging.info("Starting MrDice Unified MCP Server...")
    mcp.run(transport="http-streamable")


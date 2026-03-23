"""CLI entry point for Errordog MCP server."""

from errordog.server import create_server


def main() -> None:
    """Create and run the Errordog MCP server."""
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()

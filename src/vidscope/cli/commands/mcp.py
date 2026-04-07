"""`vidscope mcp ...` subcommands.

Currently exposes only ``vidscope mcp serve`` which starts the MCP
server on stdio. Future subcommands (e.g. ``vidscope mcp tools``
for listing the registered tools without starting the server) slot
in here.

The Typer sub-application is registered on the root app in
:mod:`vidscope.cli.app` via ``app.add_typer(mcp_app, name="mcp")``.
"""

from __future__ import annotations

import typer

__all__ = ["mcp_app"]


mcp_app = typer.Typer(
    name="mcp",
    help="MCP (Model Context Protocol) server for AI agents.",
    no_args_is_help=True,
    add_completion=False,
)


@mcp_app.command("serve")
def serve() -> None:
    """Start the vidscope MCP server on stdio.

    Exposes every vidscope use case as an MCP tool. Connect from any
    MCP client (Claude Desktop, Cline, any stdio MCP client) by
    configuring the client to run ``vidscope mcp serve`` as the
    server command.

    The server reads JSON-RPC requests from stdin and writes
    responses to stdout; all logs and errors go to stderr.

    Press Ctrl-C to stop the server.
    """
    # Imported lazily so `vidscope mcp --help` and the top-level
    # `vidscope --help` don't pay the cost of loading mcp + pydantic
    # + starlette unless the user actually wants to serve.
    from vidscope.mcp.server import main  # noqa: PLC0415

    main()

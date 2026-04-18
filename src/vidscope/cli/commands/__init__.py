"""CLI command implementations. One file per user-facing subcommand."""

from __future__ import annotations

from vidscope.cli.commands.add import add_command
from vidscope.cli.commands.collections import collection_app
from vidscope.cli.commands.export import export_command
from vidscope.cli.commands.cookies import cookies_app
from vidscope.cli.commands.doctor import doctor_command
from vidscope.cli.commands.explain import explain_command
from vidscope.cli.commands.list import list_command
from vidscope.cli.commands.mcp import mcp_app
from vidscope.cli.commands.search import search_command
from vidscope.cli.commands.show import show_command
from vidscope.cli.commands.review import review_command
from vidscope.cli.commands.stats import refresh_stats_command
from vidscope.cli.commands.status import status_command
from vidscope.cli.commands.suggest import suggest_command
from vidscope.cli.commands.tags import tag_app
from vidscope.cli.commands.trending import trending_command
from vidscope.cli.commands.watch import watch_app

__all__ = [
    "add_command",
    "collection_app",
    "cookies_app",
    "doctor_command",
    "export_command",
    "explain_command",
    "list_command",
    "mcp_app",
    "refresh_stats_command",
    "review_command",
    "search_command",
    "show_command",
    "status_command",
    "suggest_command",
    "tag_app",
    "trending_command",
    "watch_app",
]

"""
CLI commands for aipartnerupflow
"""

from aipartnerupflow.cli.commands.run import app as run_app
from aipartnerupflow.cli.commands.serve import app as serve_app
from aipartnerupflow.cli.commands.daemon import app as daemon_app
from aipartnerupflow.cli.commands.list_flows import app as list_flows_app
from aipartnerupflow.cli.commands.tasks import app as tasks_app

__all__ = [
    "run",
    "serve",
    "daemon",
    "list_flows",
    "tasks",
]

# Expose apps for main.py
run = type("run", (), {"app": run_app})()
serve = type("serve", (), {"app": serve_app})()
daemon = type("daemon", (), {"app": daemon_app})()
list_flows = type("list_flows", (), {"app": list_flows_app})()
tasks = type("tasks", (), {"app": tasks_app})()


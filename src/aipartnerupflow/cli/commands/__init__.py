"""
CLI commands for aipartnerupflow
"""

from aipartnerupflow.cli.commands.run import app as run_app
from aipartnerupflow.cli.commands.serve import app as serve_app
from aipartnerupflow.cli.commands.daemon import app as daemon_app
from aipartnerupflow.cli.commands.tasks import app as tasks_app
from aipartnerupflow.cli.commands.examples import app as examples_app
from aipartnerupflow.cli.commands.generate import app as generate_app

__all__ = [
    "run",
    "serve",
    "daemon",
    "tasks",
    "examples",
    "generate",
]

# Expose apps for main.py
run = type("run", (), {"app": run_app})()
serve = type("serve", (), {"app": serve_app})()
daemon = type("daemon", (), {"app": daemon_app})()
tasks = type("tasks", (), {"app": tasks_app})()
examples = type("examples", (), {"app": examples_app})()
generate = type("generate", (), {"app": generate_app})()


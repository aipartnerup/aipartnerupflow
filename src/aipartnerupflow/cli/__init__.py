"""CLI tools for aipartnerupflow"""
from aipartnerupflow.cli.extension import CLIExtension
__all__ = ["CLIExtension", "app"]
def __getattr__(name):
    if name == "app":
        from aipartnerupflow.cli.main import app
        return app
    raise AttributeError(f"module {__name__} has no attribute {name}")

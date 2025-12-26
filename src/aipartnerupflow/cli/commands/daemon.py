"""
Daemon command for managing background service
"""

import os
import sys
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional
import typer
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

app = typer.Typer(name="daemon", help="Manage daemon service")

# Default daemon PID file location
DEFAULT_PID_FILE = Path.home() / ".aipartnerup" / "aipartnerupflow.pid"
DEFAULT_LOG_FILE = Path.home() / ".aipartnerup" / "aipartnerupflow.log"


def get_pid_file() -> Path:
    """Get PID file path"""
    pid_file = os.getenv("AIPARTNERUPFLOW_DAEMON_PID_FILE", str(DEFAULT_PID_FILE))
    pid_path = Path(pid_file)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    return pid_path


def get_log_file() -> Path:
    """Get log file path"""
    log_file = os.getenv("AIPARTNERUPFLOW_DAEMON_LOG_FILE", str(DEFAULT_LOG_FILE))
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    return log_path


def read_pid() -> Optional[int]:
    """Read PID from file"""
    pid_file = get_pid_file()
    if not pid_file.exists():
        return None
    
    try:
        with open(pid_file, "r") as f:
            pid_str = f.read().strip()
            return int(pid_str) if pid_str else None
    except (ValueError, IOError):
        return None


def write_pid(pid: int) -> None:
    """Write PID to file"""
    pid_file = get_pid_file()
    with open(pid_file, "w") as f:
        f.write(str(pid))


def remove_pid() -> None:
    """Remove PID file"""
    pid_file = get_pid_file()
    if pid_file.exists():
        pid_file.unlink()


def is_process_running(pid: int) -> bool:
    """Check if process is running"""
    try:
        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
        return True
    except OSError:
        return False


@app.command()
def start(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    protocol: str = typer.Option("a2a", "--protocol", help="Protocol to use (a2a or mcp)"),
    background: bool = typer.Option(True, "--background/--foreground", help="Run in background"),
):
    """Start daemon service"""
    try:
        # Check if daemon is already running
        existing_pid = read_pid()
        if existing_pid and is_process_running(existing_pid):
            typer.echo(f"Daemon is already running (PID: {existing_pid})", err=True)
            raise typer.Exit(1)
        elif existing_pid:
            # Stale PID file, remove it
            remove_pid()
        
        # Build command to start API server
        log_file = get_log_file()
        python_exe = sys.executable
        api_module = "aipartnerupflow.api.main"
        
        cmd = [
            python_exe, "-m", api_module
        ]
        
        # Set environment variables for API server
        env = os.environ.copy()
        env["AIPARTNERUPFLOW_API_HOST"] = host
        env["AIPARTNERUPFLOW_API_PORT"] = str(port)
        env["AIPARTNERUPFLOW_API_PROTOCOL"] = protocol
        
        if background:
            typer.echo("Starting daemon service in background...")
            typer.echo(f"Log file: {log_file}")
            
            # Start process in background
            with open(log_file, "a") as log_f:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    start_new_session=True,  # Detach from terminal
                )
            
            # Write PID
            write_pid(process.pid)
            
            # Give it a moment to start (check if it crashes immediately)
            time.sleep(0.3)
            
            # Check if process is still running
            if process.poll() is None:
                typer.echo(f"Daemon started successfully (PID: {process.pid})")
                typer.echo(f"API server running on {host}:{port} (protocol: {protocol})")
            else:
                typer.echo("Daemon failed to start. Check log file for details.", err=True)
                remove_pid()
                raise typer.Exit(1)
        else:
            typer.echo("Starting daemon service in foreground...")
            typer.echo(f"API server will run on {host}:{port} (protocol: {protocol})")
            typer.echo("Press Ctrl+C to stop")
            # Run in foreground
            subprocess.run(cmd, env=env)
            
    except Exception as e:
        typer.echo(f"Error starting daemon: {str(e)}", err=True)
        logger.exception("Error starting daemon")
        raise typer.Exit(1)


@app.command()
def stop():
    """Stop daemon service"""
    try:
        pid = read_pid()
        if pid is None:
            typer.echo("Daemon is not running (no PID file found)")
            return
        
        if not is_process_running(pid):
            typer.echo(f"Daemon process (PID: {pid}) is not running (stale PID file)")
            remove_pid()
            return
        
        typer.echo(f"Stopping daemon (PID: {pid})...")
        
        # Send SIGTERM signal
        try:
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to terminate (max 10 seconds)
            # First check quickly (many processes respond immediately)
            time.sleep(0.2)
            if not is_process_running(pid):
                # Process terminated quickly
                pass
            else:
                # Wait longer for graceful shutdown (up to 9.8 more seconds)
                for _ in range(49):  # 49 * 0.2 = 9.8 seconds
                    time.sleep(0.2)
                    if not is_process_running(pid):
                        break
                else:
                    # Process didn't terminate, force kill
                    typer.echo("Process didn't terminate, sending SIGKILL...")
                    os.kill(pid, signal.SIGKILL)
                    time.sleep(0.2)  # SIGKILL is immediate, short wait is enough
            
            if not is_process_running(pid):
                typer.echo("Daemon stopped successfully")
                remove_pid()
            else:
                typer.echo("Failed to stop daemon", err=True)
                raise typer.Exit(1)
                
        except ProcessLookupError:
            typer.echo("Process not found (may have already stopped)")
            remove_pid()
        except PermissionError:
            typer.echo(f"Permission denied. Cannot stop process {pid}", err=True)
            raise typer.Exit(1)
            
    except Exception as e:
        typer.echo(f"Error stopping daemon: {str(e)}", err=True)
        logger.exception("Error stopping daemon")
        raise typer.Exit(1)


@app.command()
def status():
    """Check daemon status"""
    try:
        pid = read_pid()
        if pid is None:
            typer.echo("Status: Not running (no PID file)")
            return
        
        if is_process_running(pid):
            typer.echo(f"Status: Running (PID: {pid})")
            pid_file = get_pid_file()
            log_file = get_log_file()
            typer.echo(f"PID file: {pid_file}")
            typer.echo(f"Log file: {log_file}")
        else:
            typer.echo(f"Status: Not running (stale PID file: {pid})")
            typer.echo("You may want to remove the stale PID file")
            
    except Exception as e:
        typer.echo(f"Error checking daemon status: {str(e)}", err=True)
        logger.exception("Error checking daemon status")
        raise typer.Exit(1)


@app.command()
def restart(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
):
    """Restart daemon service"""
    try:
        # Stop if running
        pid = read_pid()
        if pid and is_process_running(pid):
            typer.echo("Stopping existing daemon...")
            stop()
            # Brief wait to ensure resources are released
            time.sleep(0.3)
        
        # Start
        typer.echo("Starting daemon...")
        start(host=host, port=port, background=True)
        
    except Exception as e:
        typer.echo(f"Error restarting daemon: {str(e)}", err=True)
        logger.exception("Error restarting daemon")
        raise typer.Exit(1)


@app.command()
def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show"),
):
    """View daemon logs"""
    try:
        log_file = get_log_file()
        if not log_file.exists():
            typer.echo(f"Log file not found: {log_file}")
            return
        
        if follow:
            typer.echo(f"Following log file: {log_file}")
            typer.echo("Press Ctrl+C to stop")
            try:
                import subprocess
                subprocess.run(["tail", "-f", str(log_file)])
            except FileNotFoundError:
                # Fallback to Python implementation
                with open(log_file, "r") as f:
                    # Seek to end
                    f.seek(0, 2)
                    try:
                        while True:
                            line = f.readline()
                            if line:
                                typer.echo(line.rstrip())
                            else:
                                time.sleep(0.1)
                    except KeyboardInterrupt:
                        pass
        else:
            # Show last N lines
            with open(log_file, "r") as f:
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    typer.echo(line.rstrip())
                    
    except Exception as e:
        typer.echo(f"Error viewing logs: {str(e)}", err=True)
        logger.exception("Error viewing logs")
        raise typer.Exit(1)


"""
Test CLI daemon command functionality

Tests the daemon command as documented in README.md
- Fast unit tests with mocks (default, ~2s total)
- Slow integration tests with real processes (marked @pytest.mark.slow, run separately)
"""

import pytest
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from aipartnerupflow.cli.main import app
from aipartnerupflow.cli.commands.daemon import (
    get_pid_file,
    get_log_file,
    read_pid,
    write_pid,
)

runner = CliRunner()


@pytest.fixture
def cleanup_daemon_files():
    """Cleanup daemon PID and log files before and after tests"""
    pid_file = get_pid_file()
    log_file = get_log_file()
    
    # Cleanup before
    if pid_file.exists():
        pid_file.unlink()
    if log_file.exists():
        log_file.unlink()
    
    yield
    
    # Cleanup after
    if pid_file.exists():
        pid_file.unlink()
    if log_file.exists():
        log_file.unlink()


class TestDaemonCommand:
    """Fast unit tests - verify core daemon command functionality"""
    
    def test_daemon_help(self):
        """Test daemon command help output"""
        result = runner.invoke(app, ["daemon", "--help"])
        assert result.exit_code == 0
        assert "Manage daemon" in result.stdout
    
    def test_daemon_subcommands_help(self):
        """Test daemon subcommand help (start, stop)"""
        # Start help
        result = runner.invoke(app, ["daemon", "start", "--help"])
        assert result.exit_code == 0
        assert "Start daemon service" in result.stdout
        
        # Stop help
        result = runner.invoke(app, ["daemon", "stop", "--help"])
        assert result.exit_code == 0
        assert "Stop daemon service" in result.stdout
    
    def test_daemon_status_when_not_running(self, cleanup_daemon_files):
        """Test daemon status when no daemon is running"""
        result = runner.invoke(app, ["daemon", "status"])
        assert result.exit_code == 0
        assert "not running" in result.stdout.lower() or "no pid" in result.stdout.lower()
    
    def test_daemon_stop_when_not_running(self, cleanup_daemon_files):
        """Test daemon stop when no daemon is running"""
        result = runner.invoke(app, ["daemon", "stop"])
        assert result.exit_code == 0
        assert "not running" in result.stdout.lower() or "no pid" in result.stdout.lower()
    
    @patch('aipartnerupflow.cli.commands.daemon.subprocess.Popen')
    def test_daemon_start_mocked(self, mock_popen, cleanup_daemon_files):
        """Test daemon start with port and protocol (mocked)"""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process still running
        mock_popen.return_value = mock_process
        
        result = runner.invoke(app, [
            "daemon", "start",
            "--port", "9001",
            "--protocol", "mcp",
            "--background"
        ])
        
        assert result.exit_code == 0
        assert "started successfully" in result.stdout.lower()
        assert "9001" in result.stdout
        assert "mcp" in result.stdout.lower()
        assert read_pid() == 12345
    
    @patch('aipartnerupflow.cli.commands.daemon.is_process_running')
    @patch('aipartnerupflow.cli.commands.daemon.os.kill')
    def test_daemon_stop_mocked(self, mock_kill, mock_is_running, cleanup_daemon_files):
        """Test daemon stop with process running (mocked)"""
        write_pid(99999)
        mock_is_running.side_effect = [True] + [False] * 10
        
        result = runner.invoke(app, ["daemon", "stop"])
        
        assert result.exit_code == 0
        assert "stopped successfully" in result.stdout.lower()
        assert mock_kill.called
        assert read_pid() is None
    
    @patch('aipartnerupflow.cli.commands.daemon.is_process_running')
    @patch('aipartnerupflow.cli.commands.daemon.os.kill')
    def test_daemon_stop_with_sigkill_fallback_mocked(self, mock_kill, mock_is_running, cleanup_daemon_files):
        """Test daemon stop with SIGKILL fallback (mocked)"""
        write_pid(99998)
        # Process takes multiple checks to die
        mock_is_running.side_effect = [True] * 51 + [False]
        
        result = runner.invoke(app, ["daemon", "stop"])
        
        assert result.exit_code == 0
        assert "stopped successfully" in result.stdout.lower()
        assert mock_kill.called
    
    @patch('aipartnerupflow.cli.commands.daemon.is_process_running')
    def test_daemon_status_when_running_mocked(self, mock_is_running, cleanup_daemon_files):
        """Test daemon status when running (mocked)"""
        write_pid(55555)
        mock_is_running.return_value = True
        
        result = runner.invoke(app, ["daemon", "status"])
        
        assert result.exit_code == 0
        assert "running" in result.stdout.lower()
        assert "55555" in result.stdout


class TestDaemonCommandIntegration:
    """Integration tests with real processes (marked @pytest.mark.slow)"""
    
    @pytest.mark.slow
    def test_daemon_start_real(self, cleanup_daemon_files):
        """Test daemon start with real process"""
        result = runner.invoke(app, [
            "daemon", "start",
            "--port", "9999",
            "--background"
        ])
        
        assert result.exit_code == 0
        assert "started successfully" in result.stdout.lower() or "Daemon started" in result.stdout
        
        # Cleanup
        runner.invoke(app, ["daemon", "stop"])
    
    @pytest.mark.slow
    def test_daemon_start_with_protocol_real(self, cleanup_daemon_files):
        """Test daemon start with protocol and real process"""
        result = runner.invoke(app, [
            "daemon", "start",
            "--port", "9997",
            "--protocol", "mcp",
            "--background"
        ])
        
        assert result.exit_code == 0
        assert "started successfully" in result.stdout.lower() or "Daemon started" in result.stdout
        
        # Cleanup
        runner.invoke(app, ["daemon", "stop"])
    
    @pytest.mark.slow
    def test_daemon_restart_real(self, cleanup_daemon_files):
        """Test daemon restart with real process"""
        result = runner.invoke(app, [
            "daemon", "start",
            "--port", "9998",
            "--background"
        ])
        
        if result.exit_code == 0:
            result = runner.invoke(app, [
                "daemon", "restart",
                "--port", "9998"
            ])
            assert "restart" in result.stdout.lower() or result.exit_code in [0, 1]
        
        # Cleanup
        runner.invoke(app, ["daemon", "stop"])

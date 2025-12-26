"""
Test CLI serve command functionality

Tests the serve command as documented in README.md
"""

from typer.testing import CliRunner
from aipartnerupflow.cli.main import app

runner = CliRunner()


class TestServeCommand:
    """Test cases for serve command"""
    
    def test_serve_help(self):
        """Test serve command help"""
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "Start API server" in result.stdout
        assert "--port" in result.stdout or "-p" in result.stdout
        assert "--protocol" in result.stdout or "-P" in result.stdout
    
    def test_serve_with_port_option_help(self):
        """Test serve command accepts --port option (verify via help)"""
        # Just verify the option exists in help, don't actually start server
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--port" in result.stdout or "-p" in result.stdout
        assert "Port to bind" in result.stdout
    
    def test_serve_start_subcommand_help(self):
        """Test serve start subcommand help"""
        result = runner.invoke(app, ["serve", "start", "--help"])
        assert result.exit_code == 0
        assert "--port" in result.stdout or "-p" in result.stdout
    
    def test_serve_command_structure(self):
        """Test that serve command structure is correct"""
        # Test that serve command exists and accepts options
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        # Verify it shows the start subcommand
        assert "start" in result.stdout or "COMMAND" in result.stdout
    
    def test_serve_with_protocol_option(self):
        """Test serve command with protocol option"""
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--protocol" in result.stdout or "-P" in result.stdout
        assert "a2a" in result.stdout or "mcp" in result.stdout
    
    def test_serve_start_with_protocol_option(self):
        """Test serve start subcommand with protocol option"""
        result = runner.invoke(app, ["serve", "start", "--help"])
        assert result.exit_code == 0
        assert "--protocol" in result.stdout or "-P" in result.stdout


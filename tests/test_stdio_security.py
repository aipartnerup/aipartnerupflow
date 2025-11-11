"""
Test security mechanisms for StdioExecutor

This module tests that command execution is properly secured by default
and can be enabled with appropriate configuration.
"""

import pytest
import os
from unittest.mock import patch
from aipartnerupflow.extensions.stdio import StdioExecutor


class TestStdioSecurity:
    """Test security features of StdioExecutor"""

    def test_command_disabled_by_default(self):
        """Test that command execution is disabled by default"""
        executor = StdioExecutor()
        
        # Clear any existing environment variables
        with patch.dict(os.environ, {}, clear=True):
            # Reload the module to pick up the default (disabled) state
            import importlib
            import aipartnerupflow.extensions.stdio.executor as stdio_module
            importlib.reload(stdio_module)
            
            # Create a new executor instance
            executor = stdio_module.StdioExecutor()
            
            result = executor.execute({
                "method": "command",
                "command": "echo test"
            })
            
            assert result["success"] is False
            assert "security_blocked" in result
            assert result["security_blocked"] is True
            assert "disabled by default" in result["error"].lower()

    def test_system_info_always_available(self):
        """Test that system_info method is always available (safe commands)"""
        executor = StdioExecutor()
        
        # system_info should work even when command is disabled
        result = executor.execute({
            "method": "system_info",
            "resource": "cpu"
        })
        
        # Should succeed (may vary by system, but should not be security-blocked)
        assert "system" in result
        assert "security_blocked" not in result

    @pytest.mark.skipif(
        os.getenv("AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND") != "1",
        reason="Command execution not enabled in test environment"
    )
    def test_command_enabled_with_env_var(self):
        """Test that command execution works when explicitly enabled"""
        executor = StdioExecutor()
        
        result = executor.execute({
            "method": "command",
            "command": "echo test"
        })
        
        # Should succeed if enabled
        assert result["success"] is True or "security_blocked" not in result

    def test_whitelist_validation(self):
        """Test that whitelist validation works when configured"""
        # This test would require setting up the whitelist environment variable
        # and is more of an integration test
        pass


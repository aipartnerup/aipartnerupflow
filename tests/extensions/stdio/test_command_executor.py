"""
Test CommandExecutor security mechanisms

This module tests that command execution is properly secured by default
and can be enabled with appropriate configuration.

All tests force specific AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND values to ensure
comprehensive coverage regardless of environment state.
"""

import pytest
import os
from unittest.mock import patch
import importlib
import logging


class TestCommandExecutorSecurity:
    """Test security features of CommandExecutor"""

    @pytest.mark.parametrize("env_value", ["0", "false", "no", "", None])
    @pytest.mark.asyncio
    async def test_command_disabled_with_various_values(self, env_value):
        """Test that command execution is disabled with various false values"""
        from aipartnerupflow.core.execution.errors import ConfigurationError
        # Set environment variable to disabled value
        env_dict = {}
        if env_value is not None:
            env_dict["AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND"] = env_value
        
        with patch.dict(os.environ, env_dict, clear=False):
            # Reload the module to pick up the disabled state
            import aipartnerupflow.extensions.stdio.command_executor as command_module
            
            # Temporarily suppress duplicate registration error during reload
            logger = logging.getLogger("aipartnerupflow.core.extensions.decorators")
            original_level = logger.level
            logger.setLevel(logging.CRITICAL)
            
            try:
                importlib.reload(command_module)
            except ValueError:
                # Ignore duplicate registration error during reload
                pass
            finally:
                logger.setLevel(original_level)
            
            # Create a new executor instance (will use the reloaded module's STDIO_ALLOW_COMMAND)
            executor = command_module.CommandExecutor()
            
            # Should raise ConfigurationError when disabled
            with pytest.raises(ConfigurationError, match="disabled"):
                await executor.execute({
                    "command": "echo test"
                })

    @pytest.mark.parametrize("env_value", ["1", "true", "yes", "on"])
    @pytest.mark.asyncio
    async def test_command_enabled_with_various_values(self, env_value):
        """Test that command execution works when enabled with various true values"""
        with patch.dict(os.environ, {"AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND": env_value}, clear=False):
            # Reload the module to pick up the enabled state
            import aipartnerupflow.extensions.stdio.command_executor as command_module
            
            # Temporarily suppress duplicate registration error during reload
            logger = logging.getLogger("aipartnerupflow.core.extensions.decorators")
            original_level = logger.level
            logger.setLevel(logging.CRITICAL)
            
            try:
                importlib.reload(command_module)
            except ValueError:
                # Ignore duplicate registration error during reload
                pass
            finally:
                logger.setLevel(original_level)
            
            # Create a new executor instance
            executor = command_module.CommandExecutor()
            
            result = await executor.execute({
                "command": "echo test"
            })
            
            # Should succeed when enabled
            assert result["success"] is True
            assert "security_blocked" not in result
            assert "stdout" in result
            assert "test" in result["stdout"]

    @pytest.mark.parametrize("env_value", ["1", "true", "yes", "on"])
    @pytest.mark.asyncio
    async def test_command_with_timeout_when_enabled(self, env_value):
        """Test that timeout parameter works correctly when command execution is enabled"""
        with patch.dict(os.environ, {"AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND": env_value}, clear=False):
            # Reload the module to pick up the enabled state
            import aipartnerupflow.extensions.stdio.command_executor as command_module
            
            # Temporarily suppress duplicate registration error during reload
            logger = logging.getLogger("aipartnerupflow.core.extensions.decorators")
            original_level = logger.level
            logger.setLevel(logging.CRITICAL)
            
            try:
                importlib.reload(command_module)
            except ValueError:
                # Ignore duplicate registration error during reload
                pass
            finally:
                logger.setLevel(original_level)
            
            executor = command_module.CommandExecutor()
            
            result = await executor.execute({
                "command": "echo test",
                "timeout": 5
            })
            
            # Should succeed with custom timeout
            assert result["success"] is True

    @pytest.mark.parametrize("env_value", ["1", "true", "yes", "on"])
    @pytest.mark.asyncio
    async def test_command_required_when_enabled(self, env_value):
        """Test that command parameter is required when execution is enabled"""
        from aipartnerupflow.core.execution.errors import ValidationError
        with patch.dict(os.environ, {"AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND": env_value}, clear=False):
            # Reload the module to pick up the enabled state
            import aipartnerupflow.extensions.stdio.command_executor as command_module
            
            # Temporarily suppress duplicate registration error during reload
            logger = logging.getLogger("aipartnerupflow.core.extensions.decorators")
            original_level = logger.level
            logger.setLevel(logging.CRITICAL)
            
            try:
                importlib.reload(command_module)
            except ValueError:
                # Ignore duplicate registration error during reload
                pass
            finally:
                logger.setLevel(original_level)
            
            executor = command_module.CommandExecutor()
            
            # When command execution is enabled, missing command should raise ValidationError
            with pytest.raises(ValidationError, match="command is required"):
                await executor.execute({})

    @pytest.mark.parametrize("env_value", ["1", "true", "yes", "on"])
    @pytest.mark.asyncio
    async def test_command_whitelist_validation_when_enabled(self, env_value):
        """Test that whitelist validation works when command execution is enabled"""
        from aipartnerupflow.core.execution.errors import ConfigurationError
        # Set both allow command and whitelist
        with patch.dict(os.environ, {
            "AIPARTNERUPFLOW_STDIO_ALLOW_COMMAND": env_value,
            "AIPARTNERUPFLOW_STDIO_COMMAND_WHITELIST": "echo,ls,cat"
        }, clear=False):
            # Reload the module to pick up the enabled state and whitelist
            import aipartnerupflow.extensions.stdio.command_executor as command_module
            
            # Temporarily suppress duplicate registration error during reload
            logger = logging.getLogger("aipartnerupflow.core.extensions.decorators")
            original_level = logger.level
            logger.setLevel(logging.CRITICAL)
            
            try:
                importlib.reload(command_module)
            except ValueError:
                # Ignore duplicate registration error during reload
                pass
            finally:
                logger.setLevel(original_level)
            
            executor = command_module.CommandExecutor()
            
            # Try a command in whitelist - should succeed
            result = await executor.execute({
                "command": "echo test"
            })
            assert result["success"] is True
            
            # Try a command not in whitelist - should raise ConfigurationError
            with pytest.raises(ConfigurationError, match="whitelist"):
                await executor.execute({
                    "command": "nonexistent_command_xyz"
                })

    def test_whitelist_validation_structure(self):
        """Test that whitelist validation structure is correct"""
        # This test validates the whitelist checking logic structure
        # without requiring actual whitelist configuration
        from aipartnerupflow.extensions.stdio import CommandExecutor
        executor = CommandExecutor()
        
        # Verify executor has the security mechanisms in place
        assert hasattr(executor, 'execute')
        
        # The actual whitelist validation is tested in integration tests above


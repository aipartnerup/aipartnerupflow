"""
Test SshExecutor

Tests for SSH remote execution functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from aipartnerupflow.extensions.ssh.ssh_executor import SshExecutor, ASYNCSSH_AVAILABLE


class TestSshExecutor:
    """Test SshExecutor functionality"""
    
    @pytest.mark.skipif(not ASYNCSSH_AVAILABLE, reason="asyncssh not installed")
    @pytest.mark.asyncio
    async def test_execute_command_with_key_file(self):
        """Test executing command with key file authentication"""
        executor = SshExecutor()
        
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.exit_status = 0
        
        with patch("os.path.exists", return_value=True), \
             patch("os.stat") as mock_stat, \
             patch("asyncssh.connect") as mock_connect:
            # Mock stat to return valid permissions
            mock_stat_result = MagicMock()
            mock_stat_result.st_mode = 0o600
            mock_stat.return_value = mock_stat_result
            
            mock_conn = AsyncMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value = mock_conn
            
            result = await executor.execute({
                "host": "example.com",
                "username": "user",
                "key_file": "/path/to/key",
                "command": "ls -la"
            })
            
            assert result["success"] is True
            assert result["stdout"] == "output"
            assert result["return_code"] == 0
    
    @pytest.mark.skipif(not ASYNCSSH_AVAILABLE, reason="asyncssh not installed")
    @pytest.mark.asyncio
    async def test_execute_command_with_password(self):
        """Test executing command with password authentication"""
        executor = SshExecutor()
        
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.exit_status = 0
        
        with patch("asyncssh.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value = mock_conn
            
            result = await executor.execute({
                "host": "example.com",
                "username": "user",
                "password": "pass",
                "command": "ls -la"
            })
            
            assert result["success"] is True
            assert result["return_code"] == 0
    
    @pytest.mark.asyncio
    async def test_execute_missing_host(self):
        """Test error when host is missing"""
        from aipartnerupflow.core.execution.errors import ValidationError
        executor = SshExecutor()
        
        with pytest.raises(ValidationError, match="host is required"):
            await executor.execute({
                "username": "user",
                "command": "ls"
            })
    
    @pytest.mark.asyncio
    async def test_execute_missing_username(self):
        """Test error when username is missing"""
        from aipartnerupflow.core.execution.errors import ValidationError
        executor = SshExecutor()
        
        with pytest.raises(ValidationError, match="username is required"):
            await executor.execute({
                "host": "example.com",
                "command": "ls"
            })
    
    @pytest.mark.asyncio
    async def test_execute_missing_command(self):
        """Test error when command is missing"""
        from aipartnerupflow.core.execution.errors import ValidationError
        executor = SshExecutor()
        
        with pytest.raises(ValidationError, match="command is required"):
            await executor.execute({
                "host": "example.com",
                "username": "user"
            })
    
    @pytest.mark.asyncio
    async def test_execute_missing_auth(self):
        """Test error when neither password nor key_file is provided"""
        from aipartnerupflow.core.execution.errors import ValidationError
        # Mock ASYNCSSH_AVAILABLE = True to test authentication validation logic
        with patch("aipartnerupflow.extensions.ssh.ssh_executor.ASYNCSSH_AVAILABLE", True):
            executor = SshExecutor()
            
            with pytest.raises(ValidationError, match="Either password or key_file"):
                await executor.execute({
                    "host": "example.com",
                    "username": "user",
                    "command": "ls"
                })
    
    @pytest.mark.asyncio
    async def test_execute_asyncssh_not_available(self):
        """Test behavior when asyncssh is not installed"""
        from aipartnerupflow.core.execution.errors import ConfigurationError
        with patch("aipartnerupflow.extensions.ssh.ssh_executor.ASYNCSSH_AVAILABLE", False):
            executor = SshExecutor()
            with pytest.raises(ConfigurationError, match="asyncssh is not installed"):
                await executor.execute({
                    "host": "example.com",
                    "username": "user",
                    "command": "ls"
                })
    
    @pytest.mark.skipif(not ASYNCSSH_AVAILABLE, reason="asyncssh not installed")
    @pytest.mark.asyncio
    async def test_execute_command_with_env_vars(self):
        """Test executing command with environment variables"""
        executor = SshExecutor()
        
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.exit_status = 0
        
        with patch("os.path.exists", return_value=True), \
             patch("os.stat") as mock_stat, \
             patch("asyncssh.connect") as mock_connect:
            # Mock stat to return valid permissions
            mock_stat_result = MagicMock()
            mock_stat_result.st_mode = 0o600
            mock_stat.return_value = mock_stat_result
            
            mock_conn = AsyncMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value = mock_conn
            
            result = await executor.execute({
                "host": "example.com",
                "username": "user",
                "key_file": "/path/to/key",
                "command": "echo $TEST_VAR",
                "env": {"TEST_VAR": "test_value"}
            })
            
            assert result["success"] is True
            # Verify command was executed with env vars
            call_args = mock_conn.run.call_args[0]
            assert "TEST_VAR=test_value" in call_args[0] or "test_value" in str(call_args)
    
    @pytest.mark.skipif(not ASYNCSSH_AVAILABLE, reason="asyncssh not installed")
    @pytest.mark.asyncio
    async def test_execute_command_with_custom_port(self):
        """Test executing command with custom SSH port"""
        executor = SshExecutor()
        
        mock_result = MagicMock()
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_result.exit_status = 0
        
        with patch("os.path.exists", return_value=True), \
             patch("os.stat") as mock_stat, \
             patch("asyncssh.connect") as mock_connect:
            # Mock stat to return valid permissions
            mock_stat_result = MagicMock()
            mock_stat_result.st_mode = 0o600
            mock_stat.return_value = mock_stat_result
            
            mock_conn = AsyncMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value = mock_conn
            
            result = await executor.execute({
                "host": "example.com",
                "port": 2222,
                "username": "user",
                "key_file": "/path/to/key",
                "command": "ls"
            })
            
            assert result["success"] is True
            # Verify port was used in connection
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["port"] == 2222
    
    @pytest.mark.skipif(not ASYNCSSH_AVAILABLE, reason="asyncssh not installed")
    @pytest.mark.asyncio
    async def test_execute_command_failure(self):
        """Test handling command execution failure"""
        executor = SshExecutor()
        
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.stderr = "Command failed"
        mock_result.exit_status = 1
        
        with patch("os.path.exists", return_value=True), \
             patch("os.stat") as mock_stat, \
             patch("asyncssh.connect") as mock_connect:
            # Mock stat to return valid permissions
            mock_stat_result = MagicMock()
            mock_stat_result.st_mode = 0o600
            mock_stat.return_value = mock_stat_result
            
            mock_conn = AsyncMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_conn.run = AsyncMock(return_value=mock_result)
            mock_connect.return_value = mock_conn
            
            result = await executor.execute({
                "host": "example.com",
                "username": "user",
                "key_file": "/path/to/key",
                "command": "invalid-command"
            })
            
            assert result["success"] is False
            assert result["return_code"] == 1
            assert result["stderr"] == "Command failed"
    
    @pytest.mark.skipif(not ASYNCSSH_AVAILABLE, reason="asyncssh not installed")
    @pytest.mark.asyncio
    async def test_execute_command_timeout(self):
        """Test handling command timeout"""
        executor = SshExecutor()
        
        with patch("os.path.exists", return_value=True), \
             patch("os.stat") as mock_stat, \
             patch("asyncssh.connect") as mock_connect, \
             patch("asyncio.wait_for") as mock_wait:
            # Mock stat to return valid permissions
            mock_stat_result = MagicMock()
            mock_stat_result.st_mode = 0o600
            mock_stat.return_value = mock_stat_result
            
            mock_conn = AsyncMock()
            mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_connect.return_value = mock_conn
            mock_wait.side_effect = asyncio.TimeoutError()
            
            # asyncio.TimeoutError should propagate
            with pytest.raises(asyncio.TimeoutError):
                await executor.execute({
                    "host": "example.com",
                    "username": "user",
                    "key_file": "/path/to/key",
                    "command": "sleep 100",
                    "timeout": 5
                })
    
    @pytest.mark.skipif(not ASYNCSSH_AVAILABLE, reason="asyncssh not installed")
    @pytest.mark.asyncio
    async def test_execute_ssh_connection_error(self):
        """Test handling SSH connection errors"""
        executor = SshExecutor()
        
        # Since asyncssh.Error is hard to construct, we'll test the error handling
        # by making the connection raise an exception that will propagate
        with patch("os.path.exists", return_value=True), \
             patch("os.stat") as mock_stat, \
             patch("asyncssh.connect") as mock_connect:
            # Mock stat to return valid permissions
            mock_stat_result = MagicMock()
            mock_stat_result.st_mode = 0o600
            mock_stat.return_value = mock_stat_result
            
            # Create a connection error - exceptions will propagate
            connection_error = Exception("Connection refused")
            mock_connect.side_effect = connection_error
            
            # Connection exceptions should propagate
            with pytest.raises(Exception, match="Connection refused"):
                await executor.execute({
                    "host": "example.com",
                    "username": "user",
                    "key_file": "/path/to/key",
                    "command": "ls"
                })
    
    @pytest.mark.skipif(not ASYNCSSH_AVAILABLE, reason="asyncssh not installed")
    @pytest.mark.asyncio
    async def test_execute_cancellation_before_connection(self):
        """Test cancellation before SSH connection"""
        executor = SshExecutor()
        executor.cancellation_checker = lambda: True
        
        with patch("os.path.exists", return_value=True), \
             patch("os.stat") as mock_stat:
            # Mock stat to return valid permissions
            mock_stat_result = MagicMock()
            mock_stat_result.st_mode = 0o600
            mock_stat.return_value = mock_stat_result
            
            result = await executor.execute({
                "host": "example.com",
                "username": "user",
                "key_file": "/path/to/key",
                "command": "ls"
            })
            
            assert result["success"] is False
            assert "cancelled" in result["error"].lower()
    
    @pytest.mark.skipif(not ASYNCSSH_AVAILABLE, reason="asyncssh not installed")
    @pytest.mark.asyncio
    async def test_validate_key_file_permissions(self):
        """Test key file permission validation"""
        executor = SshExecutor()
        
        import tempfile
        import os
        
        # Create a temporary key file with wrong permissions
        with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
            f.write("test key")
            key_file = f.name
        
        try:
            # Set permissions to 644 (too permissive)
            os.chmod(key_file, 0o644)
            
            with patch("os.path.exists", return_value=True), \
                 patch("os.stat") as mock_stat, \
                 patch("asyncssh.connect") as mock_connect:
                mock_stat_result = MagicMock()
                mock_stat_result.st_mode = 0o644
                mock_stat.return_value = mock_stat_result
                
                # Mock successful connection
                mock_result = MagicMock()
                mock_result.stdout = "output"
                mock_result.stderr = ""
                mock_result.exit_status = 0
                
                mock_conn = AsyncMock()
                mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
                mock_conn.__aexit__ = AsyncMock(return_value=None)
                mock_conn.run = AsyncMock(return_value=mock_result)
                mock_connect.return_value = mock_conn
                
                result = await executor.execute({
                    "host": "example.com",
                    "username": "user",
                    "key_file": key_file,
                    "command": "ls"
                })
                
                # Should still work but log warning
                # The validation is a warning, not an error
                assert result["success"] is True
        finally:
            if os.path.exists(key_file):
                os.unlink(key_file)
    
    @pytest.mark.asyncio
    async def test_get_input_schema(self):
        """Test input schema generation"""
        executor = SshExecutor()
        schema = executor.get_input_schema()
        
        assert schema["type"] == "object"
        assert "host" in schema["required"]
        assert "username" in schema["required"]
        assert "command" in schema["required"]
        assert "port" in schema["properties"]
        assert "env" in schema["properties"]


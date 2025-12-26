"""
Test DockerExecutor

Tests for Docker container execution functionality.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from aipartnerupflow.extensions.docker.docker_executor import DockerExecutor, DOCKER_AVAILABLE


class TestDockerExecutor:
    """Test DockerExecutor functionality"""
    
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not installed")
    @pytest.mark.asyncio
    async def test_execute_command_in_container(self):
        """Test executing command in Docker container"""
        executor = DockerExecutor()
        
        mock_container = MagicMock()
        mock_container.id = "container-123"
        mock_container.logs.return_value = b"output"
        mock_container.wait.return_value = {"StatusCode": 0}
        
        mock_client = MagicMock()
        mock_client.containers.create.return_value = mock_container
        
        executor._client = mock_client
        
        result = await executor.execute({
            "image": "python:3.11",
            "command": "python -c 'print(\"Hello\")'"
        })
        
        assert result["success"] is True
        assert result["container_id"] == "container-123"
        mock_client.containers.create.assert_called_once()
        mock_container.start.assert_called_once()
    
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not installed")
    @pytest.mark.asyncio
    async def test_execute_missing_image(self):
        """Test error when image is missing"""
        from aipartnerupflow.core.execution.errors import ValidationError
        executor = DockerExecutor()
        
        with pytest.raises(ValidationError, match="image is required"):
            await executor.execute({
                "command": "ls"
            })

    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not installed")
    @pytest.mark.asyncio
    async def test_execute_missing_command(self):
        """Test error when command is missing"""
        from aipartnerupflow.core.execution.errors import ValidationError
        executor = DockerExecutor()
        
        with pytest.raises(ValidationError, match="command is required"):
            await executor.execute({
                "image": "python:3.11"
            })
    
    @pytest.mark.asyncio
    async def test_execute_docker_not_available(self):
        """Test behavior when docker is not installed"""
        from aipartnerupflow.core.execution.errors import ConfigurationError
        with patch("aipartnerupflow.extensions.docker.docker_executor.DOCKER_AVAILABLE", False):
            executor = DockerExecutor()
            with pytest.raises(ConfigurationError, match="docker is not installed"):
                await executor.execute({
                    "image": "python:3.11",
                    "command": "ls"
                })
    
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not installed")
    @pytest.mark.asyncio
    async def test_execute_with_env_vars(self):
        """Test executing command with environment variables"""
        executor = DockerExecutor()
        
        mock_container = MagicMock()
        mock_container.id = "container-123"
        mock_container.logs.return_value = b"output"
        mock_container.wait.return_value = {"StatusCode": 0}
        
        mock_client = MagicMock()
        mock_client.containers.create.return_value = mock_container
        
        executor._client = mock_client
        
        result = await executor.execute({
            "image": "python:3.11",
            "command": "python -c 'import os; print(os.getenv(\"TEST_VAR\"))'",
            "env": {"TEST_VAR": "test_value"}
        })
        
        assert result["success"] is True
        call_kwargs = mock_client.containers.create.call_args[1]
        assert call_kwargs["environment"] == {"TEST_VAR": "test_value"}
    
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not installed")
    @pytest.mark.asyncio
    async def test_execute_with_volumes(self):
        """Test executing command with volume mounts"""
        executor = DockerExecutor()
        
        mock_container = MagicMock()
        mock_container.id = "container-123"
        mock_container.logs.return_value = b"output"
        mock_container.wait.return_value = {"StatusCode": 0}
        
        mock_client = MagicMock()
        mock_client.containers.create.return_value = mock_container
        
        executor._client = mock_client
        
        result = await executor.execute({
            "image": "python:3.11",
            "command": "ls /data",
            "volumes": {"/host/data": "/data"}
        })
        
        assert result["success"] is True
        call_kwargs = mock_client.containers.create.call_args[1]
        assert "/host/data:/data" in call_kwargs["volumes"]
    
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not installed")
    @pytest.mark.asyncio
    async def test_execute_with_resource_limits(self):
        """Test executing command with resource limits"""
        executor = DockerExecutor()
        
        mock_container = MagicMock()
        mock_container.id = "container-123"
        mock_container.logs.return_value = b"output"
        mock_container.wait.return_value = {"StatusCode": 0}
        
        mock_client = MagicMock()
        mock_client.containers.create.return_value = mock_container
        
        executor._client = mock_client
        
        result = await executor.execute({
            "image": "python:3.11",
            "command": "python -c 'print(\"test\")'",
            "resources": {"cpu": "1.0", "memory": "512m"}
        })
        
        assert result["success"] is True
        call_kwargs = mock_client.containers.create.call_args[1]
        assert call_kwargs["mem_limit"] == "512m"
        assert call_kwargs["cpu_quota"] == 100000  # 1.0 * 100000
    
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not installed")
    @pytest.mark.asyncio
    async def test_execute_container_failure(self):
        """Test handling container execution failure"""
        executor = DockerExecutor()
        
        mock_container = MagicMock()
        mock_container.id = "container-123"
        mock_container.logs.return_value = b"error output"
        mock_container.wait.return_value = {"StatusCode": 1}
        
        mock_client = MagicMock()
        mock_client.containers.create.return_value = mock_container
        
        executor._client = mock_client
        
        result = await executor.execute({
            "image": "python:3.11",
            "command": "python -c 'exit(1)'"
        })
        
        assert result["success"] is False
        assert result["exit_code"] == 1
    
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not installed")
    @pytest.mark.asyncio
    async def test_execute_container_timeout(self):
        """Test handling container timeout"""
        executor = DockerExecutor()
        
        mock_container = MagicMock()
        mock_container.id = "container-123"
        mock_container.logs.return_value = b"timeout"
        
        mock_client = MagicMock()
        mock_client.containers.create.return_value = mock_container
        
        executor._client = mock_client
        
        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()
            
            result = await executor.execute({
                "image": "python:3.11",
                "command": "sleep 100",
                "timeout": 5
            })
            
            assert result["success"] is False
            assert result["exit_code"] == -1
            mock_container.stop.assert_called_once()
    
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not installed")
    @pytest.mark.asyncio
    async def test_execute_image_not_found(self):
        """Test handling image not found error"""
        executor = DockerExecutor()
        
        import docker
        mock_client = MagicMock()
        mock_client.containers.create.side_effect = docker.errors.ImageNotFound("Image not found")
        
        executor._client = mock_client
        
        # ImageNotFound exception should propagate
        with pytest.raises(docker.errors.ImageNotFound):
            await executor.execute({
                "image": "nonexistent:latest",
                "command": "ls"
            })
    
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not installed")
    @pytest.mark.asyncio
    async def test_execute_keep_container(self):
        """Test keeping container after execution"""
        executor = DockerExecutor()
        
        mock_container = MagicMock()
        mock_container.id = "container-123"
        mock_container.logs.return_value = b"output"
        mock_container.wait.return_value = {"StatusCode": 0}
        
        mock_client = MagicMock()
        mock_client.containers.create.return_value = mock_container
        
        executor._client = mock_client
        
        result = await executor.execute({
            "image": "python:3.11",
            "command": "python -c 'print(\"test\")'",
            "remove": False
        })
        
        assert result["success"] is True
        mock_container.remove.assert_not_called()
    
    @pytest.mark.skipif(not DOCKER_AVAILABLE, reason="docker not installed")
    @pytest.mark.asyncio
    async def test_execute_cancellation_before_start(self):
        """Test cancellation before container start"""
        executor = DockerExecutor()
        # Set cancellation checker to return True after container creation
        cancelled = [False]
        def check_cancellation():
            if not cancelled[0]:
                cancelled[0] = True
                return False  # First check (before creation) returns False
            return True  # Second check (after creation) returns True
        
        executor.cancellation_checker = check_cancellation
        
        mock_container = MagicMock()
        mock_container.id = "container-123"
        
        mock_client = MagicMock()
        mock_client.containers.create.return_value = mock_container
        
        executor._client = mock_client
        
        result = await executor.execute({
            "image": "python:3.11",
            "command": "python -c 'print(\"test\")'"
        })
        
        assert result["success"] is False
        assert "cancelled" in result["error"].lower()
        # Container was created, so remove should be called
        mock_container.remove.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_input_schema(self):
        """Test input schema generation"""
        executor = DockerExecutor()
        schema = executor.get_input_schema()
        
        assert schema["type"] == "object"
        assert "image" in schema["required"]
        assert "command" in schema["required"]
        assert "env" in schema["properties"]
        assert "volumes" in schema["properties"]
        assert "resources" in schema["properties"]


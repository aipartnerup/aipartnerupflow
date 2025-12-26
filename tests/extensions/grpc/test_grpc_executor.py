"""
Test GrpcExecutor

Tests for gRPC service execution functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from aipartnerupflow.extensions.grpc.grpc_executor import GrpcExecutor, GRPC_AVAILABLE


class TestGrpcExecutor:
    """Test GrpcExecutor functionality"""
    
    @pytest.mark.skipif(not GRPC_AVAILABLE, reason="grpcio not installed")
    @pytest.mark.asyncio
    async def test_execute_grpc_call(self):
        """Test executing a gRPC call"""
        executor = GrpcExecutor()
        
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_channel_instance = AsyncMock()
            mock_channel.return_value = mock_channel_instance
            mock_channel_instance.__aenter__ = AsyncMock(return_value=mock_channel_instance)
            mock_channel_instance.__aexit__ = AsyncMock(return_value=None)
            mock_channel_instance.close = AsyncMock()
            
            result = await executor.execute({
                "server": "localhost:50051",
                "service": "Greeter",
                "method": "SayHello",
                "request": {"name": "World"}
            })
            
            assert result["success"] is True
            assert result["server"] == "localhost:50051"
            assert result["service"] == "Greeter"
            assert result["method"] == "SayHello"
    
    @pytest.mark.skipif(not GRPC_AVAILABLE, reason="grpcio not installed")
    @pytest.mark.asyncio
    async def test_execute_missing_server(self):
        """Test error when server is missing"""
        from aipartnerupflow.core.execution.errors import ValidationError
        executor = GrpcExecutor()
        
        with pytest.raises(ValidationError, match="server is required"):
            await executor.execute({
                "service": "Greeter",
                "method": "SayHello",
                "request": {}
            })
    
    @pytest.mark.skipif(not GRPC_AVAILABLE, reason="grpcio not installed")
    @pytest.mark.asyncio
    async def test_execute_missing_service(self):
        """Test error when service is missing"""
        from aipartnerupflow.core.execution.errors import ValidationError
        executor = GrpcExecutor()
        
        with pytest.raises(ValidationError, match="service is required"):
            await executor.execute({
                "server": "localhost:50051",
                "method": "SayHello",
                "request": {}
            })
    
    @pytest.mark.skipif(not GRPC_AVAILABLE, reason="grpcio not installed")
    @pytest.mark.asyncio
    async def test_execute_missing_method(self):
        """Test error when method is missing"""
        from aipartnerupflow.core.execution.errors import ValidationError
        executor = GrpcExecutor()
        
        with pytest.raises(ValidationError, match="method is required"):
            await executor.execute({
                "server": "localhost:50051",
                "service": "Greeter",
                "request": {}
            })
    
    @pytest.mark.asyncio
    async def test_execute_grpc_not_available(self):
        """Test behavior when grpcio is not installed"""
        from aipartnerupflow.core.execution.errors import ConfigurationError
        with patch("aipartnerupflow.extensions.grpc.grpc_executor.GRPC_AVAILABLE", False):
            executor = GrpcExecutor()
            with pytest.raises(ConfigurationError, match="grpcio is not installed"):
                await executor.execute({
                    "server": "localhost:50051",
                    "service": "Greeter",
                    "method": "SayHello",
                    "request": {}
                })
    
    @pytest.mark.skipif(not GRPC_AVAILABLE, reason="grpcio not installed")
    @pytest.mark.asyncio
    async def test_execute_grpc_call_with_metadata(self):
        """Test executing gRPC call with metadata"""
        executor = GrpcExecutor()
        
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_channel_instance = AsyncMock()
            mock_channel.return_value = mock_channel_instance
            mock_channel_instance.__aenter__ = AsyncMock(return_value=mock_channel_instance)
            mock_channel_instance.__aexit__ = AsyncMock(return_value=None)
            mock_channel_instance.close = AsyncMock()
            
            result = await executor.execute({
                "server": "localhost:50051",
                "service": "Greeter",
                "method": "SayHello",
                "request": {"name": "World"},
                "metadata": {"authorization": "Bearer token"}
            })
            
            assert result["success"] is True
            assert "metadata" in result
    
    @pytest.mark.skipif(not GRPC_AVAILABLE, reason="grpcio not installed")
    @pytest.mark.asyncio
    async def test_execute_grpc_call_with_timeout(self):
        """Test executing gRPC call with custom timeout"""
        executor = GrpcExecutor()
        
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_channel_instance = AsyncMock()
            mock_channel.return_value = mock_channel_instance
            mock_channel_instance.__aenter__ = AsyncMock(return_value=mock_channel_instance)
            mock_channel_instance.__aexit__ = AsyncMock(return_value=None)
            mock_channel_instance.close = AsyncMock()
            
            result = await executor.execute({
                "server": "localhost:50051",
                "service": "Greeter",
                "method": "SayHello",
                "request": {"name": "World"},
                "timeout": 60.0
            })
            
            assert result["success"] is True
    
    @pytest.mark.skipif(not GRPC_AVAILABLE, reason="grpcio not installed")
    @pytest.mark.asyncio
    async def test_execute_grpc_rpc_error(self):
        """Test handling gRPC RPC errors"""
        executor = GrpcExecutor()
        
        import grpc
        mock_error = grpc.RpcError()
        mock_error.code = MagicMock(return_value=grpc.StatusCode.NOT_FOUND)
        
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_channel_instance = AsyncMock()
            mock_channel.return_value = mock_channel_instance
            mock_channel_instance.__aenter__ = AsyncMock(return_value=mock_channel_instance)
            mock_channel_instance.__aexit__ = AsyncMock(return_value=None)
            mock_channel_instance.close = AsyncMock()
            
            # Simulate RPC error by patching asyncio.sleep to raise error
            # RpcError should propagate
            with patch("asyncio.sleep", side_effect=mock_error):
                with pytest.raises(grpc.RpcError):
                    await executor.execute({
                        "server": "localhost:50051",
                        "service": "Greeter",
                        "method": "SayHello",
                        "request": {"name": "World"}
                    })
    
    @pytest.mark.skipif(not GRPC_AVAILABLE, reason="grpcio not installed")
    @pytest.mark.asyncio
    async def test_execute_grpc_cancellation_before_call(self):
        """Test cancellation before gRPC call"""
        executor = GrpcExecutor()
        executor.cancellation_checker = lambda: True
        
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_channel_instance = AsyncMock()
            mock_channel.return_value = mock_channel_instance
            mock_channel_instance.__aenter__ = AsyncMock(return_value=mock_channel_instance)
            mock_channel_instance.__aexit__ = AsyncMock(return_value=None)
            mock_channel_instance.close = AsyncMock()
            
            result = await executor.execute({
                "server": "localhost:50051",
                "service": "Greeter",
                "method": "SayHello",
                "request": {"name": "World"}
            })
            
            assert result["success"] is False
            assert "cancelled" in result["error"].lower()
    
    @pytest.mark.skipif(not GRPC_AVAILABLE, reason="grpcio not installed")
    @pytest.mark.asyncio
    async def test_execute_grpc_cancellation_after_call(self):
        """Test cancellation after gRPC call"""
        executor = GrpcExecutor()
        cancelled = [False]
        
        def check_cancellation():
            if not cancelled[0]:
                cancelled[0] = True
                return False
            return True
        
        executor.cancellation_checker = check_cancellation
        
        with patch("grpc.aio.insecure_channel") as mock_channel:
            mock_channel_instance = AsyncMock()
            mock_channel.return_value = mock_channel_instance
            mock_channel_instance.__aenter__ = AsyncMock(return_value=mock_channel_instance)
            mock_channel_instance.__aexit__ = AsyncMock(return_value=None)
            mock_channel_instance.close = AsyncMock()
            
            result = await executor.execute({
                "server": "localhost:50051",
                "service": "Greeter",
                "method": "SayHello",
                "request": {"name": "World"}
            })
            
            assert result["success"] is False
            assert "cancelled" in result["error"].lower()
    
    @pytest.mark.skipif(not GRPC_AVAILABLE, reason="grpcio not installed")
    @pytest.mark.asyncio
    async def test_execute_grpc_different_services(self):
        """Test calling different gRPC services"""
        executor = GrpcExecutor()
        
        services = ["Greeter", "Calculator", "UserService"]
        
        for service in services:
            with patch("grpc.aio.insecure_channel") as mock_channel:
                mock_channel_instance = AsyncMock()
                mock_channel.return_value = mock_channel_instance
                mock_channel_instance.__aenter__ = AsyncMock(return_value=mock_channel_instance)
                mock_channel_instance.__aexit__ = AsyncMock(return_value=None)
                mock_channel_instance.close = AsyncMock()
                
                result = await executor.execute({
                    "server": "localhost:50051",
                    "service": service,
                    "method": "Process",
                    "request": {"data": "test"}
                })
                
                assert result["success"] is True
                assert result["service"] == service
    
    @pytest.mark.asyncio
    async def test_get_input_schema(self):
        """Test input schema generation"""
        executor = GrpcExecutor()
        schema = executor.get_input_schema()
        
        assert schema["type"] == "object"
        assert "server" in schema["required"]
        assert "service" in schema["required"]
        assert "method" in schema["required"]
        assert "request" in schema["required"]
        assert "metadata" in schema["properties"]
        assert "timeout" in schema["properties"]


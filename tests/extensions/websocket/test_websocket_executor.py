"""
Test WebSocketExecutor

Tests for WebSocket communication functionality.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from aipartnerupflow.extensions.websocket.websocket_executor import WebSocketExecutor, WEBSOCKETS_AVAILABLE


class TestWebSocketExecutor:
    """Test WebSocketExecutor functionality"""
    
    @pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not installed")
    @pytest.mark.asyncio
    async def test_execute_websocket_message(self):
        """Test sending WebSocket message and receiving response"""
        executor = WebSocketExecutor()
        
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.recv = AsyncMock(return_value='{"response": "ok"}')
        mock_websocket.__aenter__ = AsyncMock(return_value=mock_websocket)
        mock_websocket.__aexit__ = AsyncMock(return_value=None)
        
        with patch("websockets.connect", return_value=mock_websocket):
            result = await executor.execute({
                "url": "ws://example.com/ws",
                "message": "Hello",
                "wait_response": True
            })
            
            assert result["success"] is True
            assert result["message_sent"] == "Hello"
            mock_websocket.send.assert_called_once()
            mock_websocket.recv.assert_called_once()
    
    @pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not installed")
    @pytest.mark.asyncio
    async def test_execute_websocket_no_response(self):
        """Test sending WebSocket message without waiting for response"""
        executor = WebSocketExecutor()
        
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.__aenter__ = AsyncMock(return_value=mock_websocket)
        mock_websocket.__aexit__ = AsyncMock(return_value=None)
        
        with patch("websockets.connect", return_value=mock_websocket):
            result = await executor.execute({
                "url": "ws://example.com/ws",
                "message": "Hello",
                "wait_response": False
            })
            
            assert result["success"] is True
            assert result["message_sent"] == "Hello"
            assert result["response"] is None
            mock_websocket.send.assert_called_once()
            mock_websocket.recv.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_execute_missing_url(self):
        """Test error when URL is missing"""
        executor = WebSocketExecutor()
        
        with pytest.raises(ValueError, match="url is required"):
            await executor.execute({
                "message": "Hello"
            })
    
    @pytest.mark.asyncio
    async def test_execute_missing_message(self):
        """Test error when message is missing"""
        executor = WebSocketExecutor()
        
        with pytest.raises(ValueError, match="message is required"):
            await executor.execute({
                "url": "ws://example.com/ws"
            })
    
    @pytest.mark.asyncio
    async def test_execute_websockets_not_available(self):
        """Test behavior when websockets is not installed"""
        with patch("aipartnerupflow.extensions.websocket.websocket_executor.WEBSOCKETS_AVAILABLE", False):
            executor = WebSocketExecutor()
            result = await executor.execute({
                "url": "ws://example.com/ws",
                "message": "Hello"
            })
            
            assert result["success"] is False
            assert "websockets" in result["error"].lower()
    
    @pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not installed")
    @pytest.mark.asyncio
    async def test_execute_with_json_message(self):
        """Test sending JSON message via WebSocket"""
        executor = WebSocketExecutor()
        
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.recv = AsyncMock(return_value='{"status": "received"}')
        mock_websocket.__aenter__ = AsyncMock(return_value=mock_websocket)
        mock_websocket.__aexit__ = AsyncMock(return_value=None)
        
        with patch("websockets.connect", return_value=mock_websocket):
            result = await executor.execute({
                "url": "ws://example.com/ws",
                "message": {"type": "test", "data": "value"},
                "wait_response": True
            })
            
            assert result["success"] is True
            # Message should be JSON stringified
            call_args = mock_websocket.send.call_args[0]
            assert "test" in call_args[0] or "value" in call_args[0]
    
    @pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not installed")
    @pytest.mark.asyncio
    async def test_execute_with_custom_headers(self):
        """Test WebSocket connection with custom headers"""
        executor = WebSocketExecutor()
        
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.recv = AsyncMock(return_value="response")
        mock_websocket.__aenter__ = AsyncMock(return_value=mock_websocket)
        mock_websocket.__aexit__ = AsyncMock(return_value=None)
        
        with patch("websockets.connect", return_value=mock_websocket) as mock_connect:
            result = await executor.execute({
                "url": "ws://example.com/ws",
                "message": "Hello",
                "headers": {"Authorization": "Bearer token"}
            })
            
            assert result["success"] is True
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["extra_headers"]["Authorization"] == "Bearer token"
    
    @pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not installed")
    @pytest.mark.asyncio
    async def test_execute_response_timeout(self):
        """Test handling response timeout"""
        executor = WebSocketExecutor()
        
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.__aenter__ = AsyncMock(return_value=mock_websocket)
        mock_websocket.__aexit__ = AsyncMock(return_value=None)
        
        # Mock wait_for to raise TimeoutError when waiting for response
        with patch("websockets.connect", return_value=mock_websocket), \
             patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError()
            
            result = await executor.execute({
                "url": "ws://example.com/ws",
                "message": "Hello",
                "wait_response": True,
                "timeout": 5.0
            })
            
            assert result["success"] is False
            assert "timeout" in result["error"].lower()
    
    @pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not installed")
    @pytest.mark.asyncio
    async def test_execute_connection_closed(self):
        """Test handling connection closed error"""
        executor = WebSocketExecutor()
        
        import websockets
        
        # Create a ConnectionClosed exception using the class's __new__ method
        # This is safer than object.__new__
        try:
            connection_closed_error = websockets.exceptions.ConnectionClosed.__new__(
                websockets.exceptions.ConnectionClosed
            )
            # Set required attributes using object.__setattr__ to bypass property setters
            object.__setattr__(connection_closed_error, 'rcvd', None)
            object.__setattr__(connection_closed_error, 'sent', None)
            object.__setattr__(connection_closed_error, 'rcvd_then_sent', None)
        except (TypeError, AttributeError):
            # If that fails, create a subclass that bypasses validation
            class TestConnectionClosed(websockets.exceptions.ConnectionClosed):
                def __init__(self):
                    # Don't call super().__init__ to avoid validation
                    Exception.__init__(self, "Connection closed")
                    # Use object.__setattr__ to set internal attributes
                    object.__setattr__(self, 'rcvd', None)
                    object.__setattr__(self, 'sent', None)
                    object.__setattr__(self, 'rcvd_then_sent', None)
            
            connection_closed_error = TestConnectionClosed()
        
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.__aenter__ = AsyncMock(return_value=mock_websocket)
        mock_websocket.__aexit__ = AsyncMock(return_value=None)
        mock_websocket.recv = AsyncMock(side_effect=connection_closed_error)
        
        with patch("websockets.connect", return_value=mock_websocket):
            result = await executor.execute({
                "url": "ws://example.com/ws",
                "message": "Hello",
                "wait_response": True
            })
            
            assert result["success"] is False
            assert "closed" in result["error"].lower()
            # Note: e.code and e.reason may raise AttributeError if rcvd/sent are None
            # but the exception should still be caught and error message returned
    
    @pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not installed")
    @pytest.mark.asyncio
    async def test_execute_invalid_uri(self):
        """Test handling invalid WebSocket URI"""
        executor = WebSocketExecutor()
        
        import websockets
        
        # Create an InvalidURI exception by subclassing
        # This ensures the except clause will catch it
        class TestInvalidURI(websockets.exceptions.InvalidURI):
            def __init__(self):
                # Bypass parent __init__ requirements
                self.msg = "Invalid URI"
        
        invalid_uri_error = TestInvalidURI()
        
        with patch("websockets.connect", side_effect=invalid_uri_error):
            result = await executor.execute({
                "url": "invalid://uri",
                "message": "Hello"
            })
            
            assert result["success"] is False
            assert "invalid" in result["error"].lower()
    
    @pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not installed")
    @pytest.mark.asyncio
    async def test_execute_cancellation_before_connection(self):
        """Test cancellation before WebSocket connection"""
        executor = WebSocketExecutor()
        executor.cancellation_checker = lambda: True
        
        result = await executor.execute({
            "url": "ws://example.com/ws",
            "message": "Hello"
        })
        
        assert result["success"] is False
        assert "cancelled" in result["error"].lower()
    
    @pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not installed")
    @pytest.mark.asyncio
    async def test_execute_cancellation_after_response(self):
        """Test cancellation after receiving response"""
        executor = WebSocketExecutor()
        cancelled = [False]
        
        def check_cancellation():
            if not cancelled[0]:
                cancelled[0] = True
                return False
            return True
        
        executor.cancellation_checker = check_cancellation
        
        mock_websocket = AsyncMock()
        mock_websocket.send = AsyncMock()
        mock_websocket.recv = AsyncMock(return_value="response")
        mock_websocket.__aenter__ = AsyncMock(return_value=mock_websocket)
        mock_websocket.__aexit__ = AsyncMock(return_value=None)
        
        with patch("websockets.connect", return_value=mock_websocket):
            result = await executor.execute({
                "url": "ws://example.com/ws",
                "message": "Hello",
                "wait_response": True
            })
            
            assert result["success"] is False
            assert "cancelled" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_get_input_schema(self):
        """Test input schema generation"""
        executor = WebSocketExecutor()
        schema = executor.get_input_schema()
        
        assert schema["type"] == "object"
        assert "url" in schema["required"]
        assert "message" in schema["required"]
        assert "wait_response" in schema["properties"]
        assert "headers" in schema["properties"]


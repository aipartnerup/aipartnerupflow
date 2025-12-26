"""
Test LLM client module
"""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from aipartnerupflow.extensions.generate.llm_client import (
    OpenAIClient,
    AnthropicClient,
    create_llm_client
)


class TestLLMClient:
    """Test LLM client abstraction"""
    
    def test_create_llm_client_openai(self):
        """Test creating OpenAI client"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            # Mock the openai module import
            with patch('builtins.__import__', side_effect=lambda name, *args, **kwargs: Mock() if name == 'openai' else __import__(name, *args, **kwargs)):
                # Actually we need to patch it differently - let's just test the error case
                # or skip if openai is not installed
                try:
                    import openai  # noqa: F401
                    with patch('openai.AsyncOpenAI') as mock_openai_class:
                        mock_client = Mock(api_key="test-key")
                        mock_openai_class.return_value = mock_client
                        client = create_llm_client(provider="openai", api_key="test-key")
                        assert isinstance(client, OpenAIClient)
                except ImportError:
                    pytest.skip("OpenAI package not installed")
    
    def test_create_llm_client_anthropic(self):
        """Test creating Anthropic client"""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            try:
                import anthropic  # noqa: F401
                with patch('anthropic.AsyncAnthropic') as mock_anthropic_class:
                    mock_client = Mock(api_key="test-key")
                    mock_anthropic_class.return_value = mock_client
                    client = create_llm_client(provider="anthropic", api_key="test-key")
                    assert isinstance(client, AnthropicClient)
            except ImportError:
                pytest.skip("Anthropic package not installed")
    
    def test_create_llm_client_invalid_provider(self):
        """Test creating client with invalid provider"""
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_llm_client(provider="invalid")
    
    @pytest.mark.asyncio
    async def test_openai_client_generate(self):
        """Test OpenAI client generation"""
        try:
            import openai  # noqa: F401
        except ImportError:
            pytest.skip("OpenAI package not installed")
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch('openai.AsyncOpenAI') as mock_openai_class:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock(message=Mock(content="Test response"))]
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                mock_openai_class.return_value = mock_client
                
                client = OpenAIClient(api_key="test-key")
                result = await client.generate("Test prompt")
                assert result == "Test response"
    
    @pytest.mark.asyncio
    async def test_anthropic_client_generate(self):
        """Test Anthropic client generation"""
        try:
            import anthropic  # noqa: F401
        except ImportError:
            pytest.skip("Anthropic package not installed")
        
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch('anthropic.AsyncAnthropic') as mock_anthropic_class:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.content = [Mock(text="Test response")]
                mock_client.messages.create = AsyncMock(return_value=mock_response)
                mock_anthropic_class.return_value = mock_client
                
                client = AnthropicClient(api_key="test-key")
                result = await client.generate("Test prompt")
                assert result == "Test response"


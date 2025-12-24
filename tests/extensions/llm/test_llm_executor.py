
import sys
import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Try to import litellm, if failing, mock it so we can run unit tests without it
try:
    import litellm
except ImportError:
    if "litellm" not in sys.modules:
        sys.modules["litellm"] = MagicMock()

from aipartnerupflow.extensions.llm.llm_executor import LLMExecutor
from aipartnerupflow.core.extensions import get_registry

@pytest.fixture
def mock_litellm_module():
    """Patch the litellm module"""
    with patch("aipartnerupflow.extensions.llm.llm_executor.litellm") as mock_mod:
        mock_mod.acompletion = AsyncMock()
        yield mock_mod

@pytest.mark.asyncio
async def test_llm_executor_completion(mock_litellm_module):
    """Test standard completion"""
    mock_response = MagicMock()
    mock_response.model_dump.return_value = {
        "choices": [{"message": {"content": "Hello world"}}]
    }
    mock_litellm_module.acompletion.return_value = mock_response
    
    executor = LLMExecutor()
    inputs = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hi"}]
    }
    
    result = await executor.execute(inputs)
    
    assert result["success"] is True
    assert result["content"] == "Hello world"
    assert result["is_stream"] is False
    
    mock_litellm_module.acompletion.assert_awaited_once()
    _, kwargs = mock_litellm_module.acompletion.call_args
    assert kwargs["stream"] is False

@pytest.mark.asyncio
async def test_llm_executor_streaming_inputs(mock_litellm_module):
    """Test streaming via inputs"""
    async def mock_stream_gen():
        yield {"choices": [{"delta": {"content": "Hello"}}]}
    
    mock_litellm_module.acompletion.return_value = mock_stream_gen()
    
    executor = LLMExecutor()
    inputs = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hi"}],
        "stream": True  # Explicitly set in inputs
    }
    
    result = await executor.execute(inputs)
    
    assert result["success"] is True
    assert result["is_stream"] is True
    assert result["stream"] is not None
    
    _, kwargs = mock_litellm_module.acompletion.call_args
    assert kwargs["stream"] is True

@pytest.mark.asyncio
async def test_llm_executor_streaming_metadata(mock_litellm_module):
    """Test streaming via context metadata"""
    async def mock_stream_gen():
        yield {"choices": [{"delta": {"content": "Hello"}}]}
    
    mock_litellm_module.acompletion.return_value = mock_stream_gen()
    
    executor = LLMExecutor()
    
    # Mock context
    mock_context = MagicMock()
    mock_context.metadata = {"stream": True}
    executor.context = mock_context
    
    inputs = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hi"}],
        # stream not in inputs
    }
    
    result = await executor.execute(inputs)
    
    assert result["success"] is True
    assert result["is_stream"] is True
    
    _, kwargs = mock_litellm_module.acompletion.call_args
    assert kwargs["stream"] is True

@pytest.mark.asyncio
async def test_llm_executor_registration():
    """Test standard registration"""
    import aipartnerupflow.extensions.llm.llm_executor
    registry = get_registry()
    assert registry.is_registered("llm_executor")
    assert isinstance(registry.create_executor_instance("llm_executor"), LLMExecutor)

@pytest.mark.asyncio
async def test_llm_executor_real_api_call():
    """Test real API call if keys are present (Integration Test)"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
        
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not openai_key and not anthropic_key:
        pytest.skip("No API key found in environment (OPENAI_API_KEY or ANTHROPIC_API_KEY)")
    
    executor = LLMExecutor()
    
    # Determine model based on available key
    if openai_key:
        # Use gpt-4o for cheap testing
        model = "gpt-4o" 
    else:
        # Use claude-sonnet-4-5 for cheap testing
        model = "claude-sonnet-4-5"
        
    inputs = {
        "model": model,
        "messages": [{"role": "user", "content": "Say exactly 'TEST_SUCCESS'"}],
        # Do not mock stream here, standard call
    }
    
    print(f"\nDEBUG: Running real API call with model {model}")
    try:
        result = await executor.execute(inputs)
    except Exception as e:
        pytest.fail(f"Real API call execution exception: {str(e)}")
    
    if not result["success"]:
        pytest.fail(f"Real API call failed result: {result.get('error')}")
        
    assert result["success"] is True
    # Check if content contains TEST_SUCCESS (LLM might add punctuation)
    content = result.get("content", "")
    assert "TEST_SUCCESS" in content or "TEST_SUCCESS" in content.upper()
    assert result["is_stream"] is False

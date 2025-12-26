import logging
import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from aipartnerupflow.extensions.llm.llm_executor import LLMExecutor, LITELLM_AVAILABLE
from aipartnerupflow.core.extensions import get_registry

logger = logging.getLogger(__name__)


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

@pytest.mark.skipif(not LITELLM_AVAILABLE, reason="litellm not installed")
@pytest.mark.asyncio
async def test_llm_executor_registration():
    """Test standard registration"""
    registry = get_registry()
    assert registry.is_registered("llm_executor")
    assert isinstance(registry.create_executor_instance("llm_executor"), LLMExecutor)

@pytest.mark.skipif(not LITELLM_AVAILABLE, reason="litellm not installed")
@pytest.mark.asyncio
async def test_llm_executor_real_api_call():
    """Test real API call if keys are present (Integration Test)"""
    # Force reload environment variables from .env to ensure real keys are available
    # and not overridden by previous tests' mock keys if they leaked
    try:
        from dotenv import load_dotenv
        # Use override=True to ensure we get the real values from .env
        load_dotenv(override=True)
    except ImportError:
        pass
        
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    
    # Check for obvious mock keys to prevent accidental real API calls with fake keys
    mock_keys = ["test-key", "mock-", "test-key-123"]
    if openai_key and any(m in openai_key for m in mock_keys):
        logger.warning(f"Detected potential mock key in OPENAI_API_KEY: {openai_key}. Ignoring for real API test.")
        openai_key = None
    if anthropic_key and any(m in anthropic_key for m in mock_keys):
        logger.warning(f"Detected potential mock key in ANTHROPIC_API_KEY: {anthropic_key}. Ignoring for real API test.")
        anthropic_key = None
    
    if not openai_key and not anthropic_key:
        pytest.skip("No real API key found in environment (OPENAI_API_KEY or ANTHROPIC_API_KEY). "
                    "Skipping integration test to avoid using mock keys.")
    
    executor = LLMExecutor()
    
    # Determine model based on available key
    if openai_key:
        # Use gpt-4o for cheap testing
        model = "gpt-4o" 
        active_key_suffix = f"...{openai_key[-4:]}" if len(openai_key) > 8 else "****"
    else:
        # Use claude-sonnet-4-5 for cheap testing
        model = "claude-sonnet-4-5"
        active_key_suffix = f"...{anthropic_key[-4:]}" if len(anthropic_key) > 8 else "****"
        
    inputs = {
        "model": model,
        "messages": [{"role": "user", "content": "Say exactly 'TEST_SUCCESS'"}],
    }
    
    print(f"\nDEBUG: Running real API call with model {model} (key: {active_key_suffix})")
    try:
        result = await executor.execute(inputs)
    except Exception as e:
        pytest.fail(f"Real API call execution exception: {str(e)}")
    
    if not result["success"]:
        # If it failed due to authentication, we want to know which key was used
        error_msg = result.get('error', 'Unknown error')
        pytest.fail(f"Real API call failed with error: {error_msg}. (Model: {model})")
        
    assert result["success"] is True
    # Check if content contains TEST_SUCCESS
    content = result.get("content", "")
    assert "TEST_SUCCESS" in content or "TEST_SUCCESS" in content.upper()
    assert result["is_stream"] is False

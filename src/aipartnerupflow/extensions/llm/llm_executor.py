"""
LLM Executor using LiteLLM
"""

from typing import Dict, Any, Optional
from aipartnerupflow.core.base import BaseTask
from aipartnerupflow.core.execution.errors import ValidationError
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)

# Try to import litellm, mark availability for tests and runtime checks
try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    litellm = None  # type: ignore
    LITELLM_AVAILABLE = False
    logger.warning(
        "litellm is not installed. LLM executor will not be available. "
        "Install it with: pip install aipartnerupflow[llm]"
    )

# Only register if litellm is available (prevents registration failure when dependency is missing)
if LITELLM_AVAILABLE:
    from aipartnerupflow.core.extensions.decorators import executor_register
else:
    # No-op decorator when litellm is not available
    def executor_register(*args, **kwargs):
        def decorator(cls):
            return cls
        return decorator


@executor_register()
class LLMExecutor(BaseTask):
    """
    Executor for interacting with LLMs via LiteLLM.
    
    Supports:
    - Text generation (Chat Completion)
    - Streaming (SSE compatible output structure)
    - Multiple providers (OpenAI, Anthropic, Gemini, etc.)
    
    Example usage in task schemas:
    {
        "schemas": {
            "method": "llm_executor"
        },
        "inputs": {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": false
        }
    }
    """
    
    id = "llm_executor"
    name = "LLM Executor"
    description = "Execute LLM requests using LiteLLM (supports 100+ models)"
    tags = ["llm", "ai", "completion", "chat", "litellm"]
    examples = [
        "Generate text using GPT-4",
        "Chat with Claude",
        "Summarize text"
    ]
    
    cancelable: bool = True
    
    @property
    def type(self) -> str:
        return "llm"
        
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute LLM completion
        
        Args:
            inputs:
                model (str): Model name (e.g. "gpt-4", "claude-3-opus")
                messages (List[Dict]): Chat messages
                stream (bool): Whether to stream response
                api_key (str, optional): API key (defaults to env var)
                **kwargs: Additional LiteLLM parameters (temperature, max_tokens, etc.)
        
        Returns:
            Dict containing response or generator for streaming
        """
        model = model = inputs.get("model")
        if not model:
            raise ValidationError(f"[{self.id}] model is required in inputs")
            
        messages = inputs.get("messages")
        if not messages:
            raise ValidationError(f"[{self.id}] messages is required in inputs")
            
        if self.context and hasattr(self.context, "metadata") and self.context.metadata.get("stream"):
            stream = True
        else:
            stream = inputs.get("stream", False)

        api_key = inputs.get("api_key")
        
        # Prepare kwargs
        completion_kwargs = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        
        if api_key:
            completion_kwargs["api_key"] = api_key
            
        # Add other optional parameters from inputs
        # Filter out keys we already handled or strict internal keys
        excluded_keys = {"model", "messages", "stream", "api_key"}
        for k, v in inputs.items():
            if k not in excluded_keys and not k.startswith("_"):
                completion_kwargs[k] = v
        
        logger.info(f"Executing LLM request: model={model}, stream={stream}")
        
        # Use acompletion for async execution
        # Exceptions (e.g., litellm.AuthenticationError, litellm.APIConnectionError) 
        # will propagate to TaskManager
        response = await litellm.acompletion(**completion_kwargs)
        
        if stream:
            # For streaming, we return a generator wrapper or the generator itself.
            # Since TaskExecutor usually expects a result dict, we might need to wrap it.
            # However, usually 'execute' should return the final result or a specific structure.
            # If the system supports streaming via returned generator, we return it.
            # Based on RestExecutor, it returns a dict.
            # If streaming is requested, we can return the generator in a 'stream' key
            # or similar, IF the caller knows how to handle it.
            # Given user request "support post and sse", implies web interface usage.
            # We return the raw object so the caller (API layer) can stream it.
            return {
                "success": True,
                "stream": response, # Async generator
                "model": model,
                "is_stream": True
            }
        
        # Non-streaming response
        # litellm returns a ModelResponse object (pydantic-like or dict-like)
        # We convert to dict
        result_dict = response.model_dump() if hasattr(response, "model_dump") else dict(response)
        
        # Extract content for convenience
        content = None
        if "choices" in result_dict and len(result_dict["choices"]) > 0:
            content = result_dict["choices"][0].get("message", {}).get("content")
        
        return {
            "success": True,
            "data": result_dict,
            "content": content,
            "model": model,
            "is_stream": False
        }

    def get_demo_result(self, task: Any, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Provide demo LLM response"""
        model = inputs.get("model", "demo-gpt")
        messages = inputs.get("messages", [])
        last_message = messages[-1]["content"] if messages else "Hello"
        
        demo_content = f"Attributes of {model}: This is a simulated response to '{last_message}'."
        
        return {
            "success": True,
            "data": {
                "id": "chatcmpl-demo",
                "object": "chat.completion",
                "created": 1677652288,
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": demo_content,
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": len(last_message),
                    "completion_tokens": len(demo_content),
                    "total_tokens": len(last_message) + len(demo_content)
                }
            },
            "content": demo_content,
            "model": model,
            "is_stream": False,
            "_demo_sleep": 1.0 
        }

    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "model": {"type": "string", "description": "LLM model name"},
                "messages": {
                    "type": "array", 
                    "items": {"type": "object"}, 
                    "description": "Chat messages like [{'role': 'user', 'content': '...'}]"
                },
                "stream": {"type": "boolean", "default": False},
                "temperature": {"type": "number"},
                "max_tokens": {"type": "integer"},
                "api_key": {"type": "string"}
            },
            "required": ["model", "messages"]
        }

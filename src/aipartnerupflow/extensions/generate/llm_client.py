"""
LLM Client Abstraction

This module provides an abstraction layer for LLM clients (OpenAI, Anthropic, etc.)
to support multiple LLM providers.
"""

import os
from abc import ABC, abstractmethod
from typing import Optional
from aipartnerupflow.core.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient(ABC):
    """
    Abstract base class for LLM clients
    """
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate a response from the LLM
        
        Args:
            prompt: Input prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            Generated response text
        """
        pass


class OpenAIClient(LLMClient):
    """
    OpenAI API client implementation
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize OpenAI client
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model name (defaults to gpt-4 or OPENAI_MODEL env var)
        """
        try:
            import openai
            self.client = openai.AsyncOpenAI(
                api_key=api_key or os.getenv("OPENAI_API_KEY")
            )
        except ImportError:
            raise ImportError(
                "OpenAI package is required. Install it with: pip install openai"
            )
        
        # Default to gpt-4o which has larger context window (128k tokens)
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        
        if not self.client.api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate a response using OpenAI API
        
        Args:
            prompt: Input prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            Generated response text
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 4000),
            )
            
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


class AnthropicClient(LLMClient):
    """
    Anthropic API client implementation
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize Anthropic client
        
        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model name (defaults to claude-3-opus-20240229 or ANTHROPIC_MODEL env var)
        """
        try:
            import anthropic
            self.client = anthropic.AsyncAnthropic(
                api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
            )
        except ImportError:
            raise ImportError(
                "Anthropic package is required. Install it with: pip install anthropic"
            )
        
        # Default to claude-3-5-sonnet which has larger context window (200k tokens)
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        
        if not self.client.api_key:
            raise ValueError(
                "Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate a response using Anthropic API
        
        Args:
            prompt: Input prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            Generated response text
        """
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 4096),
                temperature=kwargs.get("temperature", 0.7),
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Anthropic returns content as a list of text blocks
            content = response.content
            if isinstance(content, list) and len(content) > 0:
                return content[0].text
            return str(content)
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise


def create_llm_client(
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> LLMClient:
    """
    Create an LLM client based on provider
    
    Args:
        provider: LLM provider name ("openai" or "anthropic")
                 Defaults to AIPARTNERUPFLOW_LLM_PROVIDER env var or "openai"
        api_key: API key (optional, uses env vars if not provided)
        model: Model name (optional, uses env vars if not provided)
        
    Returns:
        LLMClient instance
        
    Raises:
        ValueError: If provider is not supported
        ImportError: If required package is not installed
    """
    provider = provider or os.getenv("AIPARTNERUPFLOW_LLM_PROVIDER", "openai").lower()
    
    if provider == "openai":
        return OpenAIClient(api_key=api_key, model=model)
    elif provider == "anthropic":
        return AnthropicClient(api_key=api_key, model=model)
    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported providers: 'openai', 'anthropic'"
        )


__all__ = [
    "LLMClient",
    "OpenAIClient",
    "AnthropicClient",
    "create_llm_client",
]


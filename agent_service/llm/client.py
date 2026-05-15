import os
import asyncio
import logging
from typing import AsyncGenerator, Any, List, Dict
from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "dummy_key")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        
        # Load configuration from environment
        timeout_str = os.getenv("LLM_TIMEOUT", "120")
        max_retries_str = os.getenv("LLM_MAX_RETRIES", "2")
        
        try:
            self.timeout = float(timeout_str)
        except ValueError:
            self.timeout = 120.0
            
        try:
            self.max_retries = int(max_retries_str)
        except ValueError:
            self.max_retries = 2
        
        # Initialize the AsyncOpenAI client with configurable timeout and retries
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=self.max_retries
        )
        
        logger.info(f"LLMClient initialized: model={self.model}, base_url={self.base_url}, timeout={self.timeout}s, max_retries={self.max_retries}")

    async def chat_completion_stream(self, messages: List[Dict[str, Any]], **kwargs) -> AsyncGenerator[str, None]:
        """
        Stream the chat completion response with automatic retry on failure.
        
        Implements exponential backoff retry strategy for transient errors:
        - API connection errors
        - Timeout errors  
        - Rate limit errors (429)
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional arguments passed to the OpenAI API
            
        Yields:
            Content chunks from the streaming response
        """
        model = kwargs.pop("model", self.model)
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"LLM stream request (attempt {attempt + 1}/{self.max_retries + 1}): model={model}")
                
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True,
                    **kwargs
                )
                
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                        
                # Success - exit retry loop
                return
                
            except APITimeoutError as e:
                last_error = e
                logger.warning(f"LLM timeout on attempt {attempt + 1}: {str(e)}")
                
            except RateLimitError as e:
                last_error = e
                logger.warning(f"Rate limited on attempt {attempt + 1}: {str(e)}")
                # Wait longer for rate limits before retrying
                if attempt < self.max_retries:
                    wait_time = min(2 ** (attempt + 1) * 2, 60)  # Max 60 seconds
                    logger.info(f"Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    
            except APIError as e:
                last_error = e
                # Only retry on server errors (5xx), not client errors (4xx except 429)
                if hasattr(e, 'status_code') and 400 <= e.status_code < 500 and e.status_code != 429:
                    logger.error(f"Client error (not retryable): {e.status_code} - {str(e)}")
                    raise
                    
                logger.warning(f"API error on attempt {attempt + 1}: {str(e)}")
                
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error on attempt {attempt + 1}: {type(e).__name__} - {str(e)}")
            
            # Exponential backoff before retry (except on last attempt)
            if attempt < self.max_retries:
                wait_time = 2 ** attempt  # 1s, 2s, 4s...
                logger.info(f"Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        # All retries exhausted
        logger.error(f"All {self.max_retries + 1} attempts failed. Last error: {last_error}")
        raise last_error or Exception("Unknown error occurred after all retries")

    async def chat_completion(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Get the full chat completion response with automatic retry.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional arguments passed to the OpenAI API
            
        Returns:
            Complete response content string
        """
        model = kwargs.pop("model", self.model)
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"LLM request (attempt {attempt + 1}/{self.max_retries + 1}): model={model}")
                
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=False,
                    **kwargs
                )
                
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content
                return ""
                
            except (APITimeoutError, RateLimitError, APIError) as e:
                last_error = e
                logger.warning(f"Error on attempt {attempt + 1}: {type(e).__name__} - {str(e)}")
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error: {type(e).__name__} - {str(e)}")
                raise
        
        raise last_error or Exception("Unknown error occurred after all retries")

    def get_config_info(self) -> Dict[str, Any]:
        """
        Return current configuration information (for debugging).
        """
        return {
            "model": self.model,
            "base_url": self.base_url[:50] + "..." if len(self.base_url or "") > 50 else self.base_url,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "api_key_set": bool(self.api_key and self.api_key != "dummy_key"),
        }

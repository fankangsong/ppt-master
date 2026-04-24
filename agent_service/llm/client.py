import os
from typing import AsyncGenerator, Any, List, Dict
from openai import AsyncOpenAI

class LLMClient:
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "dummy_key")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        
        # Initialize the AsyncOpenAI client
        # If base_url is None, AsyncOpenAI will default to the standard OpenAI URL.
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=120.0, # Add a longer timeout for LLM generation
            max_retries=2
        )
        
    async def chat_completion_stream(self, messages: List[Dict[str, Any]], **kwargs) -> AsyncGenerator[str, None]:
        """
        Stream the chat completion response.
        """
        model = kwargs.pop("model", self.model)
        
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            **kwargs
        )
        
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat_completion(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """
        Get the full chat completion response.
        """
        model = kwargs.pop("model", self.model)
        
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False,
            **kwargs
        )
        
        if response.choices and response.choices[0].message.content:
            return response.choices[0].message.content
        return ""

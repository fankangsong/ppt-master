import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI
import traceback

async def test_connection():
    # Load env variables exactly as the app does
    load_dotenv()
    
    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY", "dummy_key")
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    print("=== Configuration ===")
    print(f"Base URL: {base_url}")
    print(f"API Key: {api_key[:5]}...{api_key[-5:]}" if len(api_key) > 10 else f"API Key: {api_key}")
    print(f"Model: {model}")
    print("=====================")
    
    try:
        # Note: we need to use http_client parameter for passing proxy if any,
        # but let's test the default setup first.
        client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=30.0,
            max_retries=0
        )
        
        print("\nSending test request...")
        messages = [{"role": "user", "content": "Hello, this is a test. Reply 'test is ok'."}]
        
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=False
        )
        
        print("\nSuccess! Response:")
        print(response.choices[0].message.content)
        
    except Exception as e:
        print("\nError occurred:")
        print(f"Type: {type(e).__name__}")
        print(f"Message: {str(e)}")
        print("\nTraceback:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_connection())
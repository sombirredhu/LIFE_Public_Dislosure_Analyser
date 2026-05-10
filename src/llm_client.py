"""
LLM Client - wrapper around Claude API.
Handles retries, rate limits, and error handling.
"""

import time
from typing import Optional
from anthropic import Anthropic, APIError, RateLimitError, APITimeoutError

from src.config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    CLAUDE_MAX_TOKENS,
    CLAUDE_TEMPERATURE
)


def ask_claude(
    system_prompt: str,
    user_message: str,
    max_tokens: int = None,
    temperature: float = None,
    max_retries: int = 3
) -> str:
    """
    Send a message to Claude and get a response.
    
    Args:
        system_prompt: System instructions for Claude
        user_message: User's question or prompt
        max_tokens: Maximum tokens in response (defaults to config)
        temperature: Response randomness 0-1 (defaults to config)
        max_retries: Number of retry attempts on failure
    
    Returns:
        Claude's response text
    
    Raises:
        ValueError: If API key is not configured
        APIError: If all retries fail
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. "
            "Please add it to your .env file."
        )
    
    if max_tokens is None:
        max_tokens = CLAUDE_MAX_TOKENS
    
    if temperature is None:
        temperature = CLAUDE_TEMPERATURE
    
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_message
                    }
                ]
            )
            
            # Extract text from response
            return response.content[0].text
        
        except RateLimitError as e:
            last_error = e
            wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            print(f"Rate limit hit. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
            time.sleep(wait_time)
        
        except APITimeoutError as e:
            last_error = e
            wait_time = 2 ** attempt
            print(f"Request timeout. Retrying {attempt + 1}/{max_retries}...")
            time.sleep(wait_time)
        
        except APIError as e:
            last_error = e
            # For other API errors, don't retry
            raise
    
    # All retries failed
    raise last_error


def ask_claude_streaming(
    system_prompt: str,
    user_message: str,
    max_tokens: int = None,
    temperature: float = None
):
    """
    Stream Claude's response token by token.
    Useful for real-time UI updates.
    
    Args:
        system_prompt: System instructions
        user_message: User's question
        max_tokens: Maximum tokens (defaults to config)
        temperature: Response randomness (defaults to config)
    
    Yields:
        Text chunks as they arrive
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set")
    
    if max_tokens is None:
        max_tokens = CLAUDE_MAX_TOKENS
    
    if temperature is None:
        temperature = CLAUDE_TEMPERATURE
    
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    
    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    ) as stream:
        for text in stream.text_stream:
            yield text


if __name__ == "__main__":
    # Test Claude API
    import sys
    
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = "What is 2+2? Answer in one sentence."
    
    print(f"Question: {question}\n")
    
    system_prompt = "You are a helpful assistant. Answer questions concisely."
    
    try:
        print("Calling Claude API...")
        response = ask_claude(system_prompt, question)
        
        print(f"\n✓ Response received:\n")
        print(response)
        
    except ValueError as e:
        print(f"\n✗ Configuration error: {e}")
        print("\nPlease create a .env file with your ANTHROPIC_API_KEY")
        print("You can copy .env.example to .env and fill in your API key")
    
    except Exception as e:
        print(f"\n✗ Error: {e}")

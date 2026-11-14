"""
Retry utilities for handling transient failures
"""
import asyncio
import logging
from typing import Callable, Any, Optional, TypeVar, Union
from functools import wraps
import random

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior"""
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retry_on: Optional[tuple] = None,
        retry_on_status: Optional[tuple] = None
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retry_on = retry_on or (Exception,)
        self.retry_on_status = retry_on_status or (500, 502, 503, 504)


async def retry_async(
    func: Callable[..., T],
    config: RetryConfig = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None
) -> T:
    """
    Retry an async function with exponential backoff
    
    Args:
        func: The async function to retry
        config: Retry configuration
        on_retry: Optional callback called on each retry with (exception, attempt_number)
        
    Returns:
        The result of the function call
        
    Raises:
        The last exception if all retries fail
    """
    if config is None:
        config = RetryConfig()
        
    last_exception = None
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            
            # Check if we should retry this exception
            should_retry = False
            
            # Check exception type
            if isinstance(e, config.retry_on):
                should_retry = True
                
            # Check HTTP status codes if it's an HTTP error
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                if e.response.status_code in config.retry_on_status:
                    should_retry = True
                elif e.response.status_code < 500:  # Don't retry client errors by default
                    should_retry = False
                    
            if not should_retry or attempt == config.max_attempts:
                raise e
                
            # Calculate delay with exponential backoff
            delay = min(
                config.initial_delay * (config.exponential_base ** (attempt - 1)),
                config.max_delay
            )
            
            # Add jitter to prevent thundering herd
            if config.jitter:
                delay = delay * (0.5 + random.random())
                
            logger.warning(
                f"Retry attempt {attempt}/{config.max_attempts} after {delay:.2f}s delay. "
                f"Error: {type(e).__name__}: {str(e)}"
            )
            
            # Call retry callback if provided
            if on_retry:
                try:
                    on_retry(e, attempt)
                except Exception as callback_error:
                    logger.error(f"Error in retry callback: {callback_error}")
                    
            # Wait before retrying
            await asyncio.sleep(delay)
            
    # This should not be reached, but just in case
    if last_exception:
        raise last_exception
    else:
        raise RuntimeError("Retry logic error: no exception captured")


def with_retry(config: RetryConfig = None):
    """
    Decorator for adding retry logic to async functions
    
    Usage:
        @with_retry(RetryConfig(max_attempts=5))
        async def my_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                lambda: func(*args, **kwargs),
                config=config
            )
        return wrapper
    return decorator


# Pre-configured retry configurations
AUTH_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=0.5,
    max_delay=5.0,
    retry_on=(Exception,),
    retry_on_status=(401, 403, 500, 502, 503, 504)
)

NETWORK_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=10.0,
    retry_on=(Exception,),
    retry_on_status=(500, 502, 503, 504, 429)  # Include rate limiting
)

DATABASE_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    initial_delay=0.1,
    max_delay=2.0,
    exponential_base=2.0,
    retry_on=(Exception,),  # Retry on database connection errors
    jitter=True
)
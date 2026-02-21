"""
Async utilities for Weather Buddy
"""
import asyncio
import concurrent.futures
import threading

# Thread pool for async operations
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

def run_async(coro):
    """Run an async coroutine in a background thread and return the result via callback"""
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    return _executor.submit(run_in_thread)

def shutdown_executor():
    """Shutdown the thread pool executor"""
    _executor.shutdown(wait=False)

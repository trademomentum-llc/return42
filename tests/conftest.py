import asyncio


async def _wait_for(predicate, timeout: float = 1.0, interval: float = 0.01):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() >= deadline:
            raise TimeoutError("Predicate was not satisfied in time")
        await asyncio.sleep(interval)

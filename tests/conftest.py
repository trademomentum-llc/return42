import asyncio


async def _wait_for(predicate, timeout: float = 1.0, interval: float = 0.01):
    deadline = asyncio.get_event_loop().time() + timeout
    while not predicate():
        if asyncio.get_event_loop().time() >= deadline:
            raise TimeoutError("Predicate was not satisfied in time")
        await asyncio.sleep(interval)

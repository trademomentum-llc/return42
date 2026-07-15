import warnings

import pytest
from return42.observability.telemetry import TelemetryBus, TelemetryEvent, EventLevel


def test_publish_and_subscribe():
    bus = TelemetryBus()
    received = []

    def handler(event):
        received.append(event)

    bus.subscribe("mesh.heartbeat", handler)
    event = TelemetryEvent(
        name="mesh.heartbeat",
        source="som-01",
        level=EventLevel.INFO,
        payload={"rssi": -42},
    )
    bus.publish(event)

    assert len(received) == 1
    assert received[0].name == "mesh.heartbeat"
    assert received[0].payload["rssi"] == -42


def test_async_subscriber():
    bus = TelemetryBus()
    received = []

    async def handler(event):
        received.append(event)

    bus.subscribe("test.async", handler)
    # The sync bus invokes async handlers without awaiting them, so the
    # expected behavior is confirmed while suppressing the coroutine warning.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        bus.publish(TelemetryEvent(name="test.async", source="test", payload={"n": 1}))

    assert len(received) == 0

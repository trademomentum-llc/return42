from prometheus_client import CollectorRegistry

from return42.observability.metrics import (
    MetricsRegistry,
    inc_counter,
    observe_histogram,
    set_gauge,
)


def _isolated_registry() -> MetricsRegistry:
    return MetricsRegistry(registry=CollectorRegistry())


def test_counter_increments_with_injected_registry():
    registry = _isolated_registry()
    inc_counter("test_requests_total", {"method": "GET"}, registry=registry)
    inc_counter("test_requests_total", {"method": "GET"}, registry=registry)
    samples = registry.get_sample_values("test_requests_total")
    assert samples[("test_requests_total", (("method", "GET"),))] == 2.0


def test_gauge_sets_value_with_injected_registry():
    registry = _isolated_registry()
    set_gauge("test_temperature_celsius", 42.0, {"node": "som-01"}, registry=registry)
    samples = registry.get_sample_values("test_temperature_celsius")
    assert samples[("test_temperature_celsius", (("node", "som-01"),))] == 42.0


def test_histogram_observes_value_with_injected_registry():
    registry = _isolated_registry()
    observe_histogram("test_latency_seconds", 0.25, {"endpoint": "/health"}, registry=registry)
    samples = registry.get_sample_values("test_latency_seconds")
    assert samples[("test_latency_seconds_bucket", (("endpoint", "/health"), ("le", "+Inf")))] == 1.0


def test_injected_registries_are_isolated():
    registry_a = _isolated_registry()
    registry_b = _isolated_registry()
    inc_counter("isolated_total", registry=registry_a)
    assert registry_a.get_sample_values("isolated_total")[("isolated_total", ())] == 1.0
    assert b"isolated_total" not in registry_b.expose()


def test_registry_exposes_prometheus_format():
    registry = _isolated_registry()
    registry.counter("local_total", "Local counter").inc()
    output = registry.expose()
    assert b"local_total" in output

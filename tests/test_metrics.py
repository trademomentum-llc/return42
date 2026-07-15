from return42.observability.metrics import (
    MetricsRegistry,
    get_registry,
    inc_counter,
    observe_histogram,
    set_gauge,
)


def test_counter_increments():
    registry = get_registry()
    inc_counter("test_requests_total", {"method": "GET"})
    inc_counter("test_requests_total", {"method": "GET"})
    samples = registry.get_sample_values("test_requests_total")
    assert samples[("test_requests_total", ("method", "GET"))] == 2.0


def test_gauge_sets_value():
    registry = get_registry()
    set_gauge("test_temperature_celsius", 42.0, {"node": "som-01"})
    samples = registry.get_sample_values("test_temperature_celsius")
    assert samples[("test_temperature_celsius", ("node", "som-01"))] == 42.0


def test_histogram_observes_value():
    registry = get_registry()
    observe_histogram("test_latency_seconds", 0.25, {"endpoint": "/health"})
    samples = registry.get_sample_values("test_latency_seconds")
    assert samples[("test_latency_seconds_bucket", ("endpoint", "/health"))] == 1.0


def test_registry_exposes_prometheus_format():
    registry = MetricsRegistry()
    registry.counter("local_total", "Local counter").inc()
    output = registry.expose()
    assert b"local_total" in output

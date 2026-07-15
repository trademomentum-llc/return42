"""Prometheus metrics wrapper."""

from __future__ import annotations

from prometheus_client import (
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    PlatformCollector,
    ProcessCollector,
    generate_latest,
)


class MetricsRegistry:
    """Wraps prometheus_client CollectorRegistry with lazy metric creation."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self._registry = registry if registry is not None else REGISTRY
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}
        # Default Prometheus collectors (python_info, process metrics, etc.) are
        # already present on prometheus_client.REGISTRY. Custom registries used
        # for tests need them registered explicitly.
        if self._registry is not REGISTRY:
            PlatformCollector(registry=self._registry)
            ProcessCollector(registry=self._registry)

    def counter(self, name: str, description: str, labels: tuple[str, ...] = ()) -> Counter:
        if name not in self._counters:
            self._counters[name] = Counter(name, description, labels, registry=self._registry)
        return self._counters[name]

    def gauge(self, name: str, description: str, labels: tuple[str, ...] = ()) -> Gauge:
        if name not in self._gauges:
            self._gauges[name] = Gauge(name, description, labels, registry=self._registry)
        return self._gauges[name]

    def histogram(self, name: str, description: str, labels: tuple[str, ...] = (), buckets: tuple[float, ...] | None = None) -> Histogram:
        if name not in self._histograms:
            kwargs = {"registry": self._registry}
            if buckets is not None:
                kwargs["buckets"] = buckets
            self._histograms[name] = Histogram(name, description, labels, **kwargs)
        return self._histograms[name]

    def get_sample_values(self, name: str) -> dict[tuple[str, tuple[tuple[str, str], ...]], float]:
        """Return sample values keyed by (metric_name, ((label_name, label_value), ...))."""
        result = {}
        for metric in self._registry.collect():
            if metric.name == name or any(sample.name == name for sample in metric.samples):
                for sample in metric.samples:
                    key = (sample.name, tuple(sorted(sample.labels.items())) if sample.labels else ())
                    result[key] = sample.value
        return result

    def expose(self) -> bytes:
        return generate_latest(self._registry)


# Global registry singleton
_GLOBAL_REGISTRY = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    return _GLOBAL_REGISTRY


def inc_counter(name: str, labels: dict[str, str] | None = None, registry: MetricsRegistry | None = None) -> None:
    labels = labels or {}
    target_registry = registry if registry is not None else get_registry()
    counter = target_registry.counter(name, f"Counter for {name}", tuple(labels.keys()))
    counter.labels(**labels).inc() if labels else counter.inc()


def set_gauge(name: str, value: float, labels: dict[str, str] | None = None, registry: MetricsRegistry | None = None) -> None:
    labels = labels or {}
    target_registry = registry if registry is not None else get_registry()
    gauge = target_registry.gauge(name, f"Gauge for {name}", tuple(labels.keys()))
    gauge.labels(**labels).set(value) if labels else gauge.set(value)


def observe_histogram(name: str, value: float, labels: dict[str, str] | None = None, registry: MetricsRegistry | None = None) -> None:
    labels = labels or {}
    target_registry = registry if registry is not None else get_registry()
    histogram = target_registry.histogram(name, f"Histogram for {name}", tuple(labels.keys()))
    histogram.labels(**labels).observe(value) if labels else histogram.observe(value)

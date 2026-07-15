"""Prometheus metrics wrapper."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest


class MetricsRegistry:
    """Wraps prometheus_client CollectorRegistry with lazy metric creation."""

    def __init__(self) -> None:
        self._registry = CollectorRegistry()
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}
        self._histograms: dict[str, Histogram] = {}

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

    def get_sample_values(self, name: str) -> dict[tuple[str, tuple[str, str]], float]:
        """Return sample values keyed by (metric_name, (label_name, label_value))."""
        result = {}
        for metric in self._registry.collect():
            if metric.name == name or any(sample.name == name for sample in metric.samples):
                for sample in metric.samples:
                    key = (sample.name, tuple(sample.labels.items())[0] if sample.labels else ("", ""))
                    result[key] = sample.value
        return result

    def expose(self) -> bytes:
        return generate_latest(self._registry)


# Global registry singleton
_GLOBAL_REGISTRY = MetricsRegistry()


def get_registry() -> MetricsRegistry:
    return _GLOBAL_REGISTRY


def inc_counter(name: str, labels: dict[str, str] | None = None) -> None:
    labels = labels or {}
    get_registry().counter(name, f"Counter for {name}", tuple(labels.keys())).labels(**labels).inc()


def set_gauge(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    labels = labels or {}
    get_registry().gauge(name, f"Gauge for {name}", tuple(labels.keys())).labels(**labels).set(value)


def observe_histogram(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    labels = labels or {}
    get_registry().histogram(name, f"Histogram for {name}", tuple(labels.keys())).labels(**labels).observe(value)

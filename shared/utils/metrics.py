"""Metrics utilities for JuicyFox (Plan A).

This module provides lightweight wrappers around ``prometheus_client``
to define and use metrics (counters, gauges, histograms) without
forcing a hard dependency.  If ``prometheus_client`` is not
installed, the metrics classes fall back to no‑op stubs so that calls
to ``inc()`` or ``observe()`` do nothing.  This allows code that
records metrics to run unchanged in environments where Prometheus is
not configured.

Example::

    from shared.utils.metrics import Counter

    requests_total = Counter('requests_total', 'Total HTTP requests')
    requests_total.inc()

The ``metrics`` module does not register any default endpoint for
exposing metrics; this should be done in your API layer if needed.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Type, Union

try:
    from prometheus_client import Counter as _PromCounter  # type: ignore
    from prometheus_client import Gauge as _PromGauge  # type: ignore
    from prometheus_client import Histogram as _PromHistogram  # type: ignore
except Exception:
    _PromCounter = None  # type: ignore
    _PromGauge = None  # type: ignore
    _PromHistogram = None  # type: ignore


class _NoOpMetric:
    """A no‑operation metric stub used when Prometheus is unavailable."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def labels(self, *args: Any, **kwargs: Any) -> "_NoOpMetric":
        return self

    def inc(self, amount: int = 1) -> None:
        pass

    def observe(self, value: float) -> None:
        pass

    def set(self, value: float) -> None:
        pass

    # Additional stubs for API compatibility with prometheus_client
    def time(self):
        """Return a context manager for timing code blocks.

        In the no‑op implementation this simply returns a context manager
        that does nothing on enter/exit.
        """
        class _NoOpTimer:
            def __enter__(self) -> "_NoOpTimer":
                return self

            def __exit__(self, *exc) -> bool:
                # Return False to propagate exceptions
                return False

        return _NoOpTimer()

    def count_exceptions(self, *args: Any, **kwargs: Any):
        """Return a context manager that counts exceptions (no‑op)."""
        class _NoOpCtx:
            def __enter__(self) -> "_NoOpCtx":
                return self

            def __exit__(self, *exc) -> bool:
                return False

        return _NoOpCtx()


def _wrap_metric(prom_cls: Optional[Any]) -> Any:
    """Return the Prometheus metric class or a no‑op stub if unavailable."""
    return prom_cls if prom_cls is not None else _NoOpMetric


# Expose metric types with proper type hints.  Each metric type may
# resolve to either a Prometheus metric class or the no‑op stub.
Counter: Type[Union[_NoOpMetric, _PromCounter]] = _wrap_metric(_PromCounter)
Gauge:   Type[Union[_NoOpMetric, _PromGauge]]   = _wrap_metric(_PromGauge)
Histogram: Type[Union[_NoOpMetric, _PromHistogram]] = _wrap_metric(_PromHistogram)


__all__ = ["Counter", "Gauge", "Histogram"]

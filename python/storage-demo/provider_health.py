from dataclasses import dataclass, field
from threading import Lock


@dataclass
class HealthMetrics:
    successes: int = 0
    failures: int = 0
    latency_samples_ms: list[float] = field(default_factory=list)


class ProviderHealthMonitor:
    def __init__(self):
        self._metrics: dict[str, HealthMetrics] = {}
        self._lock = Lock()

    def record_success(
        self,
        deployment: str,
        latency_ms: float,
    ) -> None:
        with self._lock:
            metrics = self._metrics.setdefault(
                deployment,
                HealthMetrics(),
            )
            metrics.successes += 1
            metrics.latency_samples_ms.append(latency_ms)

    def record_failure(self, deployment: str) -> None:
        with self._lock:
            metrics = self._metrics.setdefault(
                deployment,
                HealthMetrics(),
            )
            metrics.failures += 1

    def failure_rate(self, deployment: str) -> float:
        with self._lock:
            metrics = self._metrics.get(deployment)

            if not metrics:
                return 0.0

            total = metrics.successes + metrics.failures

            return metrics.failures / total if total else 0.0

    def average_latency_ms(self, deployment: str) -> float | None:
        with self._lock:
            metrics = self._metrics.get(deployment)

            if not metrics or not metrics.latency_samples_ms:
                return None

            return (
                sum(metrics.latency_samples_ms)
                / len(metrics.latency_samples_ms)
            )

    def is_healthy(
        self,
        deployment: str,
        max_failure_rate: float = 0.5,
        minimum_samples: int = 5,
    ) -> bool:
        with self._lock:
            metrics = self._metrics.get(deployment)

            if not metrics:
                return True

            total = metrics.successes + metrics.failures

            if total < minimum_samples:
                return True

            return metrics.failures / total < max_failure_rate
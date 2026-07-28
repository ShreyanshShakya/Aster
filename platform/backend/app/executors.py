"""Allowlisted execution backends.

Research planning creates an executor-neutral experiment design.  Only this
module decides which backend is available to receive a plan, preventing an
agent-generated configuration from becoming an arbitrary shell command.
"""
from dataclasses import asdict, dataclass
from app.core.config import get_settings
from app.dmlf_client import health as dmlf_health


@dataclass(frozen=True)
class ExecutorSpec:
    id: str
    label: str
    available: bool
    evidence_mode: str
    description: str


def available_executors() -> list[ExecutorSpec]:
    settings = get_settings()
    dmlf_enabled = False
    dmlf_description = "Disabled until DMLF_ADAPTER_ENABLED=true and DMLF_BRIDGE_ENDPOINT is configured."
    if settings.dmlf_adapter_enabled and settings.dmlf_bridge_endpoint:
        try:
            bridge = dmlf_health()
            nodes = bridge.get("nodes") or []
            requested_nodes = settings.dmlf_requested_nodes
            dmlf_enabled = bridge.get("status") == "ok" and len(nodes) >= requested_nodes
            if bridge.get("status") != "ok":
                dmlf_description = f"Bridge is not ready: {bridge.get('error', bridge.get('status', 'unknown status'))}."
            elif len(nodes) < requested_nodes:
                dmlf_description = f"Waiting for DMLF nodes: {len(nodes)}/{requested_nodes} registered with the manager."
            else:
                dmlf_description = f"{len(nodes)} node(s) registered. Submits bounded plans to the configured DMLF bridge and polls its manager-owned job state."
        except RuntimeError as error:
            dmlf_description = str(error)
    return [
        ExecutorSpec(
            id="local-plan-validation",
            label="Local plan validation",
            available=True,
            evidence_mode="simulated-execution-contract",
            description="Validates the plan-to-worker hand-off and writes artifacts. It does not train a model or produce benchmark metrics.",
        ),
        ExecutorSpec(
            id="dmlf",
            label="DMLF distributed training",
            available=dmlf_enabled,
            evidence_mode="real-training-when-enabled",
            description=dmlf_description,
        ),
    ]


def executor_by_id(executor_id: str) -> ExecutorSpec | None:
    return next((executor for executor in available_executors() if executor.id == executor_id), None)


def serialized_executors() -> list[dict]:
    return [asdict(executor) for executor in available_executors()]

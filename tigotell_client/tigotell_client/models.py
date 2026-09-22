"""Data models for TigoTell's /json endpoint."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TigoPanel:
    """One Tigo optimizer/panel."""

    barcode: str
    pv_node_id: int
    address: int
    voltage_in: float
    voltage_out: float
    current_in: float
    temperature: float
    duty_cycle: int
    rssi: int
    last_updated_ms: int
    last_seen_ms: int | None = None

    @property
    def power(self) -> float:
        """Return instantaneous output power as reported/calculated by TigoTell."""
        return self.voltage_out * self.current_in

    @property
    def signal_strength(self) -> str:
        """Return a qualitative signal level; Tigo's RSSI is not dBm."""
        if self.rssi >= 110:
            return "High"
        if self.rssi >= 80:
            return "Medium"
        return "Low"


@dataclass(frozen=True, slots=True)
class TigoTellData:
    """Snapshot returned by TigoTell."""

    version: str
    fs_version: str
    build_timestamp: str
    uptime_ms: int
    stats: dict[str, int]
    panels: tuple[TigoPanel, ...] = field(default_factory=tuple)


def parse_snapshot(payload: dict[str, Any]) -> TigoTellData:
    """Parse a TigoTell /json response into stable models."""
    if not isinstance(payload, dict):
        raise ValueError("top-level response must be an object")
    nodes_by_id = {
        int(node["pv_node_id"]): node for node in payload.get("nodes", []) if "pv_node_id" in node
    }
    panels: list[TigoPanel] = []
    for raw in payload.get("power", []):
        node_id = int(raw["pv_node_id"])
        node = nodes_by_id.get(node_id, {})
        barcode = str(node.get("barcode") or f"node-{node_id:04d}")
        panels.append(
            TigoPanel(
                barcode=barcode,
                pv_node_id=node_id,
                address=int(raw["address"]),
                voltage_in=float(raw["voltage_in"]),
                voltage_out=float(raw["voltage_out"]),
                current_in=float(raw["current_in"]),
                temperature=float(raw["temperature"]),
                duty_cycle=int(raw["duty_cycle"]),
                rssi=int(raw["rssi"]),
                last_updated_ms=int(raw["last_updated"]),
                last_seen_ms=(
                    int(node["last_seen_ms"]) if node.get("last_seen_ms") is not None else None
                ),
            )
        )
    panels.sort(key=lambda panel: panel.barcode)
    return TigoTellData(
        version=str(payload.get("version", "unknown")),
        fs_version=str(payload.get("fs_version", "unknown")),
        build_timestamp=str(payload.get("build_timestamp", "unknown")),
        uptime_ms=int(payload.get("uptime_ms", 0)),
        stats={str(k): int(v) for k, v in payload.get("stats", {}).items()},
        panels=tuple(panels),
    )

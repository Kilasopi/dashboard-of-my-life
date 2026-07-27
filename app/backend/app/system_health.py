from __future__ import annotations

import os
import platform
from datetime import UTC, datetime
from typing import Literal

import httpx
import psutil
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/system", tags=["system"])

LHM_URL = os.environ.get("LHM_URL", "http://host.docker.internal:8085/data.json")
LHM_TIMEOUT_SECONDS = 2.0

Leaf = tuple[list[str], str, str]


class CpuStats(BaseModel):
    name: str | None = None
    load_percent: float | None = None
    temperature_c: float | None = None
    per_core_load_percent: list[float] = []


class MemoryStats(BaseModel):
    load_percent: float | None = None
    used_gb: float | None = None
    total_gb: float | None = None


class GpuStats(BaseModel):
    name: str
    load_percent: float | None = None
    temperature_c: float | None = None
    memory_used_gb: float | None = None
    memory_total_gb: float | None = None


class StorageStats(BaseModel):
    name: str
    used_percent: float | None = None
    used_gb: float | None = None
    total_gb: float | None = None
    temperature_c: float | None = None


class SystemHealth(BaseModel):
    source: Literal["lhm", "fallback"]
    generated_at: datetime
    message: str | None = None
    cpu: CpuStats
    memory: MemoryStats
    gpu: list[GpuStats] = []
    storage: list[StorageStats] = []


def _parse_value(raw: str | None) -> float | None:
    """LHM values look like '45.0 °C', '23.4 %', '3.4 GB' - pull the leading number out."""
    if not raw or raw == "-":
        return None
    number = ""
    for ch in raw.replace(",", ""):
        if ch.isdigit() or ch in ".-":
            number += ch
        elif number:
            break
    try:
        return float(number)
    except ValueError:
        return None


def _walk(node: dict, path: list[str], leaves: list[Leaf]) -> None:
    text = node.get("Text", "")
    children = node.get("Children") or []
    new_path = [*path, text]
    if children:
        for child in children:
            _walk(child, new_path, leaves)
    else:
        value = node.get("Value")
        if value and value != "-":
            leaves.append((path, text, value))


def _fetch_lhm_leaves() -> list[Leaf] | None:
    try:
        response = httpx.get(LHM_URL, timeout=LHM_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    leaves: list[Leaf] = []
    _walk(response.json(), [], leaves)
    return leaves or None


def _matches(text: str, *keywords: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _device_name(path: list[str], fallback: str) -> str:
    """The hardware node's own name sits above the sensor-type group (Load/Temperatures/...)."""
    return path[-2] if len(path) >= 2 else fallback


def _build_from_lhm(leaves: list[Leaf]) -> SystemHealth:
    cpu = CpuStats()
    memory = MemoryStats()
    gpus: dict[str, GpuStats] = {}
    storages: dict[str, StorageStats] = {}

    for path, name, raw_value in leaves:
        breadcrumb = " > ".join([*path, name]).lower()
        value = _parse_value(raw_value)
        if value is None:
            continue

        if _matches(breadcrumb, "cpu") and not _matches(breadcrumb, "gpu"):
            if cpu.name is None:
                cpu.name = _device_name(path, "CPU")
            if name == "CPU Total" and "load" in breadcrumb:
                cpu.load_percent = value
            elif _matches(name, "cpu package", "core max", "core average", "tdie", "tctl"):
                cpu.temperature_c = value
            elif cpu.temperature_c is None and "temperature" in breadcrumb:
                cpu.temperature_c = value
            elif name.startswith("CPU Core #") and "load" in breadcrumb:
                cpu.per_core_load_percent.append(value)
            continue

        if _matches(breadcrumb, "memory", "ram") and not _matches(breadcrumb, "gpu"):
            if name == "Memory" and "load" in breadcrumb:
                memory.load_percent = value
            elif name == "Memory Used":
                memory.used_gb = value
            elif name == "Memory Available":
                memory.total_gb = round((memory.used_gb or 0) + value, 2)
            continue

        if _matches(breadcrumb, "gpu"):
            gpu_name = _device_name(path, "GPU")
            gpu = gpus.setdefault(gpu_name, GpuStats(name=gpu_name))
            if _matches(name, "gpu core") and "load" in breadcrumb:
                gpu.load_percent = value
            elif _matches(name, "gpu core", "gpu hot spot") and "temperature" in breadcrumb:
                gpu.temperature_c = value
            elif _matches(name, "gpu memory used"):
                gpu.memory_used_gb = value
            elif _matches(name, "gpu memory total") or _matches(name, "gpu memory dedicated"):
                gpu.memory_total_gb = value
            continue

        is_storage = _matches(breadcrumb, "storage", "ssd", "hdd", "nvme")
        if is_storage and not _matches(breadcrumb, "gpu"):
            drive_name = _device_name(path, name)
            storage = storages.setdefault(drive_name, StorageStats(name=drive_name))
            if _matches(name, "used space"):
                storage.used_percent = value
            elif "temperature" in breadcrumb:
                storage.temperature_c = value
            continue

    return SystemHealth(
        source="lhm",
        generated_at=datetime.now(UTC),
        cpu=cpu,
        memory=memory,
        gpu=list(gpus.values()),
        storage=list(storages.values()),
    )


def _is_containerized() -> bool:
    if os.path.exists("/.dockerenv"):
        return True
    try:
        with open("/proc/1/cgroup", encoding="utf-8") as cgroup_file:
            content = cgroup_file.read()
            return any(marker in content for marker in ("docker", "kubepods", "containerd"))
    except OSError:
        return False


def _cpu_name_fallback() -> str | None:
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        )
        name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        return str(name).strip()
    except (ImportError, OSError):
        return platform.processor() or None


def _native_storage() -> list[StorageStats]:
    drives = []
    for part in psutil.disk_partitions(all=False):
        if not part.mountpoint:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except OSError:
            continue
        name = (part.device or part.mountpoint).rstrip("\\/") or part.mountpoint
        drives.append(
            StorageStats(
                name=name,
                used_percent=round(usage.percent, 1),
                used_gb=round(usage.used / (1024**3), 1),
                total_gb=round(usage.total / (1024**3), 1),
            )
        )
    return drives


def _build_fallback() -> SystemHealth:
    containerized = _is_containerized()

    per_core = psutil.cpu_percent(interval=0.1, percpu=True)
    cpu = CpuStats(
        name=_cpu_name_fallback(),
        load_percent=round(sum(per_core) / len(per_core), 1) if per_core else None,
        per_core_load_percent=per_core,
    )
    vm = psutil.virtual_memory()
    memory = MemoryStats(
        load_percent=vm.percent,
        used_gb=round((vm.total - vm.available) / (1024**3), 2),
        total_gb=round(vm.total / (1024**3), 2),
    )
    if containerized:
        message = (
            "LibreHardwareMonitor isn't reachable, so this is only approximate CPU/memory "
            "for the backend's own container - not your real drives or temperatures. Run "
            "LibreHardwareMonitor on this PC with Options > Remote Web Server enabled "
            "(default port 8085) for accurate host stats, temperatures, storage, and GPU data."
        )
    else:
        message = (
            "LibreHardwareMonitor isn't reachable, so temperatures and GPU stats aren't "
            "available. Run LibreHardwareMonitor on this PC with Options > Remote Web Server "
            "enabled (default port 8085) for full sensor data."
        )

    return SystemHealth(
        source="fallback",
        generated_at=datetime.now(UTC),
        message=message,
        cpu=cpu,
        memory=memory,
    )


@router.get("/health", response_model=SystemHealth)
def get_system_health() -> SystemHealth:
    leaves = _fetch_lhm_leaves()
    health = _build_from_lhm(leaves) if leaves else _build_fallback()

    # Drive letters + real used/total GB (psutil) beat LHM's physical-disk,
    # percent-only view whenever we can actually see the host filesystem.
    if not _is_containerized():
        health.storage = _native_storage()

    return health


@router.get("/raw")
def get_raw_sensors() -> dict:
    """Flattened LHM sensor dump for debugging sensor names on your specific hardware."""
    leaves = _fetch_lhm_leaves()
    if not leaves:
        return {"available": False, "sensors": []}
    return {
        "available": True,
        "sensors": [{"path": path, "name": name, "value": value} for path, name, value in leaves],
    }

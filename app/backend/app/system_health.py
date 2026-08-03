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

LHM_URL = os.environ.get("LHM_URL", "http://localhost:8085/data.json")
LHM_TIMEOUT_SECONDS = 2.0

# (hardware_id, device_name, sensor_type, sensor_name, raw_value) - HardwareId/Type come
# straight from LHM's own JSON, e.g. "/amdcpu/0" + Type "Temperature", far more reliable
# than guessing from display text (which is how "CPU I/O" - a motherboard voltage rail -
# used to get mistaken for a CPU sensor).
Leaf = tuple[str | None, str | None, str | None, str, str]


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


def _walk(
    node: dict,
    hardware_id: str | None,
    device_name: str | None,
    leaves: list[Leaf],
) -> None:
    if "HardwareId" in node:
        hardware_id = node["HardwareId"]
        device_name = node.get("Text")

    children = node.get("Children") or []
    if children:
        for child in children:
            _walk(child, hardware_id, device_name, leaves)
        return

    value = node.get("Value")
    if value and value != "-":
        leaves.append((hardware_id, device_name, node.get("Type"), node.get("Text", ""), value))


def _fetch_lhm_leaves() -> list[Leaf] | None:
    try:
        response = httpx.get(LHM_URL, timeout=LHM_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    leaves: list[Leaf] = []
    _walk(response.json(), None, None, leaves)
    return leaves or None


def _build_from_lhm(leaves: list[Leaf]) -> SystemHealth:
    cpu = CpuStats()
    memory = MemoryStats()
    gpus: dict[str, GpuStats] = {}
    storages: dict[str, StorageStats] = {}
    storage_free_gb: dict[str, float] = {}

    for hardware_id, device_name, sensor_type, name, raw_value in leaves:
        if not hardware_id:
            continue
        value = _parse_value(raw_value)
        if value is None:
            continue

        if hardware_id.startswith(("/amdcpu", "/intelcpu")):
            if cpu.name is None:
                cpu.name = device_name
            if name == "CPU Total" and sensor_type == "Load":
                cpu.load_percent = value
            elif name.startswith("CPU Core #") and sensor_type == "Load":
                cpu.per_core_load_percent.append(value)
            elif sensor_type == "Temperature" and cpu.temperature_c is None:
                cpu.temperature_c = value
            continue

        if hardware_id == "/ram":
            if name == "Memory" and sensor_type == "Load":
                memory.load_percent = value
            elif name == "Memory Used" and sensor_type == "Data":
                memory.used_gb = value
            elif name == "Memory Available" and sensor_type == "Data":
                memory.total_gb = round((memory.used_gb or 0) + value, 2)
            continue

        if hardware_id.startswith("/gpu-"):
            gpu = gpus.setdefault(hardware_id, GpuStats(name=device_name or "GPU"))
            if name == "GPU Core" and sensor_type == "Load":
                gpu.load_percent = value
            elif (
                sensor_type == "Temperature"
                and name in ("GPU Core", "GPU Hot Spot")
                and gpu.temperature_c is None
            ):
                gpu.temperature_c = value
            elif name == "GPU Memory Used" and sensor_type == "SmallData":
                gpu.memory_used_gb = round(value / 1024, 2)
            elif name == "GPU Memory Total" and sensor_type == "SmallData":
                gpu.memory_total_gb = round(value / 1024, 2)
            continue

        if hardware_id.startswith(("/hdd", "/nvme", "/ssd")):
            default_name = device_name or hardware_id
            storage = storages.setdefault(hardware_id, StorageStats(name=default_name))
            if name == "Used Space" and sensor_type == "Load":
                storage.used_percent = value
            elif name == "Total Space" and sensor_type == "Data":
                storage.total_gb = value
            elif name == "Free Space" and sensor_type == "Data":
                storage_free_gb[hardware_id] = value
            elif sensor_type == "Temperature" and name in ("Temperature", "Composite Temperature"):
                storage.temperature_c = value
            continue

    for hardware_id, storage in storages.items():
        free_gb = storage_free_gb.get(hardware_id)
        if storage.total_gb is not None and free_gb is not None:
            storage.used_gb = round(storage.total_gb - free_gb, 1)

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


def _cpu_name_linux() -> str | None:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as cpuinfo_file:
            for line in cpuinfo_file:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return None


def _cpu_temperature_linux(temps: dict[str, list]) -> float | None:
    # coretemp (Intel) / k10temp or zenpower (AMD) expose an overall package/die
    # reading first; fall back to averaging whatever a chip reports.
    for chip in ("coretemp", "k10temp", "zenpower"):
        entries = temps.get(chip)
        if not entries:
            continue
        for entry in entries:
            if entry.label in ("Package id 0", "Tdie", "Tctl"):
                return entry.current
        return entries[0].current
    return None


def _gpu_temperature_linux(temps: dict[str, list]) -> float | None:
    for chip in ("amdgpu", "nouveau"):
        entries = temps.get(chip)
        if entries:
            return entries[0].current
    return None


def _nvidia_gpu_linux() -> GpuStats | None:
    import shutil
    import subprocess

    if not shutil.which("nvidia-smi"):
        return None
    try:
        output = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=True,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None

    first_line = output.splitlines()[0] if output else ""
    parts = [part.strip() for part in first_line.split(",")]
    if len(parts) != 5:
        return None
    name, load, temp, mem_used, mem_total = parts
    return GpuStats(
        name=name,
        load_percent=_parse_value(load),
        temperature_c=_parse_value(temp),
        memory_used_gb=round(float(mem_used) / 1024, 2) if mem_used.replace(".", "", 1).isdigit() else None,
        memory_total_gb=round(float(mem_total) / 1024, 2) if mem_total.replace(".", "", 1).isdigit() else None,
    )


def _apply_storage_temperatures_linux(storage: list[StorageStats], temps: dict[str, list]) -> None:
    # NVMe controllers expose their own composite temperature via hwmon without
    # needing smartctl/root; SATA/SSD drives generally don't without smartctl.
    nvme_entries = temps.get("nvme")
    if not nvme_entries:
        return
    composite = next((e.current for e in nvme_entries if e.label == "Composite"), nvme_entries[0].current)
    for drive in storage:
        if "nvme" in drive.name.lower():
            drive.temperature_c = composite


def _build_native_linux() -> SystemHealth:
    per_core = psutil.cpu_percent(interval=0.1, percpu=True)
    temps: dict[str, list] = {}
    try:
        temps = psutil.sensors_temperatures() or {}
    except (AttributeError, OSError):
        pass

    cpu = CpuStats(
        name=_cpu_name_linux(),
        load_percent=round(sum(per_core) / len(per_core), 1) if per_core else None,
        per_core_load_percent=per_core,
        temperature_c=_cpu_temperature_linux(temps),
    )
    vm = psutil.virtual_memory()
    memory = MemoryStats(
        load_percent=vm.percent,
        used_gb=round((vm.total - vm.available) / (1024**3), 2),
        total_gb=round(vm.total / (1024**3), 2),
    )

    gpus: list[GpuStats] = []
    nvidia_gpu = _nvidia_gpu_linux()
    if nvidia_gpu:
        gpus.append(nvidia_gpu)
    else:
        amd_temp = _gpu_temperature_linux(temps)
        if amd_temp is not None:
            gpus.append(GpuStats(name="GPU", temperature_c=amd_temp))

    storage = _native_storage()
    _apply_storage_temperatures_linux(storage, temps)

    return SystemHealth(
        source="fallback",
        generated_at=datetime.now(UTC),
        message=None if temps else (
            "No hwmon temperature sensors were found. Install/load your CPU's sensor "
            "driver (e.g. `sudo sensors-detect` from lm-sensors) for temperature data."
        ),
        cpu=cpu,
        memory=memory,
        gpu=gpus,
        storage=storage,
    )


def _build_fallback() -> SystemHealth:
    if platform.system() == "Linux" and not _is_containerized():
        return _build_native_linux()

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
    if leaves:
        health = _build_from_lhm(leaves)
        # psutil re-enumerates whatever Windows currently has mounted on every request, so
        # it picks up drives you plug in or remove without a restart - and it's the only
        # source that reliably sees new external drives at all (LHM's SMART-based storage
        # list often can't see removable media through a USB bridge chip). Prefer it
        # whenever we can see the real filesystem; LHM's physical-disk view (with temps)
        # is only used as a last resort when the backend is sandboxed in a container.
        if not _is_containerized():
            health.storage = _native_storage()
    else:
        # On Linux, _build_fallback already does its own native storage read (with
        # hwmon temps attached) - overwriting it here would drop those temps.
        health = _build_fallback()

    return health


@router.get("/raw")
def get_raw_sensors() -> dict:
    """Flattened LHM sensor dump for debugging sensor names on your specific hardware."""
    leaves = _fetch_lhm_leaves()
    if not leaves:
        return {"available": False, "sensors": []}
    return {
        "available": True,
        "sensors": [
            {"hardware_id": hid, "device": device, "type": typ, "name": name, "value": value}
            for hid, device, typ, name, value in leaves
        ],
    }

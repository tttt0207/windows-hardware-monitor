from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable, TypeVar

import psutil
import pynvml
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request


BASE_DIR = Path(__file__).resolve().parent
BYTES_PER_GIB = 1024**3
BYTES_PER_MIB = 1024**2
T = TypeVar("T")

nvml_ready = False


def round_number(value: float, digits: int = 1) -> float:
    return round(float(value), digits)


def bytes_to_gib(value: int) -> float:
    return round_number(value / BYTES_PER_GIB, 2)


def bytes_to_mib(value: int) -> float:
    return round_number(value / BYTES_PER_MIB, 1)


def safe_nvml_call(
    reader: Callable[[], T],
    converter: Callable[[T], Any] | None = None,
) -> Any:
    """单独保护每一次 NVML 读取；失败时只返回 None。"""
    try:
        value = reader()
        if value is None:
            return None
        return converter(value) if converter else value
    except (
        pynvml.NVMLError,
        OSError,
        TypeError,
        ValueError,
        AttributeError,
        OverflowError,
    ):
        return None


def init_nvml() -> None:
    """启动时尝试初始化 NVML；没有 NVIDIA 环境也不影响服务启动。"""
    global nvml_ready

    try:
        pynvml.nvmlInit()
        device_count = pynvml.nvmlDeviceGetCount()
        if device_count < 1:
            pynvml.nvmlShutdown()
            nvml_ready = False
            return
        nvml_ready = True
    except (pynvml.NVMLError, OSError):
        nvml_ready = False


def shutdown_nvml() -> None:
    global nvml_ready

    if not nvml_ready:
        return

    try:
        pynvml.nvmlShutdown()
    except pynvml.NVMLError:
        pass
    finally:
        nvml_ready = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_nvml()
    # 预热 psutil，避免第一次请求的 CPU 采样值不准确。
    psutil.cpu_percent(interval=None)
    yield
    shutdown_nvml()


app = FastAPI(title="Windows 本地硬件监控", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def get_system_data() -> dict[str, Any]:
    """读取运行本服务的 Windows 电脑的 CPU 与内存状态。"""
    memory = psutil.virtual_memory()
    return {
        "cpu": {
            "usage_percent": round_number(psutil.cpu_percent(interval=None)),
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
        },
        "memory": {
            "total_gib": bytes_to_gib(memory.total),
            "used_gib": bytes_to_gib(memory.used),
            "available_gib": bytes_to_gib(memory.available),
            "usage_percent": round_number(memory.percent),
        },
    }


def get_process_name(pid: int) -> str | None:
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def convert_process_memory(value: Any) -> float | None:
    """某些 Windows 驱动用超大整数表示“不支持”，统一转为 None。"""
    memory_bytes = int(value)
    if memory_bytes < 0 or memory_bytes >= 2**63:
        return None
    return bytes_to_mib(memory_bytes)


def get_gpu_processes(handle: Any) -> list[dict[str, Any]]:
    """合并计算进程和图形进程；单进程显存不可读时保留 null。"""
    processes_by_pid: dict[int, dict[str, Any]] = {}

    query_names = (
        "nvmlDeviceGetComputeRunningProcesses",
        "nvmlDeviceGetGraphicsRunningProcesses",
    )

    for query_name in query_names:
        query = getattr(pynvml, query_name, None)
        if query is None:
            continue

        running_processes = safe_nvml_call(lambda query=query: query(handle))
        if not running_processes:
            continue

        for process in running_processes:
            pid = safe_nvml_call(lambda: process.pid, int)
            if pid is None:
                continue

            used_memory = safe_nvml_call(
                lambda: process.usedGpuMemory,
                convert_process_memory,
            )
            entry = processes_by_pid.setdefault(
                pid,
                {
                    "pid": pid,
                    "name": get_process_name(pid),
                    "gpu_memory_mib": None,
                },
            )

            if used_memory is not None:
                current = entry["gpu_memory_mib"]
                entry["gpu_memory_mib"] = max(current or 0.0, used_memory)

    return sorted(
        processes_by_pid.values(),
        key=lambda item: item["gpu_memory_mib"] or 0.0,
        reverse=True,
    )


def empty_gpu_device(index: int) -> dict[str, Any]:
    return {
        "index": index,
        "name": None,
        "usage_percent": None,
        "temperature_c": None,
        "memory": {
            "total_gib": None,
            "used_gib": None,
            "free_gib": None,
            "usage_percent": None,
        },
        "processes": [],
    }


def get_gpu_device(index: int) -> dict[str, Any]:
    """读取单块 GPU。每个字段独立失败，保持设备 JSON 结构稳定。"""
    device = empty_gpu_device(index)
    handle = safe_nvml_call(lambda: pynvml.nvmlDeviceGetHandleByIndex(index))
    if handle is None:
        return device

    name = safe_nvml_call(lambda: pynvml.nvmlDeviceGetName(handle))
    if isinstance(name, bytes):
        name = name.decode("utf-8", errors="replace")
    device["name"] = name

    device["usage_percent"] = safe_nvml_call(
        lambda: pynvml.nvmlDeviceGetUtilizationRates(handle).gpu,
        round_number,
    )
    device["temperature_c"] = safe_nvml_call(
        lambda: pynvml.nvmlDeviceGetTemperature(
            handle,
            pynvml.NVML_TEMPERATURE_GPU,
        ),
        int,
    )

    # 显存对象本身以及其中每个字段都分别保护。
    memory = safe_nvml_call(lambda: pynvml.nvmlDeviceGetMemoryInfo(handle))
    if memory is not None:
        total_bytes = safe_nvml_call(lambda: memory.total, int)
        used_bytes = safe_nvml_call(lambda: memory.used, int)
        free_bytes = safe_nvml_call(lambda: memory.free, int)

        device["memory"]["total_gib"] = (
            bytes_to_gib(total_bytes) if total_bytes is not None else None
        )
        device["memory"]["used_gib"] = (
            bytes_to_gib(used_bytes) if used_bytes is not None else None
        )
        device["memory"]["free_gib"] = (
            bytes_to_gib(free_bytes) if free_bytes is not None else None
        )
        device["memory"]["usage_percent"] = (
            round_number(used_bytes / total_bytes * 100)
            if used_bytes is not None and total_bytes
            else None
        )

    device["processes"] = get_gpu_processes(handle)
    return device


def get_gpu_data() -> dict[str, Any]:
    """始终返回 available、message、devices 三个字段。"""
    if not nvml_ready:
        return {
            "available": False,
            "message": "未检测到 NVIDIA 显卡",
            "devices": [],
        }

    device_count = safe_nvml_call(pynvml.nvmlDeviceGetCount, int)
    if not device_count:
        return {
            "available": False,
            "message": "未检测到 NVIDIA 显卡",
            "devices": [],
        }

    return {
        "available": True,
        "message": "",
        "devices": [get_gpu_device(index) for index in range(device_count)],
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/hardware")
async def hardware_info() -> dict[str, Any]:
    return {
        **get_system_data(),
        "gpu": get_gpu_data(),
    }


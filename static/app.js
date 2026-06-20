const REFRESH_INTERVAL_MS = 1000;

const elements = {
    cpuValue: document.querySelector("#cpu-value"),
    cpuBar: document.querySelector("#cpu-bar"),
    cpuCores: document.querySelector("#cpu-cores"),
    memoryValue: document.querySelector("#memory-value"),
    memoryBar: document.querySelector("#memory-bar"),
    memoryUsed: document.querySelector("#memory-used"),
    memoryAvailable: document.querySelector("#memory-available"),
    memoryTotal: document.querySelector("#memory-total"),
    statusDot: document.querySelector("#status-dot"),
    connectionText: document.querySelector("#connection-text"),
    lastUpdated: document.querySelector("#last-updated"),
    gpuUnavailable: document.querySelector("#gpu-unavailable"),
    gpuEmptyTitle: document.querySelector("#gpu-empty-title"),
    gpuEmptyMessage: document.querySelector("#gpu-empty-message"),
    gpuList: document.querySelector("#gpu-list"),
    gpuTemplate: document.querySelector("#gpu-template"),
};

function isMissing(value) {
    return value === null || value === undefined;
}

function clampPercent(value) {
    if (isMissing(value) || Number.isNaN(Number(value))) {
        return 0;
    }
    return Math.min(100, Math.max(0, Number(value)));
}

function setProgress(element, value) {
    element.style.width = `${clampPercent(value)}%`;
}

function formatNumber(value, digits = 1) {
    return isMissing(value) ? "不可用" : Number(value).toFixed(digits);
}

function formatPercent(value) {
    return isMissing(value) ? "不可用" : `${formatNumber(value)}%`;
}

function formatStorage(value, unit) {
    return isMissing(value) ? "不可用" : `${value} ${unit}`;
}

function setConnection(isOnline) {
    elements.statusDot.classList.toggle("online", isOnline);
    elements.statusDot.classList.toggle("offline", !isOnline);
    elements.connectionText.textContent = isOnline ? "实时连接" : "连接中断";
}

// CPU 和内存由 psutil 提供；这里只负责更新页面，不参与 GPU 容错。
function renderSystem(data) {
    elements.cpuValue.textContent = formatPercent(data.cpu.usage_percent);
    setProgress(elements.cpuBar, data.cpu.usage_percent);

    const physical = data.cpu.physical_cores ?? "不可用";
    const logical = data.cpu.logical_cores ?? "不可用";
    elements.cpuCores.textContent =
        `${physical} 个物理核心 · ${logical} 个逻辑处理器`;

    elements.memoryValue.textContent = formatPercent(data.memory.usage_percent);
    elements.memoryUsed.textContent = formatStorage(data.memory.used_gib, "GiB");
    elements.memoryAvailable.textContent =
        formatStorage(data.memory.available_gib, "GiB");
    elements.memoryTotal.textContent = formatStorage(data.memory.total_gib, "GiB");
    setProgress(elements.memoryBar, data.memory.usage_percent);
}

function createProcessRow(process) {
    const row = document.createElement("tr");
    const nameCell = document.createElement("td");
    const pidCell = document.createElement("td");
    const memoryCell = document.createElement("td");

    nameCell.textContent = process?.name ?? "不可用";
    pidCell.textContent = process?.pid ?? "不可用";
    // Windows 笔记本驱动可能不向 NVML 提供单进程显存。
    memoryCell.textContent = isMissing(process?.gpu_memory_mib)
        ? "NVML 未提供"
        : `${formatNumber(process.gpu_memory_mib)} MiB`;

    row.append(nameCell, pidCell, memoryCell);
    return row;
}

function createGpuPanel(gpu) {
    const panel = elements.gpuTemplate.content.firstElementChild.cloneNode(true);
    const memory = gpu?.memory ?? {};
    const processes = Array.isArray(gpu?.processes) ? gpu.processes : [];

    panel.querySelector(".gpu-index").textContent =
        isMissing(gpu?.index) ? "GPU" : `GPU ${gpu.index}`;
    panel.querySelector(".gpu-name").textContent = gpu?.name ?? "不可用";
    panel.querySelector(".temperature-value").textContent =
        isMissing(gpu?.temperature_c) ? "不可用" : `${gpu.temperature_c}°C`;
    panel.querySelector(".gpu-usage-value").textContent =
        formatPercent(gpu?.usage_percent);
    panel.querySelector(".vram-usage-value").textContent =
        formatPercent(memory.usage_percent);
    panel.querySelector(".vram-detail").textContent =
        `已用 ${formatStorage(memory.used_gib, "GiB")} / ` +
        `总量 ${formatStorage(memory.total_gib, "GiB")}`;

    setProgress(panel.querySelector(".gpu-usage-bar"), gpu?.usage_percent);
    setProgress(panel.querySelector(".vram-usage-bar"), memory.usage_percent);

    const processList = panel.querySelector(".process-list");
    const noProcesses = panel.querySelector(".no-processes");
    panel.querySelector(".process-count").textContent = `${processes.length} 个进程`;

    if (processes.length > 0) {
        noProcesses.classList.add("hidden");
        processes.forEach((process) => {
            processList.appendChild(createProcessRow(process));
        });
    }

    return panel;
}

// 支持 devices 数组中的所有 NVIDIA GPU；字段缺失不会被当作请求失败。
function renderGpu(gpuData) {
    elements.gpuList.replaceChildren();

    if (!gpuData?.available) {
        elements.gpuUnavailable.classList.remove("hidden");
        elements.gpuEmptyTitle.textContent = "未检测到 NVIDIA 显卡";
        elements.gpuEmptyMessage.textContent = "CPU 和内存监控仍会正常工作。";
        return;
    }

    const devices = Array.isArray(gpuData.devices) ? gpuData.devices : [];
    if (devices.length === 0) {
        elements.gpuUnavailable.classList.remove("hidden");
        elements.gpuEmptyTitle.textContent = "未检测到 GPU 设备";
        elements.gpuEmptyMessage.textContent = "NVIDIA 服务可用，但没有返回设备。";
        return;
    }

    elements.gpuUnavailable.classList.add("hidden");
    devices.forEach((gpu) => {
        elements.gpuList.appendChild(createGpuPanel(gpu));
    });
}

async function refreshHardware() {
    try {
        const response = await fetch("/api/hardware", { cache: "no-store" });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        renderSystem(data);
        renderGpu(data.gpu);
        setConnection(true);
        elements.lastUpdated.textContent =
            `最后更新 ${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`;
    } catch (error) {
        // 只有整个 HTTP 请求失败时，才进入连接中断状态。
        console.error("硬件数据刷新失败：", error);
        setConnection(false);
        elements.lastUpdated.textContent = "数据刷新失败";
    }
}

refreshHardware();
setInterval(refreshHardware, REFRESH_INTERVAL_MS);

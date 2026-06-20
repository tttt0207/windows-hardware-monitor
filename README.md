# Windows 本地硬件监控

这是一个使用 FastAPI、HTML、CSS 和 JavaScript 编写的 Windows 本地硬件监控网页。页面每秒刷新一次，可显示 CPU、内存以及 NVIDIA GPU 的实时状态。

> 页面显示的是**运行这个项目后端的那台电脑**的硬件状态。把项目复制到另一台 Windows 电脑并在那里运行后，显示的就是那台电脑的数据。

## 功能

- CPU 使用率、物理核心数、逻辑核心数
- 内存总量、已用内存、可用内存、内存使用率
- 支持多块 NVIDIA GPU
- GPU 型号、使用率、温度
- 显存总量、已用、可用和使用率
- 正在使用 GPU 的进程及其显存占用
- 没有 NVIDIA GPU、驱动不支持某项指标时仍能正常运行

## 系统要求

- Windows 10 或 Windows 11
- Python 3.10 或更高版本
- 如需监控 NVIDIA GPU，需要安装可正常工作的 NVIDIA 显卡驱动

安装 Python 时建议勾选 **Add Python to PATH**。

## 最简单的启动方式

双击项目目录中的 `run.bat`。

它会自动：

1. 创建 `.venv` 虚拟环境（如果尚不存在）。
2. 激活虚拟环境。
3. 安装或检查 `requirements.txt` 中的依赖。
4. 在 `127.0.0.1:8000` 启动网站。
5. 等待服务启动成功后，自动使用默认浏览器打开监控页面。

正常情况下浏览器会自动打开。如果没有自动打开，也可以手动访问：

```text
http://127.0.0.1:8000
```

不要关闭运行 `run.bat` 的命令窗口；关闭窗口或按 `Ctrl+C` 会停止服务。

## 使用命令手动运行

在项目文件夹空白处按住 Shift 并单击鼠标右键，选择“在此处打开 PowerShell”，然后运行：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

如果 PowerShell 阻止激活脚本，也可以不激活，直接运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

停止服务时，在命令窗口按 `Ctrl+C`。如果已激活虚拟环境，还可以运行 `deactivate` 退出虚拟环境。

## 复制到其他 Windows 电脑

1. 复制整个 `hardware_monitor` 文件夹。
2. 不需要复制旧电脑上的 `.venv`；虚拟环境与具体电脑相关。
3. 在新电脑安装 Python 3.10 或更高版本。
4. 双击新电脑项目目录中的 `run.bat`。
5. 打开 `http://127.0.0.1:8000`。

程序不会使用原电脑的用户名、路径、CPU 或 GPU 型号。所有硬件数据都在后端运行时从当前电脑读取。

## API

实时数据接口：

```text
GET /api/hardware
```

没有 NVIDIA GPU 时，GPU 部分保持稳定结构：

```json
{
  "available": false,
  "message": "未检测到 NVIDIA 显卡",
  "devices": []
}
```

## 局域网访问（可选）

默认命令：

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

默认只允许本机通过以下地址访问：

```text
http://127.0.0.1:8000
```

如果想让同一 WiFi 或局域网中的其他设备访问，可以在项目目录运行：

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

然后在其他设备浏览器中访问运行后端电脑的局域网 IP，例如：

```text
http://192.168.1.23:8000
```

可以在 Windows 中运行 `ipconfig`，查看当前网卡的 IPv4 地址。Windows 防火墙可能会询问是否允许 Python 通过网络，请只在可信的私人网络中放行。

> 即使由手机或另一台电脑访问，页面显示的仍然是**运行 FastAPI 后端的那台电脑**的状态，不是访问者设备的状态。

## 常见问题

### 127.0.0.1 拒绝连接怎么办？

- 确认运行窗口没有被关闭。
- 查看窗口中是否出现 Python、依赖安装或端口错误。
- 确认访问的是 `http://127.0.0.1:8000`，不是 `https://`。
- 重新双击 `run.bat`，等待出现 Uvicorn 启动成功提示。

### 没有 NVIDIA 显卡怎么办？

页面会显示“未检测到 NVIDIA 显卡”，CPU 和内存监控仍可正常使用。这是正常情况，不需要额外处理。

如果电脑确实有 NVIDIA GPU，但仍未检测到，请先安装或更新 NVIDIA 官方驱动并重启电脑。

### GPU 进程显存显示“NVML 未提供”怎么办？

部分 Windows 笔记本、混合显卡模式或驱动版本不会通过 NVML 提供单个进程的显存值。这不代表程序出错；GPU 总显存和总体使用率通常仍可读取。

### 端口 8000 被占用怎么办？

改用其他端口，例如：

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8001
```

然后访问：

```text
http://127.0.0.1:8001
```

也可以关闭已经占用 8000 端口的其他程序。

### 为什么 GPU 使用率和任务管理器不完全一样？

NVML 与 Windows 任务管理器可能使用不同的采样时刻、刷新周期和 GPU 引擎统计方式。短时间内数值不完全一致是正常现象，应关注整体趋势而不是某一秒的精确一致。

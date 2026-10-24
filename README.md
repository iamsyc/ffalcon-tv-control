# FFALCON TV Control

雷鸟电视的 macOS 控制工具，提供局域网 ADB 连接、实时画面、应用管理和遥控操作。

已验证的主要成果：

- **将电视自带 ADB 开关启用的随机端口切换到固定的 `5555`**，保存连接地址，日常自动重连。
- 在缺少配对入口、没有可用 USB 调试连接的实测电视上，通过局域网完成首次 ADB 授权，取得 `device` 状态和 `uid=2000(shell)`。
- 查看电视实时画面，用鼠标、滚轮和键盘操作；修复 TCL 桌面的点击和滚轮输入。
- 搜索和打开应用、安装 APK、遥控方向与音量、截图、导出 Android 设置和厂商配置。安装已验证同版本诊断 APK 的覆盖安装。

## 软件界面

日常打开“电视控制台”，点击“实时画面”启动“客厅电视”。两个应用共用连接配置与 ADB 密钥，需放在同一目录。

### 电视控制台

![电视控制台](docs/images/console.png)

### 客厅电视实时画面

![客厅电视实时画面](docs/images/realtime.png)

## 已验证电视

| 项目 | 实测环境 |
| --- | --- |
| 电视 | 雷鸟 75S595C Ultra，系统型号 TCL Smart TV Pro |
| 系统 | Android 14 / API 34 |
| 固件 | `V8-0015T11-LF1V487.001917` |
| 屏幕 | 物理 3840×2160，实测逻辑坐标 1920×1080 |

其他雷鸟型号、其他固件、TCL 品牌及其他品牌电视均未测试，不声明支持。功能验证结果见[验证记录](docs/validation.md)。

## 电视端 APK 下载与安装

下载 [电视调试诊断 v9 APK](https://github.com/iamsyc/ffalcon-tv-control/releases/download/v0.1.0/tv-debug-entry-v9.apk)，无需自行编译。版本详情和 SHA-256 校验文件见 [v0.1.0 Release](https://github.com/iamsyc/ffalcon-tv-control/releases/tag/v0.1.0)。电视端要求 Android 14 或更高，已验证型号见上表。

1. 将 APK 复制到 U 盘，插入电视。
2. 用电视的文件管理或 U 盘安装入口打开 APK，按电视提示允许安装并完成确认。
3. 在电视应用列表打开“电视调试入口检查”，进入“电视调试诊断 v9”。
4. 需要首次局域网授权时，开启“允许电脑操作设置和运行本工具权限内的命令”，按 [ADB 授权说明](docs/adb-authorization.md)操作。

若覆盖安装提示签名冲突，需先卸载旧版再安装；卸载会清空诊断配置。ADB 授权完成后，日常控制无需持续打开电视端应用。

## 使用 macOS 控制台

macOS 控制台需在本机准备依赖并构建。

1. 电脑与电视连接同一局域网，在电视设置中开启 ADB，记录 IP 和当前随机端口。
2. 按[构建说明](docs/build.md)准备 Python 3.12+、Android SDK、ADB、scrcpy 5.0.1 和 macOS 编译工具，构建应用：

```sh
python3 tools/build.py server
python3 tools/build.py macos
```

3. 创建本机连接配置和独立 ADB 密钥，将示例 IP、端口替换为电视当前值：

```sh
python3 tools/tvctl.py init --host 192.0.2.10 --port 34961
```

4. 按[快速开始](docs/quick-start.md)完成电视授权。实测固件缺少授权弹窗和配对入口时，使用[固件专用授权流程](docs/adb-authorization.md)。该流程通过 `IpelEngine` 配置让系统服务写入电脑公钥，再恢复原始配置，无需 root 或刷机。**此流程会替换已有电脑的 ADB 授权，无法恢复旧公钥列表。** 本机项目密钥已获授权时跳过此步。
5. 连接电视，自动切换到 `5555`，打开控制台：

```sh
python3 tools/tvctl.py connect
python3 tools/tvctl.py status
python3 tools/tvctl.py adb shell id
open .build/apps/电视控制台.app
```

`status` 应返回 `device`，`id` 应返回 `uid=2000(shell)`。

## ADB 随机端口如何切换到 5555

实测电视自带设置开启的 ADB 使用随机端口，重新开启后可能变化。`connect` 按以下步骤恢复固定端口：

1. 先尝试电视的 `5555`，再尝试保存的端口；连接失败时，通过 mDNS 查找同一 IP 的 ADB 服务。
2. 确认连接状态为 `device` 后，在当前随机端口上执行 `adb -s 电视IP:当前端口 tcpip 5555`，让电视的 adbd 重启并监听 `5555`。
3. 重新连接 `电视IP:5555`，确认状态为 `device`，再保存地址供控制台和实时窗口共用。

该操作需要已获授权的 ADB 连接，切换时会短暂断连。设置作用于当前运行的服务；电视重启后保持 `5555` 尚未验证。重启或重新开启 ADB 后若恢复随机端口，再运行 `connect`；自动发现失败时传入电视当前显示的端口：

```sh
python3 tools/tvctl.py connect --port 41783
```

实现见 [runtime/tv_connection.py](runtime/tv_connection.py)。

## 详细文档

| 内容 | 入口 |
| --- | --- |
| 连接与日常操作 | [快速开始](docs/quick-start.md) |
| 首次授权与配置恢复 | [ADB 授权](docs/adb-authorization.md) |
| 构建与安装 | [构建说明](docs/build.md) |
| 端口、证书及安装问题 | [故障排查](docs/troubleshooting.md) |
| 实现原理 | [架构](docs/architecture.md)、[研究记录](docs/research.md) |

[Apache-2.0](LICENSE)。ADB 仅在受控局域网使用，不向公网开放调试端口。

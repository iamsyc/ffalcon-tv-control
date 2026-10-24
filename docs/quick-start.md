# 快速开始

## 准备

电脑和电视连接同一局域网。记录电视设置中显示的 IP 和当前 ADB 端口，保持电视开机。ADB 开关关闭后重新开启可能改变端口，该端口与无线调试的配对端口含义不同。

按[构建说明](build.md)生成需要的组件。所有命令从仓库根目录运行。文档中的 `192.0.2.10` 是示例地址，不能直接用于连接。

## 创建独立电脑身份

```sh
python3 tools/tvctl.py doctor
python3 tools/tvctl.py init --host 192.0.2.10 --port 34961
```

`init` 只创建本机文件，不修改电视：

```text
~/Library/Application Support/TVControl/
  connection.json
  keys/adbkey
  keys/adbkey.pub
```

项目按状态目录和密钥分配独立的本机 ADB Unix socket，不占用固定 TCP 端口。ADB 子进程使用专用身份目录，只加载配置中的原密钥；终端继承的 `ADB_VENDOR_KEYS` 和 `ADB_SERVER_SOCKET` 不会改变连接身份。保留私钥，避免以后重装电脑时失去身份。`init` 不覆盖已有配置。

## 完成首次授权

根据电视提供的入口选择流程：

1. **有 RSA 授权弹窗**：使用项目密钥尝试连接，在电视上核对并允许当前电脑。
2. **有“无线调试 → 使用配对码配对设备”**：运行以下命令，按提示输入电视提供的配对码。配对地址和连接地址分别取自电视页面。
3. **只有 ADB 开关，没有授权或配对入口**：符合实测固件条件时，执行[固件专用授权](adb-authorization.md)。

```sh
# 仅适用于电视确实提供六位配对码的情况
python3 tools/tvctl.py adb pair 192.0.2.10:37123

# 使用电视显示的连接端口
python3 tools/tvctl.py connect --port 34961
```

标准配对的上游说明见 [Android ADB 文档](https://developer.android.com/tools/adb#connect-to-a-device-over-wi-fi)。仅显示 IP 和端口的 ADB 开关不代表电视提供了配对服务。

`tvctl.py adb ...` 直接连接当前终端的标准输入、输出和错误，配对提示会实时显示，也可运行 `python3 tools/tvctl.py adb shell` 进入交互 shell。该透传命令没有固定会话时限；内部连接检查仍使用各自的超时。

## 验证连接

```sh
python3 tools/tvctl.py connect
python3 tools/tvctl.py status
python3 tools/tvctl.py adb shell id
python3 tools/tvctl.py adb shell getenforce
```

验收条件是 `status` 返回 `device`，且 `id` 返回 `uid=2000(shell)`。实测 SELinux 保持 `Enforcing`。端口可达、诊断 HTTP 可访问、`adb connect` 退出码为零，均不足以证明授权成功。

`connect` 会在已授权的连接上执行 `adb tcpip 5555`，验证新端口后保存目标。此步骤会重启电视 adbd，短暂中断现有连接。它无法为未授权的电脑建立身份。

## 使用控制台和实时画面

```sh
open .build/apps/电视控制台.app
```

两个 `.app` 保持在同一目录，“实时画面”按钮才能找到 `客厅电视.app`。构建目录中的应用可以直接运行；首次复制到 `~/Applications` 可使用 `python3 tools/build.py macos --install`。已有同名应用时，脚本停止，由操作者在 Finder 中明确替换。

| 功能 | 操作与输出 |
| --- | --- |
| 实时画面 | 点击“实时画面”，默认最长边 1280、上限 45 fps、关闭音频 |
| 遥控器 | 方向、确定、返回、主页、音量、静音 |
| 鼠标 | TCL 桌面点击可点击控件；垂直滚轮映射为桌面原生方向键动画 |
| 应用 | 刷新、搜索，选择后打开 |
| APK | 选择单个 APK，上传后调用 `pm install -r`；上传或安装失败也会尝试删除临时文件 |
| 截图 | 保存到 `~/Pictures/电视截图/` |
| 配置备份 | 保存到 `~/Documents/电视配置备份/`，含 Android 设置、系统属性及厂商配置 |

TCL 桌面拖动不会触发误点击，页面导航使用滚轮或方向键。其他应用继续使用 scrcpy 默认输入路径。配置备份不包含应用账号、应用私有数据或完整系统镜像，项目未提供通用一键恢复。

ADB 成功后，日常控制无需持续打开诊断 APK，也无需开启其无障碍服务。停止诊断 APK 的局域网服务可关闭其 HTTP 接口。

## 再次连接

```sh
python3 tools/tvctl.py connect
# 自动发现不可用时，读取电视 ADB 开关旁的新端口
python3 tools/tvctl.py connect --port 41783
```

自动发现仅检查配置中同一 IPv4 地址的 ADB 广播。建议在路由器为电视保留 DHCP 地址。IP 变化时，在控制台连接框输入新的 `IP:端口`，或修改本机 `connection.json` 的 `target` 后重新连接。不要删除已有私钥重新初始化。

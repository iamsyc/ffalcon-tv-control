# 从源码构建

电视端可直接下载 [已签名的 v9 APK](https://github.com/iamsyc/ffalcon-tv-control/releases/download/v0.1.0/tv-debug-entry-v9.apk)，安装方法见 [README](../README.md#电视端-apk-下载与安装)。以下步骤用于自行构建 APK、scrcpy 服务端或 macOS 控制台。

## 依赖

| 工具 | 要求 |
| --- | --- |
| Python | 3.12 或更高，无第三方 Python 依赖 |
| Java | `java`、`javac`、`keytool`；整理时用 JDK 24.0.1 构建通过 |
| Android SDK | `platforms;android-35`、`build-tools;35.0.0` |
| ADB | Android Platform Tools，含 `keygen`、mDNS；整理时用 37.0.1 |
| scrcpy | 客户端严格固定为 5.0.1 |
| macOS | 构建原生应用需要 Xcode Command Line Tools 中的 `swiftc`、`codesign` |
| 其他 | `patch`、网络下载上游 scrcpy 源码 |

使用官方 [Android SDK 工具](https://developer.android.com/tools)和 [scrcpy 安装说明](https://github.com/Genymobile/scrcpy/blob/v5.0.1/doc/macos.md)准备依赖。安装后的 scrcpy 必须仍为 5.0.1，先用 `scrcpy --version` 核对。该项目不在客户端与服务端之间提供跨版本适配。

```sh
sdkmanager 'platforms;android-35' 'build-tools;35.0.0' 'platform-tools'
export ANDROID_HOME=/path/to/android-sdk
python3 tools/tvctl.py doctor
```

Homebrew Android SDK 常见路径为 `/opt/homebrew/share/android-commandlinetools`，以本机实际安装为准。Linux 可以构建 APK 和服务端，原生控制台需要 macOS。

## 构建目标

```sh
python3 tools/build.py helper
python3 tools/build.py server
python3 tools/build.py macos
# 或一次构建全部目标
python3 tools/build.py all
```

| 目标 | 输出 |
| --- | --- |
| helper | `.build/helper/tv-debug-entry-v9.apk` |
| server | `.build/server/scrcpy-server` |
| macos | `.build/apps/电视控制台.app`、`.build/apps/客厅电视.app` |

默认构建不安装、不连接电视、不写电视配置。`server` 下载 `versions.json` 固定的 scrcpy 5.0.1 源码归档，核对 SHA-256，应用 `patches/scrcpy-5.0.1-tcl-input.patch`，调用上游无 Gradle 构建入口生成 dex 服务端。缓存保存在 `.cache/`，构建临时文件保存在 `.build/`。

补丁同时修正上游构建脚本的 `BUILD_DIR` 参数引用，允许仓库路径包含空格。

### APK 签名

首次构建在 `.local/helper.keystore` 创建本机签名密钥，默认密码 `changeit`。此文件不入库。分发自己的版本时，可通过环境变量指定长期保留的签名配置：

```sh
export TV_APK_KEYSTORE=/private/path/helper.keystore
export TV_APK_KEY_ALIAS=tv-diagnostic
# TV_APK_KEYSTORE_PASSWORD 由本机环境设置
python3 tools/build.py helper
```

覆盖升级必须使用相同签名。自行构建的 APK 与其他发布者的 APK 签名不同，不能直接覆盖，Android 会返回签名冲突。卸载后重新安装会清空诊断工具的数据及 HTTP 凭据。签名密钥与 ADB 身份密钥是两套独立文件。

### macOS 应用

原生控制台使用 AppKit，Python 后端负责 ADB。实时窗口复用本机 scrcpy 客户端并附带项目修改的服务端。构建时写入本机 Python 解释器路径，复制的 scrcpy 可执行文件仍依赖本机 Homebrew 动态库。

控制台图标由 `macos/TVConsoleIcon.swift` 绘制，构建时生成各尺寸 PNG 并通过 macOS `iconutil` 打包为 ICNS，写入应用的图标声明。源码包无需附带二进制图像资源。

两个 Python 入口关闭字节码缓存写入，避免运行时在已签名的应用包内新增 `__pycache__`。连接配置由快速开始中的 `init` 命令生成，须包含本机 ADB 可执行文件的绝对路径 `adb_path`。

因此 `.app` 适合在构建它的电脑使用。迁移到另一台电脑应重新安装依赖并构建，当前输出没有打包成可独立分发的通用二进制应用。应用采用本机 ad-hoc 签名，没有 Developer ID 公证。

重复构建会重新生成构建目录中的客户端副本，即使先前副本保留了 Homebrew 的只读权限；不会修改本机 scrcpy 原文件的权限。

```sh
# 首次安装；两个目标中任一已存在时，在复制应用前停止
python3 tools/build.py macos --install
```

## 检查

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_android.py
python3 tests/build_spaces.py
python3 tools/check_release.py
```

Android 主机检查会运行本机 HTTP、进程取消、ADB 协议及本地 socket 生命周期测试，其中停滞下载恢复检查约需一分钟。它们不访问电视。实机操作单独见[验证记录](validation.md)。

`tests/build_spaces.py` 在包含空格的临时目录中复制公共源码，执行真实服务端构建并验证生成的 dex 含输入补丁。该检查需要 Android SDK，执行后自动清除临时副本；CI 在服务端构建后运行它。

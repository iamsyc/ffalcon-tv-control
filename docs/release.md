# 发布检查

## 当前交付形态

仓库提供源码、构建入口、文档、自己的 scrcpy 补丁和脱敏验证摘要。[v0.1.0 Release](https://github.com/iamsyc/ffalcon-tv-control/releases/tag/v0.1.0) 提供已签名的电视端 `tv-debug-entry-v9.apk` 和 `SHA256SUMS.txt`，可直接下载到电视安装。项目版本为 `0.1.0`，电视端应用版本为 `9.0`，`versionCode` 为 `9`。

macOS `.app` 当前绑定构建主机的 Python 路径和 Homebrew 库，需要在使用者的电脑上构建。

README 展示的两个实际软件窗口截图位于 `docs/images/console.png` 和 `docs/images/realtime.png`。发布检查仅允许这两个 PNG 文件；更新时逐张核对，遮盖局域网地址，排除凭据及私人屏幕内容。

## 电视端 APK 发布

1. 使用保留的发布签名密钥运行 `python3 tools/build.py helper`，后续版本沿用同一密钥。
2. 使用 Android Build Tools 的 `apksigner verify --verbose --print-certs` 和 `zipalign -c 4` 检查 APK，核对包名、版本、最低 Android 版本和文件内容。
3. 为 APK 生成 `SHA256SUMS.txt`，将 APK 和校验文件上传到对应源码提交的 GitHub Release，不提交签名密钥。
4. 下载公开 Release 附件，比较 SHA-256 与本地产物，并验证 README 下载链接。

## 本地检查

```sh
python3 -m unittest discover -s tests -v
python3 tools/check_android.py
python3 tools/build.py all
python3 tests/build_spaces.py
python3 tools/check_release.py
python3 tools/package.py
```

构建和 Android 检查需要 `ANDROID_HOME`。源码包输出到 `.build/ffalcon-tv-control-source.zip`，只包含明确列出的公共目录和文件，排除构建结果、缓存、签名密钥及运行状态。

实机点击测试的日志保存在 `.local/device-checks/`。公共文件清单还会排除各源码目录中的 `*.log`，因此遗留日志不会因重新打包而进入源码包。其他新增文件仍需人工核对。

发布者检查实际文件清单，确认：

- 无 ADB 私钥、公钥身份、APK 签名密钥、HTTP 访问凭据和个人设备标识。
- 无原始研究目录、完整固件、厂商 APK、反编译厂商代码和私人屏幕截图。
- scrcpy 源码版本、归档 SHA-256、补丁及 Apache-2.0 授权文件齐全。
- README 与实际命令一致，明确限定已测机型和固件。
- 验证记录区分历史实机、本次本机检查及仍未完成的实机验收。

`check_release.py` 检查公共文件中的已知敏感模式和本地文档链接，不能替代对新增文件内容的审阅。

## 提交到 GitHub

在 GitHub 创建目标仓库后，从本地目录检查并提交公共文件。先运行检查，再核对 `git status`，确保忽略项未被强制加入。根据实际仓库 URL 添加 remote，按操作者选择的分支推送。本文不预设 GitHub 用户名、仓库地址或授权凭据。

CI 包含主机检查、Android APK 和服务端构建。通过 CI 仅表示源码能构建及离线检查通过；不表示新型号已完成首次授权，也不表示滚动体验已获实机确认。

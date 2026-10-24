# AI agent 操作约定

## 入口

先读 `README.md`、`docs/adb-authorization.md` 和 `docs/validation.md`。针对构建读取 `docs/build.md`，针对输入问题读取 `docs/architecture.md`。工作目录必须是当前仓库，避免修改历史研究目录或已安装的个人应用。

## 环境与状态

- 公共源码不包含可直接连接的电视地址、诊断凭据或 ADB 密钥。
- 使用 `tools/tvctl.py` 和 `runtime/tv_connection.py`，保持独立 server 与密钥一致，不依赖系统默认 `adb devices` 的结果。
- 默认状态目录为 `~/Library/Application Support/TVControl`。离线测试使用临时目录或 `TV_CONTROL_HOME`，不得覆盖操作者现有状态。
- APK 签名密钥、ADB 私钥、HTTP 凭据、授权计划和配置备份均为本地文件。不要提交或复制到公开日志。

## 执行边界

- 普通构建和主机测试不访问电视。实机脚本会打开应用、移动界面和上传服务端，运行前确认操作者授权范围。
- 首次特殊授权必须核对机型、固件、原始配置与影响。只有操作者明确接受替换旧电脑授权，才执行 `authorize-apply --replace-adb-authorizations`。
- 配置恢复仅撤回 IpelEngine 临时节点，不恢复旧 ADB 密钥。恢复失败保留原计划，优先恢复，停止后续配置写入。
- 未经具体请求，不刷机、降级、root、替换桌面、删除系统应用或批量关闭安全策略。
- ADB 已通后，优先使用原生 ADB，不重复部署诊断 APK 或重走授权链路。

## 证据要求

- 分开记录：静态分析、请求成功、系统实际效果、功能验收。
- 授权验收至少包含 `device`、`uid=2000(shell)` 和配置恢复精确回读。HTTP 成功、端口开放和 `connect` 退出码不足以证明完成。
- 历史实机结果与当前源码检查分别报告。未运行的电视重启、第三方 APK、其他固件或主观体验不得写成通过。
- 主桌面输入修复限定 `com.tcl.cyberui`；拖动测试验证防误点击，不代表桌面触摸拖动导航。
- 性能记录注明页面、输入、分辨率、帧率上限、编码、样本时长和测量阶段。视频包到达时间不能充当完整输入延迟。

## 修改和交付

使用 `rg` 定位相关代码。保持客户端与服务端同为 scrcpy 5.0.1，不添加未经要求的兼容层。依赖变更同时更新 `versions.json`、补丁和文档。

运行适用检查：`python3 -m unittest discover -s tests -v`、`python3 tools/check_android.py`、相应构建目标、`python3 tests/build_spaces.py`、`python3 tools/check_release.py`。改动连接模块时检查 CLI 与两个 macOS 应用的共享调用；改动输入时补充真实设备回归。

原生 `tvctl.py adb ...` 保持终端交互，内部诊断调用可以捕获输出。实机脚本的默认产物写入 `.local/device-checks`，公共源码清单排除 `*.log`。首次安装两个 macOS 应用前先检查所有目标，避免已存在目标导致部分安装。

发布前检查文件清单。禁止将 `.local`、`.build`、固件、厂商 APK、反编译代码、原始截图或个人诊断目录整体加入 Git。报告本地构建、实机验证、Git 提交和 GitHub 发布各自状态。

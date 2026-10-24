# 贡献指南

提交问题时附型号、完整固件、Android API、客户端和服务端版本、具体操作、期望结果和实际结果。输出需脱敏，禁止附私钥、完整配置备份或带诊断凭据的照片。

新型号报告必须区分“已授权 ADB 下控制可用”和“首次局域网授权可复现”。前者不能证明后者成立。特殊授权修改前先保存原始配置和恢复计划，发布报告只包含结构和摘要。

代码更改按范围验证：

```sh
python3 -m unittest discover -s tests -v
ANDROID_HOME=/path/to/android-sdk python3 tools/check_android.py
ANDROID_HOME=/path/to/android-sdk python3 tools/build.py all
ANDROID_HOME=/path/to/android-sdk python3 tests/build_spaces.py
python3 tools/check_release.py
```

Linux 可构建 `helper`、`server`；`all` 包含需要 macOS 的原生应用。Java 检查包含约一分钟的真实停滞连接测试。CI 不连接电视，不能替代实机功能验证。

提交输入补丁时使用同一动作比较修改前后结果，记录是否误触、是否释放按键及其他应用是否受影响。提交性能变更时保留固定场景的数据和真实窗口体验，不用单个平均帧率作为完成标准。

发布流程见 [docs/release.md](docs/release.md)。

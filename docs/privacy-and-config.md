# 配置审计与隐私检查

ADB 可以读取软件包、权限、服务、日志及开放的厂商配置。它可用于定位统计和推荐机制，但配置字段本身不能证明个人数据已经发送到外部。网络上报结论还需要对应进程、实际请求、目标域名及内容证据。

## 先导出配置

使用控制台“备份配置”，保存 Android `global`、`secure`、`system`、`getprop` 和厂商配置。导出中可能含设备标识和网络信息，只在本地保存。

以下查询不修改电视：

```sh
python3 tools/tvctl.py adb shell pm list packages
python3 tools/tvctl.py adb shell settings list global
python3 tools/tvctl.py adb shell settings list secure
python3 tools/tvctl.py adb shell dumpsys adb
python3 tools/tvctl.py adb shell content query \
  --uri content://com.tcl.providers.config/all \
  --projection project_id:config_content
```

## 已观察的配置面

| 配置 | 研究中发现的含义或线索 |
| --- | --- |
| 用户体验、个性化推荐 | 有明确开关和回读，历史设备已按所有者要求关闭 |
| `SupportUserActionCollect.Keycode` | 存在按键收集配置，历史回读为空列表 |
| `CloudProfile.dcs_switch` | 存在云侧统计配置，历史回读为 `false` |
| `AppBootPolicy.reportEnable` | 存在应用启动上报配置，历史回读为 `false` |
| `WifiConfig.enableWifiBuried`、`enableP2pBuried` | 存在 Wi-Fi / P2P 统计配置，历史回读为 `false` |
| `WifiConfig.enableApModel` | 存在 AP 相关配置，历史回读为 `false` |
| 安装安全策略总开关 | 影响安装策略，历史设备按所有者要求调整；不在公共工具中自动关闭 |

这些字段是单个固件上的配置线索，公开项目没有把原设备偏好作为其他设备的默认值，也没有提供批量关闭所有安全服务的命令。每次变更应先确认所属配置组和消费者实现，保留原始字符串，只修改需要的字段，再回读并验证功能。云端配置和升级可能覆盖本地值，长期效果需要另行观察。

## 有意义的后续检查

1. 比较电视空闲、打开应用和开启推荐时的出站连接，关联对应 UID 和包名。
2. 在路由器或受控网络记录 DNS 与连接元数据，区分电视流量与其他设备。
3. 将代码中出现的域名与实测连接对应，再判断统计、广告、内容播放和更新服务的用途。
4. 如需禁用组件，逐个操作并检查开机、遥控、安装、播放和更新，不从包名推断可安全删除。

当前成果没有完成全量抓包、加密请求内容分析或广告全面清除。不要把“设置已关闭”写成“所有追踪已阻断”。

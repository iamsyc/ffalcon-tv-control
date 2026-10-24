import AppKit
import UniformTypeIdentifiers

struct TVApp {
    let name: String
    let package: String
    let component: String
}

final class Console: NSObject, NSApplicationDelegate, NSTableViewDataSource, NSTableViewDelegate, NSSearchFieldDelegate {
    var window: NSWindow!
    let table = NSTableView()
    let search = NSSearchField()
    let address = NSTextField()
    let connection = NSTextField(labelWithString: "正在连接电视…")
    let resultLabel = NSTextField(labelWithString: "")
    let detailLabel = NSTextField(wrappingLabelWithString: "截图保存在“图片 / 电视截图”，配置保存在“文稿 / 电视配置备份”。")
    let countLabel = NSTextField(labelWithString: "应用")
    let spinner = NSProgressIndicator()
    var buttons: [NSButton] = []
    var revealButton: NSButton!
    var apps: [TVApp] = []
    var filtered: [TVApp] = []
    var busy = false
    var lastPath: String?

    func applicationDidFinishLaunching(_ notification: Notification) {
        makeMenu()
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1060, height: 730), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "客厅电视控制台"
        window.minSize = NSSize(width: 950, height: 680)
        window.center()
        let root = NSView()
        root.translatesAutoresizingMaskIntoConstraints = false
        window.contentView!.addSubview(root)
        NSLayoutConstraint.activate([
            root.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 24),
            root.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -24),
            root.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 24),
            root.bottomAnchor.constraint(equalTo: window.contentView!.bottomAnchor, constant: -22)
        ])
        let title = NSTextField(labelWithString: "客厅电视控制台")
        title.font = .systemFont(ofSize: 25, weight: .semibold)
        let subtitle = NSTextField(labelWithString: "应用、遥控和配置，一处管理。")
        subtitle.textColor = .secondaryLabelColor
        root.addSubview(title)
        root.addSubview(subtitle)

        let actions = NSStackView()
        actions.spacing = 10
        actions.addArrangedSubview(button("实时画面", "rectangle.on.rectangle", #selector(openVideo)))
        actions.addArrangedSubview(button("安装 APK", "square.and.arrow.down", #selector(installAPK)))
        actions.addArrangedSubview(button("截图", "camera", #selector(screenshot)))
        actions.addArrangedSubview(button("备份配置", "externaldrive", #selector(backup)))
        revealButton = button("查看文件", "folder", #selector(reveal))
        revealButton.isEnabled = false
        actions.addArrangedSubview(revealButton)
        root.addSubview(actions)

        let stateRow = NSStackView()
        stateRow.spacing = 12
        connection.font = .systemFont(ofSize: 13, weight: .medium)
        connection.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        stateRow.addArrangedSubview(connection)
        let spacer = NSView()
        spacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        stateRow.addArrangedSubview(spacer)
        address.placeholderString = "电视 IP:端口"
        address.identifier = NSUserInterfaceItemIdentifier("tv-address")
        address.widthAnchor.constraint(equalToConstant: 205).isActive = true
        let support = ProcessInfo.processInfo.environment["TV_CONTROL_HOME"].map { URL(fileURLWithPath: $0) } ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/TVControl")
        let configURL = support.appendingPathComponent("connection.json")
        if let data = try? Data(contentsOf: configURL), let config = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            address.stringValue = config["target"] as? String ?? ""
        }
        address.target = self
        address.action = #selector(connect)
        stateRow.addArrangedSubview(address)
        stateRow.addArrangedSubview(button("连接", "arrow.triangle.2.circlepath", #selector(connect)))
        root.addSubview(stateRow)
        stateRow.widthAnchor.constraint(equalTo: root.widthAnchor).isActive = true

        let divider = NSBox()
        divider.boxType = .separator
        root.addSubview(divider)
        divider.widthAnchor.constraint(equalTo: root.widthAnchor).isActive = true

        let main = NSView()
        main.setContentHuggingPriority(.defaultLow, for: .vertical)
        root.addSubview(main)
        main.widthAnchor.constraint(equalTo: root.widthAnchor).isActive = true

        let remotePanel = NSBox()
        remotePanel.boxType = .custom
        remotePanel.titlePosition = .noTitle
        remotePanel.contentViewMargins = .zero
        remotePanel.fillColor = .controlBackgroundColor
        remotePanel.borderColor = .separatorColor
        remotePanel.borderWidth = 0.5
        remotePanel.cornerRadius = 12
        main.addSubview(remotePanel)
        remotePanel.translatesAutoresizingMaskIntoConstraints = false

        let remote = NSStackView()
        remote.orientation = .vertical
        remote.alignment = .centerX
        remote.spacing = 10
        let remoteTitle = NSTextField(labelWithString: "遥控器")
        remoteTitle.font = .systemFont(ofSize: 15, weight: .semibold)
        remoteTitle.widthAnchor.constraint(equalToConstant: 184).isActive = true
        remote.addArrangedSubview(remoteTitle)
        let grid = NSGridView(views: [
            [NSView(), keyButton("上", "KEYCODE_DPAD_UP", symbol: "chevron.up", width: 56, height: 40), NSView()],
            [keyButton("左", "KEYCODE_DPAD_LEFT", symbol: "chevron.left", width: 56, height: 40), keyButton("确定", "KEYCODE_DPAD_CENTER", width: 56, height: 40), keyButton("右", "KEYCODE_DPAD_RIGHT", symbol: "chevron.right", width: 56, height: 40)],
            [NSView(), keyButton("下", "KEYCODE_DPAD_DOWN", symbol: "chevron.down", width: 56, height: 40), NSView()]
        ])
        grid.rowSpacing = 6
        grid.columnSpacing = 8
        grid.xPlacement = .fill
        grid.yPlacement = .fill
        for index in 0..<3 {
            grid.row(at: index).height = 40
            grid.column(at: index).width = 56
        }
        NSLayoutConstraint.activate([
            grid.widthAnchor.constraint(equalToConstant: 184),
            grid.heightAnchor.constraint(equalToConstant: 132)
        ])
        remote.addArrangedSubview(grid)
        remote.setCustomSpacing(12, after: remoteTitle)
        remote.setCustomSpacing(14, after: grid)
        let navigation = NSStackView(views: [
            keyButton("返回", "KEYCODE_BACK", symbol: "arrow.uturn.backward"),
            keyButton("主页", "KEYCODE_HOME", symbol: "house")
        ])
        navigation.spacing = 8
        navigation.distribution = .fillEqually
        remote.addArrangedSubview(navigation)
        let volume = NSStackView(views: [keyButton("音量 −", "KEYCODE_VOLUME_DOWN"), keyButton("音量 +", "KEYCODE_VOLUME_UP")])
        volume.spacing = 8
        volume.distribution = .fillEqually
        remote.addArrangedSubview(volume)
        let mute = keyButton("静音切换", "KEYCODE_VOLUME_MUTE", symbol: "speaker.slash", width: 184)
        remote.addArrangedSubview(mute)
        let tip = NSTextField(wrappingLabelWithString: "实时画面支持鼠标点击，也可用方向键和回车操作。")
        tip.font = .systemFont(ofSize: 12)
        tip.textColor = .secondaryLabelColor
        tip.widthAnchor.constraint(equalToConstant: 184).isActive = true
        remote.addArrangedSubview(tip)
        remote.setCustomSpacing(12, after: mute)
        remotePanel.contentView!.addSubview(remote)
        remote.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            remotePanel.leadingAnchor.constraint(equalTo: main.leadingAnchor),
            remotePanel.topAnchor.constraint(equalTo: main.topAnchor),
            remotePanel.widthAnchor.constraint(equalToConstant: 216),
            remotePanel.bottomAnchor.constraint(lessThanOrEqualTo: main.bottomAnchor),
            remote.leadingAnchor.constraint(equalTo: remotePanel.contentView!.leadingAnchor, constant: 15),
            remote.trailingAnchor.constraint(equalTo: remotePanel.contentView!.trailingAnchor, constant: -15),
            remote.topAnchor.constraint(equalTo: remotePanel.contentView!.topAnchor, constant: 15),
            remote.bottomAnchor.constraint(equalTo: remotePanel.contentView!.bottomAnchor, constant: -15)
        ])

        let appPane = NSStackView()
        appPane.orientation = .vertical
        appPane.alignment = .leading
        appPane.spacing = 12
        main.addSubview(appPane)
        appPane.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([appPane.leadingAnchor.constraint(equalTo: remotePanel.trailingAnchor, constant: 24), appPane.trailingAnchor.constraint(equalTo: main.trailingAnchor), appPane.topAnchor.constraint(equalTo: main.topAnchor, constant: 12), appPane.bottomAnchor.constraint(equalTo: main.bottomAnchor)])
        let appHeader = NSStackView()
        appHeader.spacing = 10
        countLabel.font = .systemFont(ofSize: 15, weight: .semibold)
        appHeader.addArrangedSubview(countLabel)
        let appSpacer = NSView()
        appSpacer.setContentHuggingPriority(.defaultLow, for: .horizontal)
        appHeader.addArrangedSubview(appSpacer)
        search.placeholderString = "搜索名称或包名"
        search.delegate = self
        search.widthAnchor.constraint(equalToConstant: 210).isActive = true
        appHeader.addArrangedSubview(search)
        appHeader.addArrangedSubview(button("刷新", "arrow.clockwise", #selector(refresh)))
        appPane.addArrangedSubview(appHeader)
        appHeader.widthAnchor.constraint(equalTo: appPane.widthAnchor).isActive = true
        let scroll = NSScrollView()
        scroll.hasVerticalScroller = true
        scroll.borderType = .bezelBorder
        scroll.translatesAutoresizingMaskIntoConstraints = false
        let column = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("app"))
        column.title = "应用"
        column.resizingMask = .autoresizingMask
        table.addTableColumn(column)
        table.headerView = nil
        table.rowHeight = 53
        table.usesAlternatingRowBackgroundColors = true
        table.allowsMultipleSelection = false
        table.dataSource = self
        table.delegate = self
        table.target = self
        table.doubleAction = #selector(launch)
        scroll.documentView = table
        appPane.addArrangedSubview(scroll)
        scroll.widthAnchor.constraint(equalTo: appPane.widthAnchor).isActive = true
        scroll.heightAnchor.constraint(greaterThanOrEqualToConstant: 230).isActive = true
        scroll.setContentHuggingPriority(.defaultLow, for: .vertical)
        let launchRow = NSStackView(views: [button("打开所选应用", "play.fill", #selector(launch))])
        appPane.addArrangedSubview(launchRow)

        let footer = NSStackView()
        footer.spacing = 8
        spinner.style = .spinning
        spinner.controlSize = .small
        spinner.isDisplayedWhenStopped = false
        spinner.isHidden = true
        footer.addArrangedSubview(spinner)
        resultLabel.font = .systemFont(ofSize: 13, weight: .medium)
        footer.addArrangedSubview(resultLabel)
        root.addSubview(footer)
        detailLabel.font = .systemFont(ofSize: 12)
        detailLabel.textColor = .secondaryLabelColor
        detailLabel.isSelectable = true
        detailLabel.maximumNumberOfLines = 2
        root.addSubview(detailLabel)
        detailLabel.widthAnchor.constraint(equalTo: root.widthAnchor).isActive = true
        for view in [title, subtitle, actions, stateRow, divider, main, footer, detailLabel] { view.translatesAutoresizingMaskIntoConstraints = false }
        NSLayoutConstraint.activate([
            title.topAnchor.constraint(equalTo: root.topAnchor), title.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            subtitle.topAnchor.constraint(equalTo: title.bottomAnchor, constant: 5), subtitle.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            actions.topAnchor.constraint(equalTo: subtitle.bottomAnchor, constant: 14), actions.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            stateRow.topAnchor.constraint(equalTo: actions.bottomAnchor, constant: 12), stateRow.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            divider.topAnchor.constraint(equalTo: stateRow.bottomAnchor, constant: 12), divider.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            main.topAnchor.constraint(equalTo: divider.bottomAnchor, constant: 16), main.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            main.bottomAnchor.constraint(equalTo: footer.topAnchor, constant: -18),
            footer.leadingAnchor.constraint(equalTo: root.leadingAnchor), footer.bottomAnchor.constraint(equalTo: detailLabel.topAnchor, constant: -5),
            detailLabel.leadingAnchor.constraint(equalTo: root.leadingAnchor), detailLabel.bottomAnchor.constraint(equalTo: root.bottomAnchor)
        ])
        window.initialFirstResponder = table
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        perform("status", [], "正在连接并读取应用…")
    }

    func makeMenu() {
        let main = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "退出电视控制台", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appItem.submenu = appMenu
        main.addItem(appItem)
        let operations = NSMenuItem(title: "操作", action: nil, keyEquivalent: "")
        let menu = NSMenu(title: "操作")
        for (name, action, key) in [("安装 APK", #selector(installAPK), "o"), ("刷新应用", #selector(refresh), "r"), ("实时画面", #selector(openVideo), "l")] {
            let item = NSMenuItem(title: name, action: action, keyEquivalent: key)
            item.target = self
            menu.addItem(item)
        }
        operations.submenu = menu
        main.addItem(operations)
        let editItem = NSMenuItem(title: "编辑", action: nil, keyEquivalent: "")
        let edit = NSMenu(title: "编辑")
        edit.addItem(withTitle: "剪切", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        edit.addItem(withTitle: "复制", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        edit.addItem(withTitle: "粘贴", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        edit.addItem(withTitle: "全选", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = edit
        main.addItem(editItem)
        NSApp.mainMenu = main
    }

    func button(_ title: String, _ symbol: String, _ action: Selector) -> NSButton {
        let value = NSButton(title: title, target: self, action: action)
        value.bezelStyle = .rounded
        value.image = NSImage(systemSymbolName: symbol, accessibilityDescription: nil)
        value.imagePosition = .imageLeading
        buttons.append(value)
        return value
    }
    func keyButton(_ title: String, _ key: String, symbol: String? = nil, width: CGFloat = 88, height: CGFloat = 32) -> NSButton {
        let value = NSButton(title: title, target: self, action: #selector(sendKey(_:)))
        value.identifier = NSUserInterfaceItemIdentifier(key)
        value.setAccessibilityLabel(title)
        value.toolTip = title
        value.bezelStyle = .regularSquare
        value.font = .systemFont(ofSize: 13, weight: .medium)
        value.wantsLayer = true
        value.layer?.cornerRadius = 8
        value.layer?.masksToBounds = true
        if let symbol = symbol {
            value.image = NSImage(systemSymbolName: symbol, accessibilityDescription: title)?.withSymbolConfiguration(.init(pointSize: 14, weight: .medium))
            value.imagePosition = key.hasPrefix("KEYCODE_DPAD") ? .imageOnly : .imageLeading
        }
        value.widthAnchor.constraint(equalToConstant: width).isActive = true
        value.heightAnchor.constraint(equalToConstant: height).isActive = true
        buttons.append(value)
        return value
    }
    func setBusy(_ value: Bool) {
        busy = value
        for button in buttons { button.isEnabled = !value }
        revealButton.isEnabled = lastPath != nil
        spinner.isHidden = !value
        if value { spinner.startAnimation(nil) } else { spinner.stopAnimation(nil) }
    }
    func perform(_ action: String, _ args: [String], _ description: String) {
        guard !busy else { return }
        setBusy(true)
        resultLabel.textColor = .labelColor
        resultLabel.stringValue = description
        let backend = Bundle.main.resourceURL!.appendingPathComponent("backend.py").path
        DispatchQueue.global(qos: .userInitiated).async {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: Bundle.main.object(forInfoDictionaryKey: "TVPythonExecutable") as! String)
            process.arguments = [backend, action] + args
            let output = Pipe()
            process.standardOutput = output
            process.standardError = output
            var response: [String: Any]
            do {
                try process.run()
                let data = output.fileHandleForReading.readDataToEndOfFile()
                process.waitUntilExit()
                if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    response = json
                } else { response = ["ok": false, "message": "无法解析操作结果"] }
            } catch { response = ["ok": false, "message": error.localizedDescription] }
            let result = response
            DispatchQueue.main.async {
                self.setBusy(false)
                let ok = result["ok"] as? Bool == true
                self.resultLabel.textColor = ok ? .labelColor : .systemRed
                self.resultLabel.stringValue = result["message"] as? String ?? "操作结束"
                if action == "status" || action == "connect" {
                    self.connection.stringValue = ok ? self.resultLabel.stringValue : "未连接"
                    self.connection.textColor = ok ? .systemGreen : .systemRed
                }
                if let target = result["target"] as? String {
                    self.address.stringValue = target
                }
                if let appRows = result["apps"] as? [[String: Any]] {
                    self.apps = appRows.map { TVApp(name: $0["name"] as! String, package: $0["package"] as! String, component: $0["component"] as! String) }
                    self.filterApps()
                }
                if let path = result["path"] as? String {
                    self.lastPath = path
                    self.revealButton.isEnabled = true
                    self.detailLabel.stringValue = path
                } else if ok {
                    self.detailLabel.stringValue = self.lastPath ?? "截图保存在“图片 / 电视截图”，配置保存在“文稿 / 电视配置备份”。"
                } else {
                    self.detailLabel.stringValue = "请确认电视已开机且 ADB 已开启，点击“连接”会自动识别端口。"
                }
            }
        }
    }
    func filterApps() {
        let query = search.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        filtered = apps.filter { query.isEmpty || $0.name.localizedCaseInsensitiveContains(query) || $0.package.localizedCaseInsensitiveContains(query) }
        countLabel.stringValue = "应用 · \(filtered.count)"
        table.reloadData()
        if !filtered.isEmpty { table.selectRowIndexes(IndexSet(integer: 0), byExtendingSelection: false) }
    }
    func controlTextDidChange(_ notification: Notification) { filterApps() }
    func numberOfRows(in tableView: NSTableView) -> Int { filtered.count }
    func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
        let item = filtered[row]
        let cell = NSTableCellView()
        let title = NSTextField(labelWithString: item.name)
        title.font = .systemFont(ofSize: 14, weight: .medium)
        let package = NSTextField(labelWithString: item.package)
        package.font = .systemFont(ofSize: 11)
        package.textColor = .secondaryLabelColor
        package.isHidden = item.name == item.package
        for label in [title, package] { label.lineBreakMode = .byTruncatingTail; label.maximumNumberOfLines = 1 }
        let stack = NSStackView(views: [title, package])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 2
        stack.translatesAutoresizingMaskIntoConstraints = false
        cell.addSubview(stack)
        NSLayoutConstraint.activate([stack.leadingAnchor.constraint(equalTo: cell.leadingAnchor, constant: 10), stack.trailingAnchor.constraint(equalTo: cell.trailingAnchor, constant: -10), stack.centerYAnchor.constraint(equalTo: cell.centerYAnchor)])
        return cell
    }
    @objc func connect() { perform("connect", [address.stringValue], "正在连接电视…") }
    @objc func refresh() { perform("apps", [], "正在刷新应用…") }
    @objc func launch() {
        guard !busy, filtered.indices.contains(table.selectedRow) else { return }
        let app = filtered[table.selectedRow]
        perform("launch", [app.component], "正在打开 \(app.name)…")
    }
    @objc func sendKey(_ sender: NSButton) {
        perform("key", [sender.identifier!.rawValue], "正在发送按键…")
    }
    @objc func screenshot() { perform("screenshot", [], "正在保存电视截图…") }
    @objc func backup() { perform("backup", [], "正在备份电视配置…") }
    @objc func installAPK() {
        guard !busy else { return }
        let panel = NSOpenPanel()
        panel.title = "选择要安装到电视的 APK"
        panel.prompt = "安装到电视"
        panel.allowedContentTypes = [UTType(filenameExtension: "apk")!]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.beginSheetModal(for: window) { response in
            if response == .OK, let path = panel.url?.path {
                self.perform("install", [path], "正在安装 APK，请稍候…")
            }
        }
    }
    @objc func reveal() {
        if let path = lastPath { NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)]) }
    }
    @objc func openVideo() {
        let url = Bundle.main.bundleURL.deletingLastPathComponent().appendingPathComponent("客厅电视.app")
        NSWorkspace.shared.openApplication(at: url, configuration: NSWorkspace.OpenConfiguration()) { _, error in
            DispatchQueue.main.async {
                if let error = error { self.resultLabel.stringValue = error.localizedDescription; self.resultLabel.textColor = .systemRed }
            }
        }
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}
let app = NSApplication.shared
let delegate = Console()
app.setActivationPolicy(.regular)
app.delegate = delegate
app.run()

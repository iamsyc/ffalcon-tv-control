import AppKit

// Draw the application artwork directly so source builds need no binary assets.
let directory = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)

func color(_ red: CGFloat, _ green: CGFloat, _ blue: CGFloat) -> NSColor {
    NSColor(srgbRed: red / 255, green: green / 255, blue: blue / 255, alpha: 1)
}

func rounded(_ rect: NSRect, _ radius: CGFloat, _ fill: NSColor) {
    fill.setFill()
    NSBezierPath(roundedRect: rect, xRadius: radius, yRadius: radius).fill()
}

func render(_ pixels: Int, to url: URL) throws {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels,
        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
        colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    let context = NSGraphicsContext(bitmapImageRep: bitmap)!
    NSGraphicsContext.current = context
    context.cgContext.scaleBy(x: CGFloat(pixels) / 1024, y: CGFloat(pixels) / 1024)

    let tile = NSBezierPath(roundedRect: NSRect(x: 82, y: 82, width: 860, height: 860),
                            xRadius: 190, yRadius: 190)
    NSGradient(starting: color(16, 39, 64), ending: color(12, 104, 117))!
        .draw(in: tile, angle: 55)

    // Television, including a short stand that stays visible at Dock sizes.
    let ivory = color(235, 249, 250)
    rounded(NSRect(x: 448, y: 258, width: 112, height: 110), 18, ivory)
    rounded(NSRect(x: 330, y: 234, width: 348, height: 42), 21, ivory)
    rounded(NSRect(x: 186, y: 342, width: 646, height: 420), 56, ivory)
    let screen = NSBezierPath(roundedRect: NSRect(x: 216, y: 390, width: 586, height: 342),
                              xRadius: 30, yRadius: 30)
    NSGradient(starting: color(14, 49, 73), ending: color(26, 158, 167))!
        .draw(in: screen, angle: 30)
    let play = NSBezierPath()
    play.move(to: NSPoint(x: 448, y: 484))
    play.line(to: NSPoint(x: 448, y: 634))
    play.line(to: NSPoint(x: 564, y: 559))
    play.close()
    ivory.setFill()
    play.fill()
    rounded(NSRect(x: 483, y: 361, width: 52, height: 9), 4.5, color(32, 179, 167))

    // The remote makes the console distinct from a video player.
    rounded(NSRect(x: 662, y: 193, width: 166, height: 362), 66, color(5, 45, 59))
    rounded(NSRect(x: 674, y: 205, width: 142, height: 346), 56, ivory)
    rounded(NSRect(x: 730, y: 503, width: 30, height: 14), 7, color(31, 170, 157))
    rounded(NSRect(x: 699, y: 371, width: 92, height: 92), 46, color(16, 74, 91))
    rounded(NSRect(x: 731, y: 403, width: 28, height: 28), 14, ivory)
    rounded(NSRect(x: 705, y: 315, width: 30, height: 18), 9, color(61, 120, 135))
    rounded(NSRect(x: 755, y: 315, width: 30, height: 18), 9, color(61, 120, 135))
    rounded(NSRect(x: 730, y: 263, width: 30, height: 18), 9, color(61, 120, 135))

    NSGraphicsContext.restoreGraphicsState()
    try bitmap.representation(using: .png, properties: [:])!.write(to: url)
}

for size in [16, 32, 128, 256, 512] {
    try render(size, to: directory.appendingPathComponent("icon_\(size)x\(size).png"))
    try render(size * 2, to: directory.appendingPathComponent("icon_\(size)x\(size)@2x.png"))
}

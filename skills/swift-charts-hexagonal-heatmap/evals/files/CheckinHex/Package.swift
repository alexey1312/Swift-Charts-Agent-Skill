// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "CheckinHex",
    platforms: [.iOS(.v18)],
    products: [.library(name: "CheckinHex", targets: ["CheckinHex"])],
    targets: [.target(name: "CheckinHex")]
)

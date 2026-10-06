// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "HexGaps",
    platforms: [.iOS(.v18)],
    products: [.library(name: "HexGaps", targets: ["HexGaps"])],
    targets: [.target(name: "HexGaps")]
)

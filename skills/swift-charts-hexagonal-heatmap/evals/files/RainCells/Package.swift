// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "RainCells",
    platforms: [.iOS(.v18)],
    products: [.library(name: "RainCells", targets: ["RainCells"])],
    targets: [.target(name: "RainCells")]
)

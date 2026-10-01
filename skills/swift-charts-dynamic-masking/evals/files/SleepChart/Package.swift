// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SleepChart",
    platforms: [.iOS(.v16)],
    products: [.library(name: "SleepChart", targets: ["SleepChart"])],
    targets: [.target(name: "SleepChart")]
)

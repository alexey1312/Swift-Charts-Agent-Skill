// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "TapDensity",
    platforms: [.iOS(.v16)],
    products: [.library(name: "TapDensity", targets: ["TapDensity"])],
    targets: [.target(name: "TapDensity")]
)

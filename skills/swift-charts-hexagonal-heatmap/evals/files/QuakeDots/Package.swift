// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "QuakeDots",
    platforms: [.iOS(.v18)],
    products: [.library(name: "QuakeDots", targets: ["QuakeDots"])],
    targets: [.target(name: "QuakeDots")]
)

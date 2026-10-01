import Charts
import SwiftUI

public struct Night: Identifiable {
    public let id: Date
    public let hours: Double
    public init(id: Date, hours: Double) {
        self.id = id
        self.hours = hours
    }
}

/// Hours slept per night. Shipped to iOS 16 and later.
public struct SleepHistory: View {
    let nights: [Night]

    public init(nights: [Night]) {
        self.nights = nights
    }

    public var body: some View {
        Chart(nights) { night in
            LineMark(x: .value("Night", night.id), y: .value("Hours", night.hours))
                .interpolationMethod(.catmullRom)
            AreaMark(x: .value("Night", night.id), y: .value("Hours", night.hours))
                .interpolationMethod(.catmullRom)
                .opacity(0.2)
        }
        .frame(height: 180)
    }
}

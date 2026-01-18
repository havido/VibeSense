//
//  LineChartView.swift
//  Demo App
//
//  Created by Ashraful Islam on 8/12/24.
//

import SwiftUI
import Charts

struct LineChartView: View {
    let orderedPairs: [(time: Float, value: Float)]
    let title: String
    let xLabel: String
    let yLabel: String
    let showYTicks: Bool

    var body: some View {
        VStack {
            Text(title)
                .font(.headline)
                .padding(.top)
                .foregroundStyle(.gray)

            if #available(iOS 16.0, *) {
                Chart {
                    ForEach(orderedPairs, id: \.time) { pair in
                        LineMark(
                            x: .value("Time", pair.time),
                            y: .value("Value", pair.value)
                        )
                        .foregroundStyle(.red)
                    }
                }
                .chartXAxis {
                    AxisMarks(position: .bottom) { value in
                        AxisGridLine()
                        AxisTick()
                        AxisValueLabel()
                    }
                }
                .chartYAxis {
                    if showYTicks {
                        AxisMarks(position: .leading) { value in
                            AxisGridLine()
                            AxisTick()
                            AxisValueLabel()
                        }
                    } else {
                        AxisMarks(position: .leading) { _ in
                            AxisGridLine().foregroundStyle(.clear)
                            AxisTick().foregroundStyle(.clear)
                            AxisValueLabel().foregroundStyle(.clear)
                        }
                    }
                }
                .chartXAxisLabel(xLabel, alignment: .center)
                .frame(height: 200)
                .padding()
            } else {
                // Fallback for iOS versions earlier than 16.0
                // Map each (Float, Float) pair to (Double, Double) since CGFloat is typealiased to Double and compiler fails to typecheck otherwise
                let doubleOrderedPairs = orderedPairs.map { (time: Double($0.time), value: Double($0.value)) }
                ChartsViewLegacy(orderedPairs: doubleOrderedPairs, title: title, xLabel: xLabel, yLabel: yLabel, showYTicks: showYTicks)
                    .frame(height: 200)
            }
        }
    }
}

#Preview {
    LineChartView(orderedPairs: [(time: 0.0, value: 0.0), (time: 1.0, value: 2.0), (time: 2.0, value: 1.5), (time: 3.0, value: 3.0)], title: "Dummy Chart", xLabel: "Time", yLabel: "Value", showYTicks: true)
}

struct ChartsViewLegacy: View {
    let orderedPairs: [(time: Double, value: Double)]
    let title: String
    let xLabel: String
    let yLabel: String
    let showYTicks: Bool


    private let paddingFactor: Double = 0.05 // 5% padding on each side
    private let minimumRange: Double = 0.1 // Minimum range for y-axis

    var body: some View {
        GeometryReader { geometry in
            VStack {
                Canvas { context, size in
                    var path = Path()

                    for (index, point) in orderedPairs.enumerated() {
                        let xPosition = (point.time - minX) / (maxX - minX) * size.width
                        let yPosition = adjustedMaxY == adjustedMinY ? size.height / 2 : (1 - (point.value - adjustedMinY) / (adjustedMaxY - adjustedMinY)) * (size.height - 20) + 10

                        if index == 0 {
                            path.move(to: CGPoint(x: xPosition, y: yPosition))
                        } else {
                            path.addLine(to: CGPoint(x: xPosition, y: yPosition))
                        }
                    }

                    context.stroke(path, with: .color(.red), lineWidth: 2)

                    // Draw X tick marks and labels inside the box plot, skip the first one
                    for (index, xTick) in xTickValues.enumerated() {
                        if index > 0 {
                            let xPosition = (xTick - minX) / (maxX - minX) * size.width
                            context.stroke(Path { path in
                                path.move(to: CGPoint(x: xPosition, y: size.height))
                                path.addLine(to: CGPoint(x: xPosition, y: size.height - 5))
                            }, with: .color(.black), lineWidth: 1)
                            context.draw(Text(String(format: "%.0f", xTick)).font(.caption), at: CGPoint(x: xPosition, y: size.height - 20), anchor: .top)
                        }
                    }

                    // Draw Y tick marks and labels inside the box plot
                    if showYTicks {
                        let yTicks = yTickValues
                        let range = adjustedMaxY - adjustedMinY
                        let strideSize = range / Double(yTicks.count - 1)
                        for yTick in yTicks {
                            let yPosition = adjustedMaxY == adjustedMinY ? size.height / 2 : (1 - (yTick - adjustedMinY) / (adjustedMaxY - adjustedMinY)) * (size.height - 20) + 10
                            let formatString = strideSize < 1 ? "%.2f" : "%.1f"
                            context.draw(Text(String(format: formatString, yTick)).font(.caption), at: CGPoint(x: 10, y: yPosition), anchor: .leading)
                        }
                    }
                }

                HStack {
                    Spacer()
                    Text(xLabel).font(.caption).padding([.top, .trailing])
                    Spacer()
                }
            }
        }
    }

    // Helper properties and methods for the fallback implementation
    private var minXValue: Double {
        orderedPairs.min(by: { $0.time < $1.time })?.time ?? 0
    }

    private var maxXValue: Double {
        orderedPairs.max(by: { $0.time < $1.time })?.time ?? 1
    }

    private var minYValue: Double {
        orderedPairs.min(by: { $0.value < $1.value })?.value ?? 0
    }

    private var maxYValue: Double {
        orderedPairs.max(by: { $0.value < $1.value })?.value ?? 1
    }

    private var minX: Double {
        return minXValue - paddingFactor * (maxXValue - minXValue)
    }

    private var maxX: Double {
        return maxXValue + paddingFactor * (maxXValue - minXValue)
    }

    private var adjustedMinY: Double {
        minYValue - paddingFactor * max(maxYValue - minYValue, minimumRange)
    }

    private var adjustedMaxY: Double {
        maxYValue + paddingFactor * max(maxYValue - minYValue, minimumRange)
    }

    private var xTickValues: [Double] {
        let strideSize = max(1.0, (maxX - minX) / 10) // Ensure X-axis ticks have a minimum stride size
        return Array(stride(from: ceil(minX), through: floor(maxX), by: strideSize))
    }

    private var yTickValues: [Double] {
        let numberOfTicks = 4
        let range = adjustedMaxY - adjustedMinY
        let strideSize = range / Double(numberOfTicks - 1)
        return range == 0 ? Array(repeating: adjustedMinY, count: numberOfTicks) : Array(stride(from: adjustedMinY, through: adjustedMaxY, by: strideSize))
    }
}

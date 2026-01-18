import SwiftUI
import SmartSpectraSwiftSDK
internal import AVFoundation

struct ContentView: View {
    @ObservedObject var sdk = SmartSpectraSwiftSDK.shared
    @ObservedObject var vitalsProcessor = SmartSpectraVitalsProcessor.shared
    @State private var isVitalMonitoringEnabled: Bool = false
    @State private var showCameraFeed: Bool = false
    @State private var averagesTimer: Timer? = nil
    @State private var isCameraFeedVisible: Bool = false
    @State private var isUsingBackCamera: Bool = true

    init() {
        let apiKey = "k8iMqD6n2E9ej2k6yOsii7sxQrfjiJ71ybjz2FA8"
        sdk.setApiKey(apiKey)
        sdk.setCameraPosition(.back)
    }

    var body: some View {
        GeometryReader { geo in
            VStack(spacing: 8) {
                // App Title
                Image("logo")
                    .resizable()
                    .scaledToFit()
                    .frame(width: geo.size.width * 0.3)
                    .frame(maxWidth: .infinity)
                    .padding(.top, 4)

                // Camera Frame with overlayed metrics
                ZStack(alignment: .topLeading) {
                    // Background rounded rectangle to define the frame
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .fill(Color(UIColor.secondarySystemBackground))
                        .overlay(
                            Group {
                                if let image = vitalsProcessor.imageOutput {
                                    Image(uiImage: image)
                                        .resizable()
                                        .scaledToFill()
                                } else {
                                    if #available(iOS 17.0, *) {
                                        ContentUnavailableView {
                                            Label("Camera Feed", systemImage: "camera.fill")
                                        } description: {
                                            if !isVitalMonitoringEnabled {
                                                Text("Start monitoring to see live frames")
                                            } else {
                                                Text("Starting camera feed...")
                                            }
                                        }
                                    } else {
                                        VStack(spacing: 8) {
                                            Image(systemName: "camera.fill")
                                                .font(.largeTitle)
                                                .foregroundColor(.secondary)
                                            Text("Camera Feed")
                                                .font(.headline)
                                                .foregroundColor(.secondary)
                                            if !isVitalMonitoringEnabled {
                                                Text("Start monitoring to see live frames")
                                                    .font(.caption)
                                                    .foregroundColor(.secondary)
                                            } else {
                                                Text("Starting camera feed...")
                                                    .font(.caption)
                                                    .foregroundColor(.secondary)
                                            }
                                        }
                                    }
                                }
                            }
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                            .clipped()
                            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                        )
                }
                .animation(.none, value: isVitalMonitoringEnabled)
                .frame(height: geo.size.height * 0.6)

                // Instruction text under the camera frame
                Text(isVitalMonitoringEnabled ? "Double tap to stop monitoring" : "Double tap to start monitoring")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .padding(.top, 4)

                ContinuousVitalsPlotView()
                    .scaleEffect(0.8)
                    .frame(maxWidth: .infinity)
                    .fixedSize(horizontal: false, vertical: true)
                
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .onLongPressGesture {
            sendGeminiRequest()
            print("longpress");
        }
        .onTapGesture(count: 2) {
            if !isVitalMonitoringEnabled {
                isVitalMonitoringEnabled = true
                startVitalsMonitoring()
            } else {
                isVitalMonitoringEnabled = false
                stopVitalsMonitoring()
            }
            print("taptap");
        }
        .padding(.horizontal)
        .onDisappear {
            stopVitalsMonitoring()
        }
    }

    func startVitalsMonitoring() {
        vitalsProcessor.startProcessing()
        vitalsProcessor.startRecording()
        startAveragesTimer()
    }

    func stopVitalsMonitoring() {
        vitalsProcessor.stopProcessing()
        vitalsProcessor.stopRecording()
        stopAveragesTimer()
    }

    func startAveragesTimer() {
        averagesTimer?.invalidate()
        averagesTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { _ in
            sendAveragesToServer()
        }
    }

    func stopAveragesTimer() {
        averagesTimer?.invalidate()
        averagesTimer = nil
    }

    func calculatePulseAverage() -> Float? {
        guard let metrics = sdk.metricsBuffer else { return nil }
        let values = metrics.pulse.rate.map { $0.value }
        guard !values.isEmpty else { return nil }
        return values.reduce(0, +) / Float(values.count)
    }

    func calculateBreathingAverage() -> Float? {
        guard let metrics = sdk.metricsBuffer else { return nil }
        let values = metrics.breathing.rate.map { $0.value }
        guard !values.isEmpty else { return nil }
        return values.reduce(0, +) / Float(values.count)
    }

    func sendAveragesToServer() {
        print("send averages")
        guard let pulseAvg = calculatePulseAverage(), let breathingAvg = calculateBreathingAverage() else { return }
        guard let url = URL(string: "http://172.20.10.4:8080/biometrics") else { return }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let json: [String: Float] = [
            "pulse_average": pulseAvg,
            "breathing_average": breathingAvg
        ]
        guard let jsonData = try? JSONSerialization.data(withJSONObject: json) else { return }
        request.httpBody = jsonData
        URLSession.shared.dataTask(with: request) { _, _, _ in }.resume()
    }
    
    func sendGeminiRequest() {
        print("send gemini")
        // 172.20.10.4
        // 10.19.133.167:8080
        guard let url = URL(string: "http://172.20.10.4:8080/gemini") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        URLSession.shared.dataTask(with: request) { _, response, error in
            if let error = error {
                print("❌ Request failed:", error)
            } else {
                print("✅ Signal sent")
            }
        }.resume()
    }

    /// Toggles camera feed display and starts processing if needed
    /// - Parameter enabled: When true, enables camera feed preview; when false, hides the camera feed
    private func toggleCameraFeedDisplay(enabled: Bool) {
        // Toggle between back and front camera each time this is called
        isUsingBackCamera.toggle()

        // Temporarily disable image output to avoid conflicts while switching
        sdk.setImageOutputEnabled(false)

        // If processing is ongoing, stop and restart around the camera switch
        let wasMonitoring = isVitalMonitoringEnabled
        if wasMonitoring {
            vitalsProcessor.stopProcessing()
        }

        if isUsingBackCamera {
            sdk.setCameraPosition(.back)
            print("Switching to back camera")
        } else {
            sdk.setCameraPosition(.front)
            print("Switching to front camera")
        }

        // Re-enable image output
        sdk.setImageOutputEnabled(true)

        // Resume processing if it was active
        if wasMonitoring {
            vitalsProcessor.startProcessing()
        }
    }
}


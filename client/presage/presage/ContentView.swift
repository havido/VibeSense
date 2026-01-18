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
        // (Required) Authentication. Only need to use one of the two options: API Key or Oauth below
        // Authentication with Oauth currently only supported for apps in testflight/appstore
        // Option 1: (authentication with api key) set apiKey. API key from https://physiology.presagetech.com. Leave default or remove if you want to use oauth. Oauth overrides api key
        let apiKey = "tdxQUC2abP82L6NgUSDGA9k7T5yzLvd139ePE6ln"
        sdk.setApiKey(apiKey)

        // Option 2: (Oauth) If you want to use Oauth, copy the Oauth config from PresageTech's developer portal (<https://physiology.presagetech.com/>) to your app's root.
        // No additional code needed for Oauth
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
                    
                    // Toggle button in top-right corner
                    VStack {
                        HStack {
                            Spacer()
                            Button(action: {
                                isCameraFeedVisible.toggle()
                                toggleCameraFeedDisplay(enabled: isCameraFeedVisible)
                            }) {
                                Image(systemName: isCameraFeedVisible ? "eye.slash" : "eye")
                                    .font(.system(size: 14, weight: .semibold))
                                    .foregroundColor(.primary)
                                    .padding(8)
                                    .background(.ultraThinMaterial, in: Circle())
                            }
                        }
                        Spacer()
                    }
                    .padding(8)
                }
                .animation(.none, value: isVitalMonitoringEnabled)
                .gesture(
                    DragGesture(minimumDistance: 20, coordinateSpace: .local)
                        .onEnded { value in
                            let horizontal = value.translation.width
                            let vertical = abs(value.translation.height)
                            if horizontal > 30 && vertical < 40 { // right swipe
                                isCameraFeedVisible.toggle()
                                toggleCameraFeedDisplay(enabled: isCameraFeedVisible)
                            }
                        }
                )
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
        guard let pulseAvg = calculatePulseAverage(), let breathingAvg = calculateBreathingAverage() else { return }
        guard let url = URL(string: "http://10.19.133.167:8080/biometrics") else { return }
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
        guard let url = URL(string: "http://10.19.133.167:8080/gemini") else { return }

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

        // Example SDK calls — replace with the correct API from SmartSpectraSwiftSDK if different
        if isUsingBackCamera {
            // Switch to back camera
            sdk.setCameraPosition(.back)
            print("Switching to back camera")
        } else {
            // Switch to front camera
            sdk.setCameraPosition(.front)
            print("Switching to front camera")
        }

        // Optionally ensure image output is enabled when toggling
        sdk.setImageOutputEnabled(true)
    }
}


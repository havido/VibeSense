import SwiftUI
import SmartSpectraSwiftSDK

struct ContentView: View {
    @ObservedObject var sdk = SmartSpectraSwiftSDK.shared
    @ObservedObject var vitalsProcessor = SmartSpectraVitalsProcessor.shared
    @State private var isVitalMonitoringEnabled: Bool = false
    @State private var showCameraFeed: Bool = false
    @State private var averagesTimer: Timer? = nil

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
        VStack {
            GroupBox(label: Text("VibeSense")) {
                ContinuousVitalsPlotView()
                Grid {
                    GridRow {
                        Text("Status: \(vitalsProcessor.statusHint)")
                    }
                    GridRow {
                        HStack {
                            Button(isVitalMonitoringEnabled ? "Stop": "Start") {
                                isVitalMonitoringEnabled.toggle()
                                if(isVitalMonitoringEnabled) {
                                    startVitalsMonitoring()
                                } else {
                                    stopVitalsMonitoring()
                                }
                            }
                        }
                    }
                }
                .padding(.horizontal, 10)
            }
        
            Button {
                    sendGeminiRequest()
                    } label: {
                        Text("GEMINI")
                            .font(.title)
                            .fontWeight(.bold)
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 128)
                            .background(Color.red)
                            .cornerRadius(16)
                            .shadow(radius: 8)
                    }
                    .padding(.horizontal)
            // Camera Preview Toggle
            HStack {
                Text("Camera Preview")
                Spacer()
                Toggle("", isOn: $showCameraFeed)
                    .onChange(of: showCameraFeed) { newValue in
                        toggleCameraFeedDisplay(enabled: newValue)
                    }
            }
            .padding(.horizontal)

            // Camera Feed (only shows when enabled)
            if showCameraFeed {
                Group {
                    if let image = vitalsProcessor.imageOutput {
                        Image(uiImage: image)
                            .resizable()
                            .aspectRatio(contentMode: .fit)
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
                .frame(height: 200)
                .cornerRadius(8)
            }

            Spacer()
        }
        .padding()
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
        // Enable image output if not enabled already
        if enabled {
            // this sets it for the shared instance of the sdk and will affect other parts of the app using the sdk
            sdk.setImageOutputEnabled(enabled)
        }

    }
}

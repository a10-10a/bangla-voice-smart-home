#include <WiFi.h>
#include <WebServer.h>

// ---------------------------------------------------------------------------
// Wi-Fi credentials — set these to your laptop's mobile hotspot
// ---------------------------------------------------------------------------
const char* WIFI_SSID     = "SSID";
const char* WIFI_PASSWORD = "PASSWORD";

// ---------------------------------------------------------------------------
// Pin assignments
// ---------------------------------------------------------------------------
const int PIN_LIGHT1     = 0;
const int PIN_LIGHT2     = 1;
const int PIN_FAN1       = 2;   // DRV8833 IN1
const int PIN_FAN2       = 3;   // DRV8833 IN3
const int PIN_STATUS_LED = 8;   // Onboard blue LED, active-LOW

const int LED_ON  = LOW;
const int LED_OFF = HIGH;

WebServer server(80);

// Wi-Fi health check interval (simple auto-reconnect for production use)
unsigned long lastWifiCheck = 0;
const unsigned long WIFI_CHECK_INTERVAL_MS = 5000;

// ---------------------------------------------------------------------------
// Blink the onboard status LED for `durationMs`, then restore it to OFF.
// Brief blocking delay is fine here since pulses are short (100-200 ms)
// and only occur on discrete events, not continuously.
// ---------------------------------------------------------------------------
void blinkStatusLed(unsigned long durationMs) {
  digitalWrite(PIN_STATUS_LED, LED_ON);
  delay(durationMs);
  digitalWrite(PIN_STATUS_LED, LED_OFF);
}

// ---------------------------------------------------------------------------
// Generic helper: set an appliance pin, blink the status LED to confirm the
// command executed, and send the plain-text HTTP reply.
// ---------------------------------------------------------------------------
void handleAppliance(int pin, int level, const char* okMessage) {
  digitalWrite(pin, level);
  blinkStatusLed(100);   // 100 ms pulse = "valid command executed"
  server.send(200, "text/plain", String("OK: ") + okMessage);
}

// ---------------------------------------------------------------------------
// Route handlers
// ---------------------------------------------------------------------------
void handleLight1On()  { handleAppliance(PIN_LIGHT1, HIGH, "Light 1 ON"); }
void handleLight1Off() { handleAppliance(PIN_LIGHT1, LOW,  "Light 1 OFF"); }
void handleLight2On()  { handleAppliance(PIN_LIGHT2, HIGH, "Light 2 ON"); }
void handleLight2Off() { handleAppliance(PIN_LIGHT2, LOW,  "Light 2 OFF"); }
void handleFan1On()    { handleAppliance(PIN_FAN1,   HIGH, "Fan 1 ON"); }
void handleFan1Off()   { handleAppliance(PIN_FAN1,   LOW,  "Fan 1 OFF"); }
void handleFan2On()    { handleAppliance(PIN_FAN2,   HIGH, "Fan 2 ON"); }
void handleFan2Off()   { handleAppliance(PIN_FAN2,   LOW,  "Fan 2 OFF"); }

void handleNotFound() {
  server.send(404, "text/plain", "ERROR: Not Found");
}

// ---------------------------------------------------------------------------
// setup()
// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("Booting ESP32-C3 Smart Home Controller...");

  pinMode(PIN_LIGHT1, OUTPUT);
  pinMode(PIN_LIGHT2, OUTPUT);
  pinMode(PIN_FAN1, OUTPUT);
  pinMode(PIN_FAN2, OUTPUT);
  digitalWrite(PIN_LIGHT1, LOW);
  digitalWrite(PIN_LIGHT2, LOW);
  digitalWrite(PIN_FAN1, LOW);
  digitalWrite(PIN_FAN2, LOW);

  pinMode(PIN_STATUS_LED, OUTPUT);
  digitalWrite(PIN_STATUS_LED, LED_OFF);   

  // --- Connect to Wi-Fi hotspot ---
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected! IP address: ");
  Serial.println(WiFi.localIP());

  blinkStatusLed(200);   

  // --- Register HTTP routes ---
  server.on("/light1/on",  HTTP_GET, handleLight1On);
  server.on("/light1/off", HTTP_GET, handleLight1Off);
  server.on("/light2/on",  HTTP_GET, handleLight2On);
  server.on("/light2/off", HTTP_GET, handleLight2Off);
  server.on("/fan1/on",    HTTP_GET, handleFan1On);
  server.on("/fan1/off",   HTTP_GET, handleFan1Off);
  server.on("/fan2/on",    HTTP_GET, handleFan2On);
  server.on("/fan2/off",   HTTP_GET, handleFan2Off);
  server.onNotFound(handleNotFound);

  server.begin();
  Serial.println("HTTP server started.");
}

// ---------------------------------------------------------------------------
// loop()
// ---------------------------------------------------------------------------
void loop() {
  if (millis() - lastWifiCheck > WIFI_CHECK_INTERVAL_MS) {
    lastWifiCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Wi-Fi disconnected — attempting reconnect...");
      WiFi.reconnect();
    }
  }
  server.handleClient();
}
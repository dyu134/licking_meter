#include <Arduino.h>
#include <LittleFS.h>
#include "Adafruit_NeoPixel.h"

// ==== Touch pin configuration ====
const uint8_t TOUCH_PINS[] = {2, 3};
const uint8_t NUM_TOUCH_PINS = 2;
const uint8_t BNC_PINS[] = {7, 8};
const uint8_t NUM_BNC_PINS = 2;
//const uint8_t LED_PINS[] = {42, 41, 40, 39};
//const uint8_t NUM_LED_PINS = 4;
const uint8_t RGB_PIN = 47;
const bool prototype  = true;

uint32_t threshold[4] = {10000, 10000};
Adafruit_NeoPixel RGB = Adafruit_NeoPixel(1, RGB_PIN, NEO_GRB + NEO_KHZ800);

uint32_t statusLedTimer = 0;
bool errorPersists = false;

void flashRed(int count) {
  errorPersists = true; // Mark error as persisting
  if (count == 1) {
    RGB.setPixelColor(0, RGB.Color(255, 0, 0));
    RGB.show();
    delay(50);
    RGB.setPixelColor(0, RGB.Color(0, 0, 0));
    RGB.show();
    delay(950);
    RGB.setPixelColor(0, RGB.Color(255, 0, 0)); // Keep Red at end
    RGB.show();
  } else if (count == 2) {
    RGB.setPixelColor(0, RGB.Color(255, 0, 0));
    RGB.show();
    delay(50);
    RGB.setPixelColor(0, RGB.Color(0, 0, 0));
    RGB.show();
    delay(50);
    RGB.setPixelColor(0, RGB.Color(255, 0, 0));
    RGB.show();
    delay(50);
    RGB.setPixelColor(0, RGB.Color(0, 0, 0));
    RGB.show();
    delay(850);
    RGB.setPixelColor(0, RGB.Color(255, 0, 0)); // Keep Red at end
    RGB.show();
  }
}

void saveThresholds() {
  errorPersists = false; // Reset error on new op
  RGB.setPixelColor(0, RGB.Color(255, 0, 0)); // Red while saving
  RGB.show();
  File f = LittleFS.open("/thr.txt", "w");
  if (!f) {
    Serial.println("Failed to open thr.txt for writing");
    flashRed(1);
    return;
  }
  for (int i = 0; i < NUM_TOUCH_PINS; i++) {
    f.println(threshold[i]);
  }
  f.close();
  RGB.setPixelColor(0, RGB.Color(0, 255, 0)); // Green on success
  RGB.show();
  statusLedTimer = millis(); // Start 1s timer
}

void loadThresholds() {
  errorPersists = false; // Reset error on new op
  RGB.setPixelColor(0, RGB.Color(0, 0, 255)); // Blue while loading
  RGB.show();
  if (!LittleFS.exists("/thr.txt")) {
    Serial.println("thr.txt not found, using defaults");
    saveThresholds();
    return;
  }
  File f = LittleFS.open("/thr.txt", "r");
  if (!f) {
    Serial.println("Failed to open thr.txt for reading");
    flashRed(2);
    return;
  }
  char line[32];
  for (int i = 0; i < NUM_TOUCH_PINS && f.available(); i++) {
    int len = f.readBytesUntil('\n', line, sizeof(line) - 1);
    line[len] = '\0';
    threshold[i] = strtoul(line, NULL, 10);
  }
  f.close();
  RGB.setPixelColor(0, RGB.Color(0, 255, 0)); // Green on success
  RGB.show();
  statusLedTimer = millis(); // Start 1s timer
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== FreeRTOS Dual-Core Touch Counter ===");

  for (int i = 0; i < NUM_BNC_PINS; i++) pinMode(BNC_PINS[i], OUTPUT);
  //for (int i = 0; i < NUM_LED_PINS; i++) pinMode(LED_PINS[i], OUTPUT);

  RGB.begin();
  RGB.setBrightness(50); // Reduce overall brightness
  RGB.show(); // Initialize all pixels to 'off'

  if (!LittleFS.begin(true)) {
    Serial.println("LittleFS Mount Failed");
    flashRed(2);
    return;
  }
  loadThresholds();
}

void handleSerialCommand() {
  if (Serial.available()) {
    char buffer[64];
    int len = Serial.readBytesUntil('\n', buffer, sizeof(buffer) - 1);
    buffer[len] = '\0';
    
    int x;
    uint32_t y;
    if (sscanf(buffer, "THR %d %u", &x, &y) == 2) {
      if (x >= 0 && x < NUM_TOUCH_PINS) {
        threshold[x] = y;
        saveThresholds();
        Serial.printf("Threshold[%d] set to %u and saved\n", x, y);
      } else {
        Serial.println("Invalid threshold index");
        flashRed(1);
      }
    }
  }
}

void loop() {
  handleSerialCommand();
  
  bool anyTouched = false;
  for (int i = 0; i < NUM_TOUCH_PINS; i++) {
    uint32_t val = 0;
    //if (prototype && (i == 2 || i == 3)) {
      // Skip P1 and P2 on prototype
      //val = 0;
    //} else {
    val = touchRead(TOUCH_PINS[i]);
    //}
    Serial.printf("P%d:%u  ", i + 1, val);
    //if (prototype && (i == 2 || i == 3)) {
      //Serial.print(" ");
    //} else {
    if (val > threshold[i]) {
      digitalWrite(BNC_PINS[i], HIGH);
      //digitalWrite(LED_PINS[i], HIGH);
      Serial.print("*");
      anyTouched = true;
    } else {
      digitalWrite(BNC_PINS[i], LOW);
      //digitalWrite(LED_PINS[i], LOW);
      Serial.print(" ");
    }
    //}
  }
  Serial.println();

  // LED logic
  if (statusLedTimer != 0) {
    if (millis() - statusLedTimer > 1000) {
      statusLedTimer = 0; // 1s passed
    }
  }

  if (statusLedTimer == 0 && !errorPersists) {
    // Idle state: loop color flash based on touch
    if (anyTouched) {
      RGB.setPixelColor(0, RGB.Color(0, 255, 255)); // White flash on touch
    } else {
      RGB.setPixelColor(0, RGB.Color(0, 0, 0)); // OFF
    }
  }
  // If errorPersists is true, we keep the last color (Red) set by flashRed
  // If statusLedTimer > 0, we keep the last color (Green/Blue/Red) set by ops

  RGB.show();
  //delay(10);
}
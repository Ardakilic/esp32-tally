#include <Arduino.h>
#include <Preferences.h>
#include <U8g2lib.h>
#include <esp_sleep.h>
#include "tally_logic.h"

constexpr int BTN_UP = 3, BTN_DOWN = 4;
constexpr uint32_t IDLE_SLEEP_MS = 60000, NVS_FLUSH_MS = 2000;

U8G2_SSD1306_128X32_UNIVISION_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE, /*clock=*/7, /*data=*/6);
Preferences prefs;
Tally tally;
bool dirty = false;
uint32_t dirty_since = 0;

static void draw() {
  char buf[8];
  snprintf(buf, sizeof buf, "%ld", (long)tally.count);
  u8g2.clearBuffer();
  u8g2.drawStr((128 - u8g2.getStrWidth(buf)) / 2, 16, buf);
  u8g2.sendBuffer();
}

static void flush() {
  if (!dirty) return;
  prefs.putInt("count", tally.count);
  dirty = false;
}

static void sleepNow() {
  flush();
  u8g2.setPowerSave(1);
  pinMode(BTN_UP, INPUT_PULLUP);
  pinMode(BTN_DOWN, INPUT_PULLUP);
  esp_deep_sleep_enable_gpio_wakeup(BIT(BTN_UP) | BIT(BTN_DOWN), ESP_GPIO_WAKEUP_GPIO_LOW);
  esp_deep_sleep_start();
}

void setup() {
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);  // USB CDC with no host attached must never stall the loop
  pinMode(BTN_UP, INPUT_PULLUP);
  pinMode(BTN_DOWN, INPUT_PULLUP);
  prefs.begin("tally");
  tally.count = prefs.getInt("count", 0);
  u8g2.begin();
  u8g2.setFont(u8g2_font_logisoso28_tn);
  u8g2.setFontPosCenter();
  draw();
  // the press that woke us from deep sleep must not count
  while (!digitalRead(BTN_UP) || !digitalRead(BTN_DOWN)) delay(10);
  tally.last_activity_ms = millis();
}

void loop() {
  uint32_t now = millis();
  if (tally.update(!digitalRead(BTN_UP), !digitalRead(BTN_DOWN), now)) {
    draw();
    dirty = true;
    dirty_since = now;
    Serial.printf("count=%ld\n", (long)tally.count);
  }
  if (dirty && now - dirty_since >= NVS_FLUSH_MS) flush();
  if (now - tally.last_activity_ms >= IDLE_SLEEP_MS) sleepNow();
  delay(5);
}

#include <Arduino.h>
#include <Preferences.h>
#include <U8g2lib.h>
#include <esp_sleep.h>
#include "tally_logic.h"

constexpr int BTN_UP = 3, BTN_DOWN = 4;
// Super Mini blue LED: active-LOW with a 10k pull-up, and a strapping pin (must be high at reset).
// Lit only while setup() runs, so a blink on every boot/wake proves the MCU is alive with a dark OLED.
constexpr int LED_PIN = 8;
constexpr uint32_t IDLE_SLEEP_MS = 60000;

U8G2_SSD1306_128X32_UNIVISION_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE, /*clock=*/7, /*data=*/6);
Preferences prefs;
Tally tally;

static void draw() {
  char buf[8];
  snprintf(buf, sizeof buf, "%ld", (long)tally.count);
  u8g2.clearBuffer();
  u8g2.drawStr((128 - u8g2.getStrWidth(buf)) / 2, 16, buf);
  u8g2.sendBuffer();
}

static void sleepNow() {
  u8g2.setPowerSave(1);
  uint64_t mask = (digitalRead(BTN_UP) ? BIT(BTN_UP) : 0) | (digitalRead(BTN_DOWN) ? BIT(BTN_DOWN) : 0);
  if (mask) esp_deep_sleep_enable_gpio_wakeup(mask, ESP_GPIO_WAKEUP_GPIO_LOW);  // a held/stuck pin would re-wake instantly
  esp_deep_sleep_start();
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);  // USB CDC with no host attached must never stall the loop
  Serial.printf("boot reset=%d wake=%d\n", (int)esp_reset_reason(), (int)esp_sleep_get_wakeup_cause());
  pinMode(BTN_UP, INPUT_PULLUP);
  pinMode(BTN_DOWN, INPUT_PULLUP);
  prefs.begin("tally");
  tally.count = prefs.getInt("count", 0);
  Serial.printf("count=%ld (restored)\n", (long)tally.count);
  u8g2.begin();
  u8g2.setFont(u8g2_font_logisoso28_tn);
  u8g2.setFontPosCenter();
  draw();
  digitalWrite(LED_PIN, HIGH);
  pinMode(LED_PIN, INPUT);  // the pull-up keeps it off through deep sleep at zero drive
  // Seed instead of waiting for release: a stuck-LOW button must not block boot and drain the cell.
  tally.up.raw = tally.up.stable = !digitalRead(BTN_UP);
  tally.down.raw = tally.down.stable = !digitalRead(BTN_DOWN);
  tally.combo = tally.up.stable || tally.down.stable;  // the wake press's release must not count
  tally.last_activity_ms = millis();
}

void loop() {
  uint32_t now = millis();
  if (tally.update(!digitalRead(BTN_UP), !digitalRead(BTN_DOWN), now)) {
    draw();
    // Write per click: NVS is log-structured, a 4-byte entry per click into the 20 KB default
    // partition is tens of millions of clicks before wear matters, and a power cut never loses one.
    prefs.putInt("count", tally.count);
    Serial.printf("count=%ld\n", (long)tally.count);
  }
  if (now - tally.last_activity_ms >= IDLE_SLEEP_MS) sleepNow();
  delay(5);
}

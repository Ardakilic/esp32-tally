#include <Arduino.h>
#include <Preferences.h>
#include <U8g2lib.h>
#include <Wire.h>
#include <esp_sleep.h>
#include "grind_chart.h"
#include "sleep_logic.h"
#include "tally_logic.h"

constexpr int BTN_UP = 3, BTN_DOWN = 4;
// Super Mini blue LED: active-LOW with a 10k pull-up, and a strapping pin (must be high at reset).
// Lit only while setup() runs, so a blink on every boot/wake proves the MCU is alive with a dark OLED.
constexpr int LED_PIN = 8;
constexpr uint32_t IDLE_SLEEP_MS = 30000;
#ifndef SAVE_DELAY_MS
#define SAVE_DELAY_MS 2000  // see platformio.ini build_flags
#endif

U8G2_SSD1306_128X32_UNIVISION_F_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE, /*clock=*/7, /*data=*/6);
Preferences prefs;
Tally tally;
SaveDelay save;

// Baselines in the default U8g2 mode: a glyph with no descent fills the rows just above y.
constexpr int BIG_BASELINE = 30;  // logisoso28 (28 px digits): rows 2..29, the same with or without labels
constexpr int LABEL_GAP = 6;      // px between the digits and the label column

static void draw() {
  char num[8];
  snprintf(num, sizeof num, "%ld", (long)tally.count);
  const char *names[GRIND_MAX_LINES];
  int n = grind_matches(tally.count, names, GRIND_MAX_LINES);
  if (n > GRIND_MAX_LINES) n = GRIND_MAX_LINES;
  // 3 lines of 6x10 (10 px pitch, 7 px caps) fill the 32 px height; a 4th needs 5x8 (8 px, 6 px caps)
  const uint8_t *font = n > 3 ? u8g2_font_5x8_tf : u8g2_font_6x10_tf;
  int pitch = n > 3 ? 8 : 10, cap = n > 3 ? 6 : 7;
  u8g2.clearBuffer();
  u8g2.setFont(font);
  int lw = 0;
  for (int i = 0; i < n; i++) lw = max(lw, (int)u8g2.getStrWidth(names[i]));
  u8g2.setFont(u8g2_font_logisoso28_tn);
  int nw = u8g2.getStrWidth(num);
  int gap = n ? LABEL_GAP : 0;  // no labels: the digits alone are centred
  int x0 = max(0, (128 - (nw + gap + lw)) / 2);  // an over-long name clips at the right edge
  u8g2.drawStr(x0, BIG_BASELINE, num);
  u8g2.setFont(font);
  int top = (32 - pitch * n) / 2;  // the block of n lines is centred vertically
  for (int i = 0; i < n; i++) u8g2.drawStr(x0 + nw + gap, top + pitch * i + 1 + cap, names[i]);
  u8g2.sendBuffer();
}

static void flush() {
  if (!save.dirty) return;
  prefs.putInt("count", tally.count);
  save.dirty = false;
}

static bool displayOn = false;

static void armWake() {
  // Clear retained config: sleepNow() arms twice and enable() ORs, so without
  // this the second call would keep the first call's source instead of latest winning.
  esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_GPIO);
  esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_TIMER);
  bool upHigh = digitalRead(BTN_UP);
  bool downHigh = digitalRead(BTN_DOWN);
  static_assert(SLEEP_BTN_UP == BTN_UP && SLEEP_BTN_DOWN == BTN_DOWN, "sleep_logic pins must match wiring");
  uint64_t mask = buildWakeMask(upHigh, downHigh);
  if (mask) {
    esp_deep_sleep_enable_gpio_wakeup(mask, ESP_GPIO_WAKEUP_GPIO_LOW);  // a held/stuck pin would re-wake instantly
  } else {
    esp_sleep_enable_timer_wakeup(TIMER_FALLBACK_US);  // mask==0, both stuck LOW: timer failsafe, see sleep_logic.h
  }
}

static void sleepNow() {
  armWake();  // arm first so a hung display/NVS below cannot block sleep
  if (displayOn) {
    (void)u8g2.setPowerSave(1);  // best effort (bounded by Wire.setTimeOut): sleep proceeds even on I2C NACK
    displayOn = false;
  }
  flush();
  armWake();  // re-read pins: latest state wins, timer fallback if both now stuck
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
  u8g2.setBusClock(400000);  // a full frame takes ~50 ms at the 100 kHz default and would starve button polling
  Wire.setTimeOut(20);  // bound each I2C txn so a dead display cannot stall sleep entry (default 50 ms)
  u8g2.begin();
  draw();
  displayOn = true;
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
    displayOn = true;
    // Deferred: written SAVE_DELAY_MS after the last change so a burst of clicks is one NVS write;
    // sleepNow() flushes first, so deep sleep never loses a pending count.
    save.touch(now);
    Serial.printf("count=%ld\n", (long)tally.count);
  }
  if (save.due(now, SAVE_DELAY_MS)) flush();
  if (now - tally.last_activity_ms >= IDLE_SLEEP_MS) sleepNow();
  delay(5);
}

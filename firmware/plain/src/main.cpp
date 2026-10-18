#include <Arduino.h>
#include <Preferences.h>
#include <U8g2lib.h>
#include <esp_sleep.h>
#include "grind_chart.h"
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
// .rtc.data: kept through deep sleep, reloaded (zeroed) by the bootloader on every other reset
RTC_DATA_ATTR WakePlan wake;

// RTC memory survives deep sleep and software/panic/WDT/brownout resets; it is lost on a power
// cut and (most likely) on the RST key, which powers the C3 down. So a bad magic at boot = power
// was cut (switch off, a tripped/latched cell protection, a broken joint) or RST was pressed.
struct Trace { uint32_t magic, sleeps, timer_wakes; uint8_t stage; };  // no initializers: never touched at startup
RTC_NOINIT_ATTR Trace trace;
constexpr uint32_t TRACE_MAGIC = 0x7A11C0DE;
// Where the firmware last was; read back at the next boot as `last`.
enum Stage : uint8_t { ST_LOST, ST_BOOT, ST_AWAKE, ST_FLUSH, ST_OLED_OFF, ST_SLEEP };
static bool warm;    // RTC trace intact at this boot
static uint8_t last;  // stage the previous run stopped in (ST_LOST = power cut or RST key)
BootLog<8> bootlog;  // NVS "bootlog": one record per boot that was not a deep-sleep wake

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

static uint8_t downBits() { return (digitalRead(BTN_UP) ? 0 : 1) | (digitalRead(BTN_DOWN) ? 0 : 2); }

[[noreturn]] static void sleepArmed() {
  uint32_t s = wake.plan(WakePlan::BOTH & ~downBits());
  uint64_t mask = (wake.armed & 1 ? BIT(BTN_UP) : 0) | (wake.armed & 2 ? BIT(BTN_DOWN) : 0);
  if (mask) esp_deep_sleep_enable_gpio_wakeup(mask, ESP_GPIO_WAKEUP_GPIO_LOW);  // a held/stuck pin would re-wake instantly
  esp_sleep_enable_timer_wakeup(s * 1000000ULL);  // always armed: re-checks a held pin, and the hourly safety wake
  ++trace.sleeps;
  trace.stage = ST_SLEEP;
  esp_deep_sleep_start();
}

static void sleepNow() {
  trace.stage = ST_FLUSH;
  flush();
  trace.stage = ST_OLED_OFF;
  u8g2.setPowerSave(1);  // 0xAE is synchronous and the OLED stays powered: no delay needed before sleep
  sleepArmed();
}

static const char *resetName(int r) {
  static const char *const names[] = {"unknown", "power-on", "ext", "sw", "panic", "int-wdt", "task-wdt", "wdt",
                                      "deep-sleep", "brownout", "sdio", "usb", "jtag", "efuse", "pwr-glitch", "cpu-lockup"};
  return r >= 0 && r < (int)(sizeof names / sizeof *names) ? names[r] : "?";
}

static const char *stageName(int s) {
  static const char *const names[] = {"rtc lost", "boot", "awake", "flush", "oled-off", "sleep"};
  return s >= 0 && s < (int)(sizeof names / sizeof *names) ? names[s] : "?";
}

// At boot and again on any serial input: this boot, then the kept log, oldest first.
static void report() {
  int r = esp_reset_reason();
  Serial.printf("boot reset=%d (%s) wake=%d rtc=%s last=%s sleeps=%lu timer_wakes=%lu\n", r, resetName(r),
                (int)esp_sleep_get_wakeup_cause(), warm ? "warm" : "cold", stageName(last),
                (unsigned long)trace.sleeps, (unsigned long)trace.timer_wakes);
  for (int i = 0, n = bootlog.size(); i < n; i++) {
    const auto &e = bootlog.at(i);
    Serial.printf("log %lu/%lu: reset=%d (%s) last=%s sleeps=%u\n", (unsigned long)(bootlog.total - n + i + 1),
                  (unsigned long)bootlog.total, e.reason, resetName(e.reason), stageName(e.stage), e.sleeps);
  }
}

void setup() {
  // Catch-all: any hang in I2C, NVS, loop() or sleep entry becomes a task-WDT panic + reboot (5 s,
  // CONFIG_ESP_TASK_WDT_PANIC=y) instead of a dark, dead counter; loopTask feeds it before every loop().
  enableLoopWDT();
  warm = trace.magic == TRACE_MAGIC;
  last = warm ? trace.stage : ST_LOST;
  if (!warm) trace = {TRACE_MAGIC, 0, 0, ST_LOST};
  trace.stage = ST_BOOT;
  pinMode(BTN_UP, INPUT_PULLUP);
  pinMode(BTN_DOWN, INPUT_PULLUP);
  // Silent timer wake: back to sleep unless an armed button is down. Must stay before the LED,
  // Serial, NVS and the OLED, so the hourly wake costs no blink, no flash write, no redraw.
  if (esp_sleep_get_wakeup_cause() == ESP_SLEEP_WAKEUP_TIMER) {
    delayMicroseconds(100);  // an unarmed pin had no pull-up while asleep
    ++trace.timer_wakes;
    if (!wake.is_press(downBits())) sleepArmed();
  }
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  Serial.setTxBufferSize(1024);  // before begin(); with no host the ring keeps the newest bytes for a later terminal
  Serial.begin(115200);
  Serial.setTxTimeoutMs(0);  // USB CDC with no host attached must never stall the loop (so never Serial.flush())
  prefs.begin("tally");
  // Read on every boot so a report after a button wake still lists it; written only by the boots it records.
  if (prefs.getBytesLength("bootlog") == sizeof bootlog) prefs.getBytes("bootlog", &bootlog, sizeof bootlog);
  esp_reset_reason_t reason = esp_reset_reason();
  if (reason != ESP_RST_DEEPSLEEP) {
    uint16_t sleeps = warm ? (trace.sleeps < 65535 ? trace.sleeps : 65535) : 0;
    bootlog.push({(uint8_t)reason, last, sleeps});
    prefs.putBytes("bootlog", &bootlog, sizeof bootlog);
  }
  report();
  tally.count = prefs.getInt("count", 0);
  Serial.printf("count=%ld (restored)\n", (long)tally.count);
  u8g2.setBusClock(400000);  // a full frame takes ~50 ms at the 100 kHz default and would starve button polling
  u8g2.begin();
  draw();
  digitalWrite(LED_PIN, HIGH);
  pinMode(LED_PIN, INPUT);  // the pull-up keeps it off through deep sleep at zero drive
  // Seed instead of waiting for release: a stuck-LOW button must not block boot and drain the cell.
  tally.up.raw = tally.up.stable = !digitalRead(BTN_UP);
  tally.down.raw = tally.down.stable = !digitalRead(BTN_DOWN);
  tally.combo = tally.up.stable || tally.down.stable;  // the wake press's release must not count
  tally.last_activity_ms = millis();
  trace.stage = ST_AWAKE;
}

void loop() {
  uint32_t now = millis();
  if (tally.update(!digitalRead(BTN_UP), !digitalRead(BTN_DOWN), now)) {
    draw();
    // Deferred: written SAVE_DELAY_MS after the last change so a burst of clicks is one NVS write;
    // sleepNow() flushes first, so deep sleep never loses a pending count.
    save.touch(now);
    Serial.printf("count=%ld\n", (long)tally.count);
  }
  if (save.due(now, SAVE_DELAY_MS)) flush();
  if (now - tally.last_activity_ms >= IDLE_SLEEP_MS) sleepNow();
  if (Serial.available()) {  // any key: print the report again (the boot one is usually missed)
    while (Serial.available()) Serial.read();
    report();
  }
  delay(5);
}

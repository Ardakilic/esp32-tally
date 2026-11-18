// Waveshare RP2040-Zero build: same behaviour as firmware/plain/src/main.cpp (ESP32-C3 Super Mini), with
// LittleFS instead of NVS and RP2040 DORMANT + a watchdog reboot instead of ESP32 deep sleep.
#include <Arduino.h>
#include <Wire.h>
#include <LittleFS.h>
#include <U8g2lib.h>
#include <Adafruit_NeoPixel.h>
#include <hardware/clocks.h>
#include <hardware/gpio.h>
#include <hardware/pll.h>
#include <hardware/structs/rosc.h>
#include <hardware/watchdog.h>
#include <hardware/xosc.h>
#include "grind_chart.h"
#include "tally_logic.h"

// Buttons to GND. OLED on I2C1 (Wire1): RP2040 I2C pins come in fixed pairs, GP14/GP15 is one, and on the
// perfboard it sits in col 9 rows 8/7, the column that also holds the 3V3/GND pins (rows 2/1) the OLED needs
// (crossing-free wiring).
constexpr int BTN_UP = 26, BTN_DOWN = 8;
constexpr int OLED_SDA = 14, OLED_SCL = 15;
constexpr uint32_t IDLE_SLEEP_MS = 30000;
// Watchdog scratch[0] = "this boot is a dormant wake": survives the watchdog reboot, cleared by power-on/RUN.
// The bootrom and the SDK use only scratch[4..7].
constexpr uint32_t WAKE_MAGIC = 0x7a11d0e5u;
#ifndef SAVE_DELAY_MS
#define SAVE_DELAY_MS 2000  // see platformio.ini build_flags
#endif

// U8g2 passes constructor clock/data pins to Wire.begin() only on ESP cores; on Arduino-Pico the pins are set
// on Wire1 itself (setSDA/setSCL in setup(), before begin()).
U8G2_SSD1306_128X32_UNIVISION_F_2ND_HW_I2C u8g2(U8G2_R0, U8X8_PIN_NONE);
// On-board WS2812 (GP16, powered from 3V3 permanently). Lit only while setup() runs, so a blink on every
// boot/wake proves the MCU is alive with a dark OLED; stays lit = setup() hung (e.g. a Wire pin panic).
Adafruit_NeoPixel pixel(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);
Tally tally;
SaveDelay save;

// Baselines in the default U8g2 mode: a glyph with no descent fills the rows just above y.
constexpr int BIG_BASELINE = 30;  // logisoso28 (28 px digits): rows 2..29, the same with or without labels
constexpr int LABEL_GAP = 6;      // px between the digits and the label column

// Keep in sync with draw() in firmware/plain/src/main.cpp (same panel, same fonts, same layout).
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

// One 4-byte file, rewritten in place: open "r+" + write + close is ONE metadata commit that carries the new
// count, so a power cut keeps the old or the new value (EEPROM emulation would erase-then-program one sector and
// could lose it all). Two Arduino-Pico 6.1.0 wrapper defaults break that, so neither is used:
//  - "w" adds O_TRUNC and LittleFSImpl::open() syncs right after opening, which commits an EMPTY file before the
//    write (a cut there reads back as 0);
//  - the default time callback (time(nullptr)) adds a 't' attribute commit after every close (and a probe open).
// Host replay of littlefs 2.11 at this geometry: 1 commit and ~1 erase per 16 saves vs 3 and ~1 per 4 with both.
static int32_t loadCount() {
  LittleFS.setTimeCallback(nullptr);  // before begin(): begin() passes it to the FS, open() to every File
  LittleFS.begin();  // formats a blank/unmountable partition (autoFormat defaults to true)
  int32_t v = 0;
  File f = LittleFS.open("/count", "r");
  if (f) {
    if (f.read(reinterpret_cast<uint8_t *>(&v), sizeof v) != sizeof v) v = 0;
    f.close();
  }
  return (v >= 0 && v <= Tally::MAX) ? v : 0;
}

// True only if c reads back: File::close() (the commit) drops littlefs's return code, so read-back is the only
// way to learn that the save landed.
static bool storeCount(int32_t c) {
  File f = LittleFS.open("/count", "r+");     // no truncate: nothing reaches flash until close() commits
  if (!f) f = LittleFS.open("/count", "w");  // first save only: creates the file (an empty one reads back as 0)
  if (!f) return false;
  bool ok = f.write(reinterpret_cast<const uint8_t *>(&c), sizeof c) == sizeof c;
  f.close();
  int32_t v = -1;
  File r = LittleFS.open("/count", "r");
  if (r) {
    ok = ok && r.read(reinterpret_cast<uint8_t *>(&v), sizeof v) == sizeof v;
    r.close();
  }
  return ok && v == c;
}

// A failed save keeps the count pending and is retried SAVE_DELAY_MS later, SAVE_TRIES attempts per burst (a new
// click starts over): bounded, so a broken filesystem cannot keep the chip awake or grind the flash.
constexpr int SAVE_TRIES = 3;
static int save_failures = 0;

static void flush(uint32_t now) {
  if (!save.dirty || save_failures >= SAVE_TRIES) return;
  if (storeCount(tally.count)) {
    save.dirty = false;
    save_failures = 0;
  } else {
    save.touch(now);
    Serial.printf("save failed (%d/%d)\n", ++save_failures, SAVE_TRIES);
  }
}

// Wake source per pin, chosen from its level now: a released (high) pin wakes on LEVEL_LOW (its press), a
// held/stuck (low) pin on LEVEL_HIGH (its release), so there is always a wake source (with none the XOSC
// never restarts) and a stuck button cannot keep the chip awake. Levels are not latched (datasheet 2.19.3):
// no stale event from the awake period can fire, and a change between gpio_get() and the enable wakes at
// once instead of being lost (an edge armed for the old level would miss it).
static void armWake(uint pin) {
  constexpr uint32_t ALL = GPIO_IRQ_LEVEL_LOW | GPIO_IRQ_LEVEL_HIGH | GPIO_IRQ_EDGE_FALL | GPIO_IRQ_EDGE_RISE;
  gpio_set_dormant_irq_enabled(pin, ALL, false);  // the SDK call also acknowledges latched edges
  gpio_set_dormant_irq_enabled(pin, gpio_get(pin) ? GPIO_IRQ_LEVEL_LOW : GPIO_IRQ_LEVEL_HIGH, true);
}

// DORMANT (all clocks and oscillators stopped), then a fresh boot: every wake runs setup() like the ESP32's
// deep-sleep wake, so nothing has to be restored by hand. Follows pico-extras sleep.c.
[[noreturn]] static void dormantThenReboot() {
  noInterrupts();  // nothing (USB IRQ, alarms) may run while clocks are torn down; we never return
  armWake(BTN_UP);
  armWake(BTN_DOWN);
  // Everything onto the 12 MHz crystal, so the PLLs and the ring oscillator can be stopped.
  clock_configure(clk_ref, CLOCKS_CLK_REF_CTRL_SRC_VALUE_XOSC_CLKSRC, 0, XOSC_HZ, XOSC_HZ);
  clock_configure(clk_sys, CLOCKS_CLK_SYS_CTRL_SRC_VALUE_CLK_REF, 0, XOSC_HZ, XOSC_HZ);
  clock_stop(clk_usb);
  clock_stop(clk_adc);
  clock_stop(clk_rtc);
  clock_configure(clk_peri, 0, CLOCKS_CLK_PERI_CTRL_AUXSRC_VALUE_CLK_SYS, XOSC_HZ, XOSC_HZ);
  pll_deinit(pll_sys);  // DORMANT does not halt the PLLs (datasheet 2.11.3)
  pll_deinit(pll_usb);
  const uint32_t rosc_ctrl = rosc_hw->ctrl;
  rosc_hw->ctrl = (rosc_ctrl & ~ROSC_CTRL_ENABLE_BITS) | (ROSC_CTRL_ENABLE_VALUE_DISABLE << ROSC_CTRL_ENABLE_LSB);
  xosc_dormant();  // all clocks stop here; a wake level restarts the XOSC and execution continues
  // The watchdog reboot resets CLOCKS (clk_ref back on the ROSC) but not the ROSC itself (the SDK's PSM WDSEL
  // spares ROSC/XOSC): restart it first, or the chip reboots into a dead clock and locks up.
  rosc_hw->ctrl = (rosc_ctrl & ~ROSC_CTRL_ENABLE_BITS) | (ROSC_CTRL_ENABLE_VALUE_ENABLE << ROSC_CTRL_ENABLE_LSB);
  while (!(rosc_hw->status & ROSC_STATUS_STABLE_BITS)) {
  }
  watchdog_hw->scratch[0] = WAKE_MAGIC;
  // 10 ms watchdog timer reboot (getResetReason() == SOFT_RESET; a delay-0 trigger would misreport as
  // PWRON_RESET). The watchdog tick runs from clk_ref = XOSC here, so the countdown works.
  rp2040.reboot();  // spins until the reset but is not declared noreturn, hence the loop
  while (true) {
  }
}

static void sleepNow() {
  if (!save_failures) flush(millis());  // the ordinary pending save; flash writes need the normal clocks
  // DORMANT ends in a reboot, which drops RAM: with a failed save still retrying (loop(), every SAVE_DELAY_MS),
  // stay awake; once the tries are spent, sleep anyway (losing the burst, as a power cut would) — staying up
  // for good would drain the cell
  if (save.dirty && save_failures < SAVE_TRIES) return;
  u8g2.setPowerSave(1);  // blocking I2C, done before clk_sys/clk_peri change
  pixel.clear();
  pixel.show();          // already dark since setup(); re-latched black for certainty
  delay(1);              // let the PIO shift the last bits out (> 280 us low latch) before its clock stops
  Serial.flush();
  dormantThenReboot();
}

void setup() {
  pixel.begin();
  pixel.setPixelColor(0, pixel.Color(0, 0, 16));  // dim blue: the 3rd byte in both GRB and RGB order
  pixel.show();
  Serial.begin(115200);  // USB CDC: with no host (or the port closed) writes are dropped at once, never block
  const bool woke = watchdog_hw->scratch[0] == WAKE_MAGIC;
  watchdog_hw->scratch[0] = 0;
  Serial.printf("boot reset=%d wake=%d\n", (int)rp2040.getResetReason(), (int)woke);
  pinMode(BTN_UP, INPUT_PULLUP);  // RP2040 pads come out of reset with the pull-DOWN on
  pinMode(BTN_DOWN, INPUT_PULLUP);
  tally.count = loadCount();
  Serial.printf("count=%ld (restored)\n", (long)tally.count);
  Wire1.setSDA(OLED_SDA);  // before begin(): a non-I2C1 pin, or a change after begin(), panics
  Wire1.setSCL(OLED_SCL);
  u8g2.setBusClock(400000);  // a full frame takes ~50 ms at the 100 kHz default and would starve button polling
  u8g2.begin();
  draw();
  pixel.clear();
  pixel.show();
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
    // Deferred: written SAVE_DELAY_MS after the last change so a burst of clicks is one flash write;
    // sleepNow() flushes first, so DORMANT never loses a pending count.
    save.touch(now);
    save_failures = 0;  // a new burst gets fresh save attempts
    Serial.printf("count=%ld\n", (long)tally.count);
  }
  if (save.due(now, SAVE_DELAY_MS)) flush(now);
  if (now - tally.last_activity_ms >= IDLE_SLEEP_MS) sleepNow();
  delay(5);
}

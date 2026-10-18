#pragma once
#include <cstdint>

// Button/count state machine, pure C++ so it compiles on the host for the self-test.
struct Tally {
  static constexpr uint32_t DEBOUNCE_MS = 20, COMBO_MS = 1000;
  static constexpr int32_t MAX = 99999;

  struct Btn {
    bool raw = false, stable = false;
    uint32_t since = 0;  // last raw change; for a held button this is the press time
  };

  int32_t count = 0;
  uint32_t last_activity_ms = 0;
  Btn up, down;
  bool combo = false;  // reset fired; swallow both releases until both buttons are up

  // +1 debounced press, -1 debounced release, 0 nothing
  static int edge(Btn &b, bool raw, uint32_t now) {
    if (raw != b.raw) { b.raw = raw; b.since = now; }
    if (raw == b.stable || now - b.since < DEBOUNCE_MS) return 0;
    b.stable = raw;
    return raw ? 1 : -1;
  }

  // Returns true when count changed. Call every few ms.
  bool update(bool up_raw, bool down_raw, uint32_t now) {
    int eu = edge(up, up_raw, now), ed = edge(down, down_raw, now);
    if (eu || ed) last_activity_ms = now;
    int32_t before = count;
    if (!combo && up.stable && down.stable &&
        now - up.since >= COMBO_MS && now - down.since >= COMBO_MS) {
      combo = true;
      count = 0;
    }
    if (!combo) {
      if (eu < 0 && count < MAX) ++count;
      if (ed < 0 && count > 0) --count;
    }
    if (!up.stable && !down.stable) combo = false;
    return count != before;
  }
};

// One NVS write per burst: every change restarts the delay; due() once delay_ms passed with no change.
struct SaveDelay {
  bool dirty = false;
  uint32_t since = 0;
  void touch(uint32_t now) { dirty = true; since = now; }
  bool due(uint32_t now, uint32_t delay_ms) const { return dirty && now - since >= delay_ms; }
};

// Deep-sleep wake plan (bit 1 = UP, 2 = DOWN). Every sleep arms a timer besides the GPIO wake of
// the buttons that are up: a held/stuck button stays out of the GPIO mask (its low level would
// re-wake at once) and is re-checked on a backoff, and the hourly wake re-arms even if a GPIO wake
// never comes. Limitation: a button left unarmed (held at sleep) that is down at a timer wake counts
// as still stuck, so after a >= 30 s hold a new press of that same button is only seen after a later
// re-arm (the next timer wake that finds it up).
struct WakePlan {
  static constexpr uint8_t BOTH = 3;
  static constexpr uint32_t RETRY_MIN_S = 2, RETRY_MAX_S = 600, SAFETY_S = 3600;
  uint8_t armed = 0;     // buttons GPIO-armed for the current sleep
  uint32_t retry_s = 0;  // 0 = both were up; else the backoff while one is down

  // Sets armed, returns the timer interval in s.
  uint32_t plan(uint8_t up) {
    armed = up & BOTH;
    if (armed == BOTH) { retry_s = 0; return SAFETY_S; }
    retry_s = !retry_s ? RETRY_MIN_S : retry_s * 2 < RETRY_MAX_S ? retry_s * 2 : RETRY_MAX_S;
    return retry_s;
  }
  // Timer wake: an armed button that is down = a press that raced the timer.
  bool is_press(uint8_t down) const { return armed & down; }
};

// The last N boots that were not a deep-sleep wake; stage 0 = RTC memory lost (power cut).
// Stored as one NVS blob, so it stays a plain fixed-size struct.
template <int N> struct BootLog {
  struct Rec { uint8_t reason, stage; uint16_t sleeps; };
  Rec rec[N] = {};
  uint32_t total = 0;
  void push(Rec r) { rec[total % N] = r; ++total; }  // overwrites the oldest
  int size() const { return total < (uint32_t)N ? (int)total : N; }
  const Rec &at(int i) const { return rec[(total - size() + i) % N]; }  // i-th oldest kept
};

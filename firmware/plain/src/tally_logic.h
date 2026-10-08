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

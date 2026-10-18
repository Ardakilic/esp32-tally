#pragma once
#include <cstdint>

// Deep-sleep wake-mask logic, pure C++ so it compiles on the host for the self-test.
// Mirrors firmware/plain/src/main.cpp sleepNow(): with INPUT_PULLUP buttons, a HIGH
// pin is released (wake on LOW press) and a LOW pin is held/stuck (excluded from the
// mask so it can't re-wake instantly). When both pins are stuck LOW the mask is 0
// and no GPIO can wake us, so the caller must arm the timer failsafe instead.
constexpr int SLEEP_BTN_UP = 3;
constexpr int SLEEP_BTN_DOWN = 4;
constexpr uint64_t SLEEP_WAKE_MASK_ALL = (1ULL << SLEEP_BTN_UP) | (1ULL << SLEEP_BTN_DOWN);  // 0x18

// Failsafe: if no GPIO can wake us, wake on a timer so a stuck button can't brick
// the device in deep sleep. 90 s keeps the cell cost negligible (~one wake per 3x
// the 30 s idle timeout) while recovering quickly.
constexpr uint64_t TIMER_FALLBACK_US = 90ULL * 1000000ULL;

inline uint64_t buildWakeMask(bool upHigh, bool downHigh) {
  return (upHigh ? (1ULL << SLEEP_BTN_UP) : 0ULL) | (downHigh ? (1ULL << SLEEP_BTN_DOWN) : 0ULL);
}

// Timer is needed exactly when the GPIO mask is empty.
inline bool needsTimerFallback(uint64_t mask) { return mask == 0; }
inline bool shouldArmTimer(uint64_t mask) { return needsTimerFallback(mask); }

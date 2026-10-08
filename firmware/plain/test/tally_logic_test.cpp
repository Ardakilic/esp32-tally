// Host self-test, no framework:
//   docker run --rm -v "$PWD":/work -w /work gcc:14 sh -c 'g++ -std=c++17 -Wall -Wextra -Werror -Isrc test/tally_logic_test.cpp -o /tmp/t && /tmp/t'
#include <cassert>
#include <cstdio>
#include "tally_logic.h"

static Tally t;
static uint32_t now = 1000;

// Hold the raw button state for `ms`, ticking every 5 ms like the firmware loop.
static bool hold(bool up, bool down, uint32_t ms) {
  bool changed = false;
  for (uint32_t end = now + ms; now < end; now += 5) changed |= t.update(up, down, now);
  return changed;
}

int main() {
  // click = press then release
  assert(!hold(true, false, 50));
  assert(hold(false, false, 50));
  assert(t.count == 1);
  assert(t.last_activity_ms > 1000);

  // decrement stops at 0
  hold(false, true, 50); hold(false, false, 50);
  assert(t.count == 0);
  hold(false, true, 50);
  assert(!hold(false, false, 50));
  assert(t.count == 0);

  // clamp at 99999
  t.count = Tally::MAX;
  hold(true, false, 50);
  assert(!hold(false, false, 50));
  assert(t.count == Tally::MAX);

  // bounce shorter than 20 ms is ignored
  t.count = 7;
  hold(true, false, 10); hold(false, false, 50);
  assert(t.count == 7);
  // bounce at the start of a real press still yields exactly one click
  hold(true, false, 10); hold(false, false, 5); hold(true, false, 50); hold(false, false, 50);
  assert(t.count == 8);

  // both held < 1 s is not a reset
  hold(true, true, 500); hold(false, false, 50);
  assert(t.count == 8);

  // both held >= 1 s resets and the two releases do not count
  hold(true, false, 30);
  hold(true, true, 1100);
  assert(t.count == 0);
  assert(!hold(false, true, 50));
  assert(!hold(false, false, 50));
  assert(t.count == 0);
  // and the machine is usable again afterwards
  hold(true, false, 50); hold(false, false, 50);
  assert(t.count == 1);

  puts("OK");
  return 0;
}

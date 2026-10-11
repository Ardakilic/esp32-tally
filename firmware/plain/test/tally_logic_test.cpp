// Host self-test, no framework:
//   docker run --rm -v "$PWD/firmware":/work -w /work/plain gcc:14 sh -c 'g++ -std=c++17 -Wall -Wextra -Werror -Isrc -I../common test/tally_logic_test.cpp -o /tmp/t && /tmp/t'
#include <cassert>
#include <cstdio>
#include <cstring>
#include "grind_chart.h"
#include "tally_logic.h"

static Tally t;
static uint32_t now = 1000;

// Hold the raw button state for `ms`, ticking every 5 ms like the firmware loop.
static bool hold(bool up, bool down, uint32_t ms) {
  bool changed = false;
  for (uint32_t end = now + ms; now < end; now += 5) changed |= t.update(up, down, now);
  return changed;
}

// SaveDelay driven like main.cpp's loop; `writes` stands in for prefs.putInt.
constexpr uint32_t SAVE_MS = 2000;
static SaveDelay sv;
static int writes = 0;
static int32_t written = -1;
static void tick(bool up, bool down) {
  if (t.update(up, down, now)) sv.touch(now);
  if (sv.due(now, SAVE_MS)) { ++writes; written = t.count; sv.dirty = false; }
  now += 5;
}
static void run(bool up, bool down, uint32_t ms) { for (uint32_t end = now + ms; now < end;) tick(up, down); }
// one click, padded to `period` ms
static void click(uint32_t period) { run(true, false, 50); run(false, false, period - 50); }

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

  // seeded like setup(): the wake press is still held, its release must not count
  t = Tally{};
  t.up.raw = t.up.stable = true;
  t.combo = true;
  assert(!hold(false, false, 50));
  hold(true, false, 50);
  assert(hold(false, false, 50));
  assert(t.count == 1);
  // DOWN stuck low since boot: UP clicks (and a long UP hold) neither count nor reset
  t = Tally{};
  t.count = 5;
  t.down.raw = t.down.stable = true;
  t.combo = true;
  for (int i = 0; i < 3; ++i) { hold(true, true, 50); assert(!hold(false, true, 50)); }
  hold(true, true, 1100); hold(false, true, 50);
  assert(t.count == 5);

  // grind chart: rows are sane
  for (const GrindRange &r : GRIND_CHART) {
    assert(r.from >= 0 && r.from <= r.to);
    assert(r.name && r.name[0]);
  }
  // grind_matches agrees with a plain re-implementation for every count, whatever the table holds
  long busiest = 0;
  int most = 0;
  const char *busiest_first = nullptr;
  for (long c = 0; c <= 100; ++c) {
    const char *want[16];
    int k = 0;
    for (const GrindRange &r : GRIND_CHART)
      if (c >= r.from && c <= r.to) { assert(k < 16); want[k++] = r.name; }
    const char *got[16];
    assert(grind_matches(c, got, 16) == k);
    for (int i = 0; i < k; ++i) assert(got[i] == want[i]);
    // max = 0 writes nothing (out may be null) and still reports every match
    assert(grind_matches(c, nullptr, 0) == k);
    if (k > most) { most = k; busiest = c; busiest_first = want[0]; }
  }
  // capped at 1: the first match in table order is kept, the return value is still the full count
  if (most) {
    const char *one[1];
    assert(grind_matches(busiest, one, 1) == most);
    assert(one[0] == busiest_first);
  }

  // shipped table; update if you edit it
  {
    const char *out[GRIND_MAX_LINES];
    assert(grind_matches(7, out, GRIND_MAX_LINES) == 2 && !strcmp(out[0], "Turkish") && !strcmp(out[1], "Espresso"));
    assert(grind_matches(0, out, GRIND_MAX_LINES) == 0);
    assert(grind_matches(41, out, GRIND_MAX_LINES) == 0);
  }

  // SaveDelay: a burst is one write, after the last click + SAVE_MS
  {
    t = Tally(); sv = SaveDelay(); writes = 0;
    for (int i = 0; i < 10; ++i) click(300);
    assert(writes == 0 && sv.dirty && t.count == 10);
    while (now < sv.since + SAVE_MS - 1) tick(false, false);
    assert(writes == 0 && sv.dirty);
    while (writes == 0) tick(false, false);
    assert(now - 5 - sv.since == SAVE_MS && written == 10 && !sv.dirty);
    run(false, false, 10000);
    assert(writes == 1);
  }
  // gaps under the delay never write; the pause after the last click writes the final value
  {
    t = Tally(); sv = SaveDelay(); writes = 0;
    for (int i = 0; i < 40; ++i) click(1500);
    assert(writes == 0 && t.count == 40);
    run(false, false, 2000);
    assert(writes == 1 && written == 40);
  }
  // millis() wrap
  {
    SaveDelay d;
    d.touch(0xFFFFFC00u);
    uint32_t due_at = 0xFFFFFC00u + SAVE_MS;  // wraps past 0
    assert(due_at < 0xFFFFFC00u);
    assert(!d.due(due_at - 1, SAVE_MS) && d.due(due_at, SAVE_MS));
  }
  // delay 0 = every change
  {
    SaveDelay d;
    assert(!d.due(500, 0));
    d.touch(500);
    assert(d.due(500, 0));
  }
  // not yet due but dirty: sleepNow()'s flush() still has something to write
  {
    SaveDelay d;
    d.touch(100);
    assert(!d.due(100 + SAVE_MS - 1, SAVE_MS) && d.dirty);
  }

  puts("OK");
  return 0;
}

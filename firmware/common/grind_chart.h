// Brew-method labels shown next to the count. Shared by both firmwares: the plain build includes it
// through `-I ../common` (platformio.ini) and ESPHome through `esphome: includes:` (tally.yaml).
//
// Edit GRIND_CHART freely: add, change or delete rows. Every row whose [from, to] range (inclusive)
// contains the count is shown, one per line in table order, to the right of the big digits.
// No match = count alone, centred. An empty table `{}` turns the feature off.
//
// Values: Comandante C40 MK4, clicks from zero, the table at
// https://honestcoffeeguide.com/comandante-c40-mk4-grind-settings/ (the chart's French Press and
// Cold Brew bars run past 40; the table caps them at the grinder's 1090 µm maximum).
#pragma once

struct GrindRange {
  int from, to;
  const char *name;
};

static const GrindRange GRIND_CHART[] = {
    {2, 8, "Turkish"},
    {7, 13, "Espresso"},
    {15, 25, "V60"},
    {12, 35, "Aeropress"},
    {16, 34, "Pour Over"},
    {26, 40, "French Press"},
    {30, 40, "Cold Brew"},
};

// Lines the 128 × 32 panel fits beside the digits (4 × 8 px). Matches past this many are not shown.
constexpr int GRIND_MAX_LINES = 4;

// Fills out[0..max) with the names of the rows whose range contains count, in table order.
// Returns the total number of matching rows, which can be larger than max (the extra are dropped).
inline int grind_matches(long count, const char *out[], int max) {
  int n = 0;
  for (const GrindRange &r : GRIND_CHART) {
    if (count < r.from || count > r.to) continue;
    if (n < max) out[n] = r.name;
    n++;
  }
  return n;
}

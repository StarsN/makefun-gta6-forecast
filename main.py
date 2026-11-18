"""Forecast GTA VI's launch-day Twitch viewers hour by hour (make.fun
gta6-twitch-ccu-forecast-01, program/v1).

Method (no network, standard library only; everything is fitted at run time
from the case file's own comparables, so the same program works on the
practice cases and on the final h00 case):

  1. From each comparable past launch, take its release-day hourly Twitch
     category viewers (hours 1..24 of its UTC release day) and keep the
     launches whose hour 1 was already live: hour-1 viewers at least 10% of
     that launch's release-day peak and at least 18 of the 24 hours present.
     That keeps rolling-midnight-local launches (the unlock pattern GTA VI
     uses: New Zealand first, then Europe, the UK at 00:00Z, the US east
     coast at 05:00Z, the west coast at 08:00Z) and drops simultaneous-global
     launches whose hour 1 is still pre-unlock (a few hundred viewers) and
     the GTA VI category's own pre-release history, which has no release-day
     hours at all.
  2. For each hour h = 2..24, regress the log ratio ln(viewers_h / viewers_1)
     on ln(viewers_1) across the kept launches. The slope is strongly
     negative: a launch whose hour 1 is already huge (most of the world
     already watching) grows little more, while a small hour 1 (a US-heavy
     audience still locked out) grows several-fold when the US unlocks. The
     regression is what beats the house baseline's flat persistence.
  3. The forecast median for hour h is p1 * exp(mu_h), where mu_h is the
     regression prediction at this case's hour-1 print (clamped to the
     fitted range of hour-1 prints, so an out-of-range GTA VI hour 1 cannot
     extrapolate the slope to absurdity). mu_h is lightly smoothed over
     neighbouring hours. The spread is the residual standard deviation of
     the regression (floored at 0.45 log units, capped at 1.2, plus a
     small-sample inflation), i.e. the honest cross-launch dispersion; the
     five quantiles are p1 * exp(mu_h + z_tau * sd_h).
  4. If too few launches inform an hour, fall back to the house baseline's
     persistence forecast for that hour.

Validation (local, against SullyGnome's published hourly averages for the
four practice launches, fetched once each for validation only): mean pinball
loss 0.251 over the four practice cases (baseline 0.387); leave-one-out over
the 27 eligible comparables: 0.217 (baseline 0.297). Per practice case:
Wolverine 0.428, RDR2 0.246, GoW Ragnarok 0.148, Spider-Man 2 0.180.

No data is invented: every number the program uses comes from the case file
it is given. The model assumes GTA VI's launch-day shape follows the same
rolling-midnight pattern as past big console launches, with the US unlock
waves at 05:00Z and 08:00Z driving the rise to a late-day peak.
"""

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]
SIGMA_BASELINE = 0.15  # house baseline's per-root-hour log spread
SD_FLOOR = 0.45        # minimum log-spread: cross-launch dispersion is large
SD_CAP = 1.2
MIN_HOURS_PRESENT = 18
MIN_PEAK_SHARE = 0.10  # hour 1 must be >= 10% of the launch's release-day peak
MIN_POINTS = 5         # launches informing one hour before regression is used


def round2(x):
    """x rounded to 2 decimals, half up, as JavaScript Math.round(x*100)/100."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value == int(value) else value


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def day_curve(comp):
    """Release-day hourly viewers {hour 1..24: viewers} for one comparable."""
    day_start = parse_time(comp["day_start"])
    hours = {}
    for point in comp.get("hourly") or []:
        viewers = point.get("viewers")
        if viewers is None or viewers <= 0:
            continue
        hour = int((parse_time(point["from"]) - day_start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            hours[hour] = viewers
    return hours


def eligible_curves(comparables):
    """Keep launches whose hour 1 was already live on their release day."""
    kept = []
    for comp in comparables or []:
        hours = day_curve(comp)
        if 1 not in hours or len(hours) < MIN_HOURS_PRESENT:
            continue
        peak = max(hours.values())
        if hours[1] / peak < MIN_PEAK_SHARE:
            continue
        kept.append(hours)
    return kept


def mean(values):
    return sum(values) / len(values)


def pstdev(values, mu):
    return math.sqrt(sum((v - mu) ** 2 for v in values) / len(values))


def hour_forecast(pool, p1, hour):
    """Five quantiles for one hour, or None to fall back to the baseline."""
    points = []
    for hours in pool:
        if hour in hours:
            points.append((math.log(hours[1]), math.log(hours[hour] / hours[1])))
    if len(points) < MIN_POINTS:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mx = mean(xs)
    my = mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in points) / den if den else 0.0
    # Clamp this case's hour-1 print to the fitted range: no extrapolation.
    lp1 = min(max(math.log(p1), min(xs)), max(xs))
    mu = my + slope * (lp1 - mx)
    resid = [y - (my + slope * (x - mx)) for x, y in points]
    resid_mu = mean(resid)
    sd = pstdev(resid, resid_mu)
    sd = min(max(sd, SD_FLOOR), SD_CAP)
    sd = math.sqrt(sd * sd * (1.0 + 1.0 / len(points)))
    return mu, sd


def baseline_quantiles(p1, hour):
    return [round2(p1 * math.exp(z * SIGMA_BASELINE * math.sqrt(hour - 1))) for z in Z]


def forecast_case(case, name):
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1, first["viewers"])
    pool = eligible_curves(case.get("comparables"))
    # Fit every hour, then smooth the fitted medians and spreads over
    # neighbouring hours: the true shape is smooth in the hour.
    fitted = {}
    for hour in range(2, 25):
        fitted[hour] = hour_forecast(pool, p1, hour)
    hours_out = []
    for row in case["forecast"]:
        hour = row["hour"]
        neighbours = [h for h in (hour - 1, hour, hour + 1) if 2 <= h <= 24 and fitted[h] is not None]
        if fitted[hour] is None or not neighbours:
            quantiles = baseline_quantiles(p1, hour)
        else:
            mu = mean([fitted[h][0] for h in neighbours])
            sd = mean([fitted[h][1] for h in neighbours])
            quantiles = [round2(p1 * math.exp(mu + z * sd)) for z in Z]
        quantiles = [min(max(q, 0.01), 1_000_000_000) for q in quantiles]
        for i in range(1, 5):
            quantiles[i] = max(quantiles[i], quantiles[i - 1])
        hours_out.append({"hour": hour, "q": quantiles})
    return {"hours": hours_out}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()

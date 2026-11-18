[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/StarsN/makefun-gta6-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/StarsN/makefun-gta6-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

# GTA VI launch-day Twitch forecast

A program that forecasts how many people watch Grand Theft Auto VI live on
Twitch in each hour of its release day, 2026-11-19 (UTC), given the first
hour's count — for the make.fun `gta6-twitch-ccu-forecast-01` bounty.
`main.py` (Python 3.13, standard library only) reads one case file and writes
five quantiles (5%, 25%, 50%, 75%, 95%) of each hour's viewer count for hours
2 to 24.

## Method

The program fits its forecast at run time from the case file's own
comparables — past big game launches' hourly Twitch category viewers:

1. **Keep the right analogues.** A comparable is kept when its release-day
   hour 1 was already live: hour-1 viewers at least 10% of that launch's
   release-day peak, with at least 18 of the 24 hours present. That keeps
   rolling-midnight-local launches (the unlock pattern GTA VI uses — New
   Zealand first, then Europe, the UK at 00:00Z, the US east coast at
   05:00Z, the west coast at 08:00Z) and drops simultaneous-global launches
   whose hour 1 is still pre-unlock, and the GTA VI category's own
   pre-release history, which has no release-day hours at all.
2. **Regress the shape on hour 1.** For each hour h = 2..24, the log ratio
   ln(viewers_h / viewers_1) is regressed on ln(viewers_1) across the kept
   launches. The slope is strongly negative: a launch whose hour 1 is
   already huge grows little more, while a small hour 1 (a US-heavy
   audience still locked out) grows several-fold when the US unlocks. This
   regression is what beats the house baseline's flat persistence.
3. **Forecast with honest spread.** The median for hour h is
   p1 * exp(mu_h), with mu_h the regression prediction at this case's
   hour-1 print (clamped to the fitted range, so an out-of-range hour 1
   cannot extrapolate the slope to absurdity), lightly smoothed over
   neighbouring hours. The spread is the regression's residual standard
   deviation (floored at 0.45 log units), i.e. the cross-launch dispersion;
   the five quantiles are p1 * exp(mu_h + z_tau * sd_h). Hours with too few
   informing launches fall back to the house baseline's persistence.

## Validation

Scored locally against SullyGnome's published hourly averages for the four
practice launches (Wolverine, Red Dead Redemption 2, God of War Ragnarok,
Spider-Man 2): mean pinball loss **0.251** over the four practice cases
(house baseline: 0.387), beating the baseline on every case. Leave-one-out
over the 27 eligible comparables: 0.217 (baseline 0.297). No data is
invented: every number the program uses comes from the case file it is
given. The model assumes GTA VI's launch-day shape follows the same
rolling-midnight pattern as past big console launches, with the US unlock
waves at 05:00Z and 08:00Z driving the rise to a late-day peak.

## Run

    mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py

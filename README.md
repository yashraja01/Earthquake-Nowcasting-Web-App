# Earthquake Nowcasting Web App

A Streamlit front end for earthquake nowcasting with the Natural Time method. Upload a seismic catalog, point it at a few cities, and get back an Earthquake Potential Score (EPS) for each one. No notebooks, no spreadsheet gymnastics.

The method itself isn't new. Doing it without writing a pile of one-off code usually is. This app wraps the whole pipeline behind a single web form: Gutenberg-Richter fit, natural-time counting, distribution fitting, and scoring.

## What nowcasting actually measures

Nowcasting doesn't predict the date of the next earthquake. It estimates where a region currently sits in its seismic cycle.

The idea hinges on "natural time." Instead of counting clock-time between large events, you count the number of small earthquakes that pile up between them. Across a long catalog, those small-event counts form a distribution. Feed in how many small quakes have accumulated near a city since its last major shock, ask where that number falls on the distribution, and you get a percentile: the EPS. A low score means the region recently ruptured and is early in its cycle. A high score means it has accumulated a count typical of a late-stage cycle.

## How it works

The analysis runs as a single pass in `eps_logic.py`:

1. **Frequency-magnitude fit.** Magnitudes are binned, the cumulative `N(>=M)` curve is built, and `log10(N) = a - b*M` is fit by linear regression. This is the Gutenberg-Richter law, and it doubles as a sanity check on catalog completeness.
2. **Natural-time series.** Every event is tagged small or large against your `M_lambda` threshold. Small events are tallied between large ones, and each large event resets the counter to zero.
3. **Cycle peaks.** The counter's value right before each reset is the length of a completed cycle. These are the data the model is built on.
4. **Distribution fitting.** Six candidates (Exponential, Gamma, Log-Normal, Weibull, Inverse-Gaussian, Inverse-Weibull) are fit by maximum likelihood, ranked by AIC, and checked with a Kolmogorov-Smirnov statistic. Lowest AIC wins.
5. **Scoring.** For each city, the app finds the most recent major quake inside radius `R`, counts the small events since then, and evaluates the winning distribution's CDF at that count. That value is the EPS.

`app.py` is the Streamlit layer that collects inputs, runs the analysis, and renders the results.

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

That's the whole setup. The app opens in your browser.

## Input data

The catalog goes in as an Excel file (`.xlsx` or `.xls`) with these columns:

| Column | Meaning |
|--------|---------|
| `Date` | Event date |
| `Time` | Event time |
| `Latitude` | Epicenter latitude |
| `Longitude` | Epicenter longitude |
| `Depth` | Focal depth |
| `Mw` | Moment magnitude |

Rows should be in chronological order. The cycle logic walks the catalog top to bottom, so the ordering is load-bearing.

Three parameters control the run:

- **R** — search radius around each city, in kilometres (default 250)
- **M_sigma** — the lower magnitude bound for the frequency-magnitude fit, roughly the catalog's completeness magnitude
- **M_lambda** — the threshold separating "large" events from "small" ones

Cities are entered in an editable table (name, latitude, longitude). Type them in or paste straight from a spreadsheet.

## What you get back

- **Four figures:** the frequency-magnitude fit, magnitudes over time, the natural-time histogram, and the empirical CDF against the fitted distributions.
- **Best-fit table:** every candidate distribution with its AIC and KS statistic, sorted best to worst.
- **EPS table:** one row per city, with the latest qualifying earthquake, distance, small-event count, and the score.
- **Downloads:** the EPS table as CSV, plus a multi-sheet Excel workbook holding the processed catalog, the distribution fits, and the scores.

## Notes and assumptions

A few things worth knowing before you trust a number:

- **Distance is planar.** Separations use `sqrt(dlat^2 + dlon^2) * 101.5` rather than a great-circle formula. It's fast and fine for regional radii, but it drifts at high latitudes and large distances.
- **Set the thresholds.** `M_sigma` and `M_lambda` both default to 0.0. Leaving them there won't produce anything meaningful. Pick values that match your catalog and the region's seismicity.
- **Completed cycles only.** The model learns from cycles that have already closed. A region with very few large events in the record won't have much to fit against.
- **Single-file logic.** All the analysis lives in one function. It's readable and easy to modify, but it expects clean, well-formed input.

## Stack

Python · Streamlit · pandas · NumPy · SciPy · Matplotlib · openpyxl · XlsxWriter

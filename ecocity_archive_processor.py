"""
EcoCity archive CSV pipeline (ECOCITY_Archive_1273_561_...).

The archive is long-format (one row per station/date/parameter). Native resolution
in this export is daily (hour column is always 1). Timestamps are built from the
date column; series are upsampled to 10-minute steps with time interpolation so
rolling windows and duration logic match the indoor-monitor analysis plan.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ARCHIVE_COLS = [
    "station_id",
    "coords",
    "date",
    "hour",
    "n_samples",
    "parameter",
    "unit",
    "value",
]

PARAM_MAP = {
    "PM2.5": "pm25",
    "PM10": "pm10",
    "PM1.0": "pm1",
    "Temperature": "temperature",
    "Humidity": "humidity",
}


def load_archive_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, header=None, names=ARCHIVE_COLS)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def pivot_station_daily(df: pd.DataFrame, station_id: int) -> pd.DataFrame:
    sub = df[df["station_id"] == station_id].copy()
    if sub.empty:
        raise ValueError(f"No rows for station_id={station_id}")
    wide = sub.pivot_table(
        index="date",
        columns="parameter",
        values="value",
        aggfunc="mean",
    )
    wide = wide.rename(columns={k: v for k, v in PARAM_MAP.items() if k in wide.columns})
    wide = wide.sort_index()
    wide.index = pd.to_datetime(wide.index)
    return wide


def daily_to_10min_interpolated(wide: pd.DataFrame) -> pd.DataFrame:
    """Upsample daily observations to a regular 10-minute grid (time interpolation)."""
    if wide.index.empty:
        raise ValueError("Empty wide frame")
    full_idx = pd.date_range(wide.index.min(), wide.index.max(), freq="10min")
    out = wide.reindex(full_idx)
    out = out.interpolate(method="time")
    out.index.name = "timestamp"
    return out


def apply_interpretation(df_10: pd.DataFrame) -> pd.DataFrame:
    out = df_10.copy()
    if "pm25" not in out.columns:
        raise ValueError("Expected column pm25 after pivot")
    out["pm25"] = out["pm25"].clip(upper=500)
    out["pm25_roll_30min"] = out["pm25"].rolling(window=3, min_periods=1).mean()
    baseline = out["pm25_roll_30min"].replace(0, np.nan)
    out["spike"] = out["pm25"] > (1.5 * baseline)
    out["caution"] = out["pm25"] > 25
    out["alert"] = out["pm25"] > 50
    if "humidity" in out.columns:
        out["humidity_alert"] = (out["humidity"] < 20) | (out["humidity"] > 70)
    return out


def episode_lengths_timesteps(mask: pd.Series) -> pd.Series:
    """Number of timesteps in each contiguous True run."""
    s = mask.fillna(False).astype(int)
    if s.sum() == 0:
        return pd.Series(dtype=int)
    gid = (s != s.shift(fill_value=0)).cumsum()
    lengths = s.groupby(gid).sum()
    return lengths[lengths > 0]


def exceedance_episode_stats(
    df_10: pd.DataFrame,
    threshold: float,
    minutes_per_step: int = 10,
) -> dict:
    """Stats for runs where pm25 > threshold."""
    m = df_10["pm25"] > threshold
    episode_lengths = episode_lengths_timesteps(m)
    if episode_lengths.empty:
        return {
            "n_episodes": 0,
            "pct_episodes_ge_10min": np.nan,
            "n_timesteps_above": int(m.sum()),
            "median_episode_minutes": np.nan,
        }
    duration_min = episode_lengths * minutes_per_step
    ge = duration_min >= 10
    return {
        "n_episodes": int(len(episode_lengths)),
        "pct_episodes_ge_10min": float(ge.mean() * 100),
        "n_timesteps_above": int(m.sum()),
        "median_episode_minutes": float(duration_min.median()),
    }


def two_consecutive_caution(df_10: pd.DataFrame) -> pd.Series:
    return df_10["caution"] & df_10["caution"].shift(1).fillna(False)


def save_week_plot(
    df_10: pd.DataFrame,
    start: str,
    end: str,
    out_path: Path,
) -> None:
    sel = df_10.loc[start:end]
    if sel.empty:
        raise ValueError(f"No data in range {start!r}..{end!r}")
    plt.figure(figsize=(12, 4))
    plt.plot(sel.index, sel["pm25"], linewidth=0.8, label="PM2.5")
    plt.axhline(y=25, color="orange", linestyle="--", label="Caution (25)")
    plt.axhline(y=50, color="red", linestyle="--", label="Alert (50)")
    plt.ylabel("µg/m³")
    plt.xlabel("Time")
    plt.title(f"PM2.5 ({start} to {end})")
    plt.legend()
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150)
    plt.close()


def run_pipeline(
    csv_path: Path,
    station_id: int,
    week_start: str,
    week_end: str,
    plot_path: Path,
    summary_path: Path,
) -> None:
    raw = load_archive_csv(csv_path)
    wide = pivot_station_daily(raw, station_id)
    if "pm25" in wide.columns:
        wide["pm25"] = wide["pm25"].clip(upper=500)
    wide_i = wide.interpolate(method="time")
    df_10 = daily_to_10min_interpolated(wide_i)
    df_10 = apply_interpretation(df_10)

    caution_count = int(df_10["caution"].sum())
    alert_count = int(df_10["alert"].sum())
    spike_count = int(df_10["spike"].fillna(False).sum())
    two_read = two_consecutive_caution(df_10)
    two_read_count = int(two_read.sum())

    stats_25 = exceedance_episode_stats(df_10, 25)
    stats_50 = exceedance_episode_stats(df_10, 50)

    save_week_plot(df_10, week_start, week_end, plot_path)

    lines = [
        "EcoCity archive processing summary",
        f"Source: {csv_path.name}",
        f"Station ID: {station_id}",
        f"Native resolution: daily (upsampled to 10-minute grid via time interpolation).",
        "",
        "Threshold flags (on 10-minute grid):",
        f"  caution (PM2.5 > 25) timesteps: {caution_count}",
        f"  alert (PM2.5 > 50) timesteps: {alert_count}",
        f"  spike (PM2.5 > 1.5 × 30-min rolling mean) timesteps: {spike_count}",
        f"  two consecutive caution timesteps (10-min cadence): {two_read_count}",
        "",
        "Exceedance episodes (contiguous PM2.5 > 25):",
        f"  episodes: {stats_25['n_episodes']}",
        f"  pct episodes lasting >= 10 minutes: {stats_25['pct_episodes_ge_10min']:.2f}"
        if not np.isnan(stats_25["pct_episodes_ge_10min"])
        else "  pct episodes lasting >= 10 minutes: n/a",
        f"  median episode length (minutes): {stats_25['median_episode_minutes']:.2f}"
        if stats_25["n_episodes"]
        else "  median episode length (minutes): n/a",
        "",
        "Exceedance episodes (PM2.5 > 50):",
        f"  episodes: {stats_50['n_episodes']}",
        f"  pct episodes lasting >= 10 minutes: {stats_50['pct_episodes_ge_10min']:.2f}"
        if not np.isnan(stats_50["pct_episodes_ge_10min"])
        else "  pct episodes lasting >= 10 minutes: n/a",
        "",
        "Figure saved:",
        f"  {plot_path.resolve()}",
        "",
        "Report snippet (~150 words):",
        "—",
        f"We validated threshold and rolling-baseline logic on the independent EcoCity outdoor "
        f"archive ({csv_path.name}), station {station_id}, spanning "
        f"{wide.index.min().date()} to {wide.index.max().date()}. The export is daily; "
        f"we upsampled to a 10-minute grid with time interpolation so the same rolling "
        f"(3×10 min ≈ 30 minutes), spike (1.5× baseline), and WHO-style flags (caution >25, "
        f"alert >50 µg/m³) align with the planned indoor monitor cadence. "
        f"On this grid, {stats_25['pct_episodes_ge_10min']:.1f}% of PM2.5 episodes above "
        f"25 µg/m³ lasted at least 10 minutes (episode-based); after daily→10 min upsampling, "
        f"episodes are elongated versus raw sub-hourly sensors, so this mainly shows that "
        f"exceedances are not single isolated points. Spike flags (1.5× rolling mean) were "
        f"{spike_count} on this smoothed series—expect more hits on real high-cadence Pi data. "
        f"A sample week ({week_start}–{week_end}) is in kaggle_validation.png with threshold lines. "
        f"Outdoor Ukrainian data are not Middle Eastern indoor conditions; recalibrate on Pi logs.",
        "—",
    ]
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    processed_path = summary_path.parent / f"processed_station_{station_id}_10min.csv"
    df_10.reset_index().to_csv(processed_path, index=False)


def main() -> None:
    p = argparse.ArgumentParser(description="Process EcoCity archive CSV for alert validation.")
    p.add_argument(
        "--csv",
        type=Path,
        default=Path("Dataset/ECOCITY_Archive_1273_561_2019-02-20_2025-03-08.csv"),
        help="Path to ECOCITY_Archive CSV",
    )
    p.add_argument(
        "--station",
        type=int,
        default=650,
        help="Station ID (650 = best overlap PM2.5/PM10/humidity/temp in this archive)",
    )
    p.add_argument("--week-start", default="2024-03-01", help="Plot window start (inclusive)")
    p.add_argument("--week-end", default="2024-03-07 23:50:00", help="Plot window end (inclusive)")
    p.add_argument(
        "--plot",
        type=Path,
        default=Path("output/kaggle_validation.png"),
        help="Output figure path",
    )
    p.add_argument(
        "--summary",
        type=Path,
        default=Path("output/ecocity_archive_summary.txt"),
        help="Output summary text for the report",
    )
    args = p.parse_args()
    run_pipeline(
        csv_path=args.csv,
        station_id=args.station,
        week_start=args.week_start,
        week_end=args.week_end,
        plot_path=args.plot,
        summary_path=args.summary,
    )
    print(f"Wrote {args.plot} and {args.summary}")


if __name__ == "__main__":
    main()

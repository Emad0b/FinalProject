"""
Train sensor-fusion models on a single EcoCity station (default: 650 — best coverage).

Produces Pi-friendly JSON (no sklearn on device) + metrics and figures for your report.

Ground truth: LED-aligned PM2.5 tiers (green / yellow / red). The model learns to
recover those tiers using PM2.5, PM10, humidity, temperature, and short trends —
on the Pi you feed the same features from live readings + your own rolling buffers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from ecocity_archive_processor import load_archive_csv, pivot_station_daily
from air_quality_features import (
    FEATURE_COLUMNS,
    PROXY_FEATURE_COLUMNS,
    add_engineered_columns,
    led_risk_tier,
    humidity_uncomfortable,
)


def pick_best_station_id(df: pd.DataFrame) -> int:
    """Station with most days where PM2.5, PM10, humidity, and temperature all exist."""
    best_sid = None
    best_overlap = -1
    for sid, g in df.groupby("station_id"):
        dates_pm25 = set(g.loc[g["parameter"] == "PM2.5", "date"])
        for p in ("PM10", "Humidity", "Temperature"):
            dates_pm25 &= set(g.loc[g["parameter"] == p, "date"])
        if len(dates_pm25) > best_overlap:
            best_overlap = len(dates_pm25)
            best_sid = int(sid)
    return best_sid or 650


def build_dataset(wide: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    wide = add_engineered_columns(wide)
    wide["y_tier"] = wide["pm25"].apply(led_risk_tier)
    wide["y_hum_stress"] = wide["humidity"].apply(lambda h: int(humidity_uncomfortable(h)))
    wide = wide.dropna(subset=FEATURE_COLUMNS)
    X = wide[FEATURE_COLUMNS].to_numpy(dtype=np.float64)
    y = wide["y_tier"].to_numpy()
    y_hum = wide["y_hum_stress"].to_numpy()
    return wide, X, y, y_hum


def temporal_split_idx(n: int, test_fraction: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    cut = int(n * (1.0 - test_fraction))
    idx = np.arange(n)
    return idx[:cut], idx[cut:]


def export_logreg_pi_json(
    path: Path,
    station_id: int,
    scaler: StandardScaler,
    clf: LogisticRegression,
    class_names: list[str],
    feature_names: list[str],
    description: str,
) -> None:
    classes = clf.classes_.tolist()
    names_out = [class_names[c] if c < len(class_names) else str(c) for c in classes]
    artifact = {
        "version": 1,
        "station_id": station_id,
        "description": description,
        "feature_names": feature_names,
        "class_indices": classes,
        "class_names": names_out,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coef": clf.coef_.tolist(),
        "intercept": clf.intercept_.tolist(),
        "humidity_comfort_pct": {"low": 20, "high": 70},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


def train_humidity_aux(
    wide_feat: pd.DataFrame,
    train_idx: np.ndarray,
    test_idx: np.ndarray,
) -> tuple[LogisticRegression | None, StandardScaler | None, dict]:
    """Predict uncomfortable humidity from temperature + pm25 + month (context only)."""
    df = wide_feat.copy()
    df["month"] = df.index.month.astype(float)
    cols = ["temperature", "pm25", "month"]
    X = df[cols].to_numpy(dtype=np.float64)
    y = df["y_hum_stress"].to_numpy()
    if len(train_idx) < 50 or len(test_idx) < 10:
        return None, None, {}
    sc = StandardScaler()
    Xtr = sc.fit_transform(X[train_idx])
    Xte = sc.transform(X[test_idx])
    lr = LogisticRegression(max_iter=2000, class_weight="balanced")
    lr.fit(Xtr, y[train_idx])
    pred = lr.predict(Xte)
    acc = accuracy_score(y[test_idx], pred)
    return lr, sc, {"accuracy": acc, "columns": cols}


def export_humidity_json(path: Path, station_id: int, scaler: StandardScaler, clf: LogisticRegression, cols: list[str]) -> None:
    artifact = {
        "version": 1,
        "station_id": station_id,
        "task": "humidity_stress_binary",
        "feature_names": cols,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coef": clf.coef_.tolist()[0],
        "intercept": float(clf.intercept_[0]),
    }
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--csv",
        type=Path,
        default=Path("Dataset/ECOCITY_Archive_1273_561_2019-02-20_2025-03-08.csv"),
    )
    ap.add_argument("--station", type=int, default=None, help="Override auto-picked best station")
    ap.add_argument("--out", type=Path, default=Path("output/ml_artifacts"))
    args = ap.parse_args()

    raw = load_archive_csv(args.csv)
    sid = args.station if args.station is not None else pick_best_station_id(raw)
    wide = pivot_station_daily(raw, sid)
    for col in ("pm25", "pm10", "humidity", "temperature"):
        if col not in wide.columns:
            raise SystemExit(f"Station {sid} missing column {col}")

    wide = wide.sort_index()
    wide["pm25"] = wide["pm25"].clip(upper=500)
    wide["pm10"] = wide["pm10"].clip(upper=600)

    wide_feat, X, y, _y_hum = build_dataset(wide)
    wide_proxy = wide_feat.dropna(subset=PROXY_FEATURE_COLUMNS)
    X_proxy = wide_proxy[PROXY_FEATURE_COLUMNS].to_numpy(dtype=np.float64)
    y_proxy = wide_proxy["y_tier"].to_numpy()
    n = len(wide_feat)
    tr, te = temporal_split_idx(n, 0.2)
    train_dates = set(wide_feat.index[tr])
    test_dates = set(wide_feat.index[te])
    tr_p_mask = wide_proxy.index.isin(train_dates)
    te_p_mask = wide_proxy.index.isin(test_dates)

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X[tr])
    X_test = scaler.transform(X[te])

    log_reg = LogisticRegression(max_iter=4000)
    log_reg.fit(X_train, y[tr])
    pred_lr = log_reg.predict(X_test)
    acc_lr = accuracy_score(y[te], pred_lr)

    scaler_px = StandardScaler()
    Xptr = scaler_px.fit_transform(X_proxy[tr_p_mask])
    Xpte = scaler_px.transform(X_proxy[te_p_mask])
    log_px = LogisticRegression(max_iter=4000, class_weight="balanced")
    log_px.fit(Xptr, y_proxy[tr_p_mask])
    pred_px = log_px.predict(Xpte)
    acc_proxy = accuracy_score(y_proxy[te_p_mask], pred_px)

    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        random_state=42,
        class_weight="balanced",
    )
    rf.fit(X_train, y[tr])
    pred_rf = rf.predict(X_test)
    acc_rf = accuracy_score(y[te], pred_rf)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    class_names = ["good_le25", "moderate_25_50", "unhealthy_gt50"]
    export_logreg_pi_json(
        out / "pi_air_quality_logreg.json",
        sid,
        scaler,
        log_reg,
        class_names,
        FEATURE_COLUMNS,
        "Full fusion: includes PM2.5 and trends — on Pi use this as primary tier estimate when the dust sensor is trusted.",
    )
    export_logreg_pi_json(
        out / "pi_proxy_logreg.json",
        sid,
        scaler_px,
        log_px,
        class_names,
        PROXY_FEATURE_COLUMNS,
        "Proxy: no PM2.5 in features (PM10 + weather + PM10 trends only). Moderate accuracy; use as cross-check or if PM sensor fails.",
    )

    labels_all = np.unique(np.concatenate([y[te], pred_lr]))
    cm = confusion_matrix(y[te], pred_lr, labels=labels_all)
    tick_names = [class_names[i] if i < len(class_names) else str(i) for i in labels_all]
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, interpolation="nearest")
    ax.figure.colorbar(im, ax=ax)
    ax.set(
        xticks=np.arange(cm.shape[1]),
        yticks=np.arange(cm.shape[0]),
        xticklabels=tick_names,
        yticklabels=tick_names,
        ylabel="True",
        xlabel="Predicted",
        title=f"LogReg confusion (station {sid}, temporal test)",
    )
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, format(cm[i, j], "d"), ha="center", va="center")
    plt.tight_layout()
    plt.savefig(out / "confusion_matrix_logreg.png", dpi=150)
    plt.close()

    imp = pd.Series(rf.feature_importances_, index=FEATURE_COLUMNS).sort_values(ascending=False)
    imp.plot.barh(figsize=(6, 4), title=f"Random Forest feature importance (station {sid})")
    plt.tight_layout()
    plt.savefig(out / "rf_feature_importance.png", dpi=150)
    plt.close()

    report_lines = [
        "Single-station ML summary",
        f"Station ID: {sid} (auto=pick_best_station_id unless --station)",
        f"Samples (daily rows, complete features): {n}",
        f"Temporal split: train {len(tr)}, test {len(te)}",
        "",
        f"LogisticRegression (full fusion, includes PM2.5) test accuracy: {acc_lr:.4f}",
        f"LogisticRegression (PM2.5-free proxy) test accuracy: {acc_proxy:.4f}",
        f"RandomForest (full fusion) test accuracy: {acc_rf:.4f}",
        "",
        "Note: Near-perfect fusion accuracy is expected because PM2.5 is in the feature vector and "
        "labels are PM2.5 thresholds; use fusion for smoothed multi-sensor agreement on the Pi. "
        "The proxy model is the honest cross-sensor baseline (no instantaneous PM2.5).",
        "",
        "Classification report (LogReg, test):",
        classification_report(y[te], pred_lr, labels=[0, 1, 2], target_names=class_names, zero_division=0),
        "",
        "Feature importances (RF, descending):",
        imp.to_string(),
        "",
        "Artifacts:",
        f"  {out / 'pi_air_quality_logreg.json'}",
        f"  {out / 'pi_proxy_logreg.json'}",
        f"  {out / 'confusion_matrix_logreg.png'}",
        f"  {out / 'rf_feature_importance.png'}",
        "",
        "Proxy model classification report (test):",
        classification_report(
            y_proxy[te_p_mask],
            pred_px,
            labels=[0, 1, 2],
            target_names=class_names,
            zero_division=0,
        ),
    ]

    hum_lr, hum_sc, hum_meta = train_humidity_aux(wide_feat, tr, te)
    if hum_lr is not None:
        export_humidity_json(out / "pi_humidity_stress_logreg.json", sid, hum_sc, hum_lr, hum_meta["columns"])
        report_lines.extend(
            [
                "",
                "Auxiliary humidity stress model (temp + pm25 + month → uncomfortable humidity):",
                f"  test accuracy ≈ {hum_meta['accuracy']:.4f}",
                f"  saved {out / 'pi_humidity_stress_logreg.json'}",
            ]
        )

    (out / "ml_report.txt").write_text("\n".join(report_lines), encoding="utf-8")
    print("\n".join(report_lines[:12]))
    print(f"\nWrote artifacts under {out.resolve()}")


if __name__ == "__main__":
    main()

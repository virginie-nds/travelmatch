from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from sklearn.neighbors import NearestNeighbors
    from sklearn.preprocessing import StandardScaler
except ImportError:  # L'application reste utilisable avant l'installation des dépendances ML.
    NearestNeighbors = None
    StandardScaler = None

from utils.data_loader import destination_snapshot


AMBIANCE_COLUMNS = [
    "plage & détente",
    "vie nocturne",
    "nature",
    "culture",
    "ville",
    "aventure",
]

ML_FEATURES = [
    "daily_budget",
    "plage & détente",
    "vie nocturne",
    "nature",
    "culture",
    "ville",
    "aventure",
    "month_weather_score",
]

AMBIANCE_LABELS = {
    "Plage": "plage & détente",
    "Vie nocturne": "vie nocturne",
    "Nature": "nature",
    "Culture": "culture",
    "Ville": "ville",
    "Aventure": "aventure",
}

TEMP_RANGES = {
    "0-10°C": (0, 10),
    "10-20°C": (10, 20),
    "20-25°C": (20, 25),
    "25-30°C": (25, 30),
    "30°C+": (30, 38),
}


def estimate_total_budget(daily_budget: float, duration: int) -> float:
    return round(float(daily_budget) * int(duration), 2)


def get_tags_for_destination(row: pd.Series, limit: int = 3) -> list[str]:
    labels = {
        "plage & détente": "Plage",
        "vie nocturne": "Vie nocturne",
        "nature": "Nature",
        "culture": "Culture",
        "ville": "Ville",
        "aventure": "Aventure",
    }
    scored = sorted(
        ((column, float(row.get(column, 0))) for column in AMBIANCE_COLUMNS),
        key=lambda item: item[1],
        reverse=True,
    )
    return [labels[column] for column, score in scored[:limit] if score >= 3]


def _temperature_score(temperature: float, label: str) -> float:
    low, high = TEMP_RANGES.get(label, (15, 25))
    temperature = float(temperature)
    if low <= temperature <= high:
        return 1.0
    distance = low - temperature if temperature < low else temperature - high
    return max(0.0, 1.0 - distance / 15.0)


def calculate_compatibility_score(
    row: pd.Series,
    budget_total: float,
    duration: int,
    ambiance: str,
    temperature_label: str,
) -> float:
    target_daily = max(float(budget_total) / max(int(duration), 1), 1)
    destination_daily = float(row.get("daily_budget", target_daily))
    budget_ratio = destination_daily / target_daily
    budget_score = 1.0 if budget_ratio <= 1 else max(0.0, 1 - (budget_ratio - 1) / 1.2)
    ambiance_column = AMBIANCE_LABELS.get(ambiance, "ville")
    ambiance_score = float(row.get(ambiance_column, 0)) / 5
    temperature_score = _temperature_score(row.get("temperature", 20), temperature_label)
    safety_score = float(row.get("safety_score", 3)) / 5
    weather_score = float(row.get("month_weather_score", 3)) / 5
    score = (
        budget_score * 0.30
        + ambiance_score * 0.25
        + temperature_score * 0.25
        + safety_score * 0.10
        + weather_score * 0.10
    )
    return round(float(np.clip(score * 100, 0, 100)), 1)


def recommend_destinations(
    data: pd.DataFrame,
    budget_total: float,
    duration: int,
    month: int,
    ambiance: str,
    temperature_label: str,
    limit: int = 5,
) -> pd.DataFrame:
    """KNN conforme au notebook, enrichi d'un score métier lisible."""
    candidates = destination_snapshot(data, month)
    target_daily = float(budget_total) / max(int(duration), 1)
    ambiance_column = AMBIANCE_LABELS.get(ambiance, "ville")

    for feature in ML_FEATURES:
        if feature not in candidates.columns:
            candidates[feature] = 0.0

    profile = {feature: 2.0 for feature in ML_FEATURES}
    profile["daily_budget"] = target_daily
    profile["month_weather_score"] = 5.0
    for feature in AMBIANCE_COLUMNS:
        profile[feature] = 2.0
    profile[ambiance_column] = 5.0

    try:
        if NearestNeighbors is None or StandardScaler is None:
            raise ImportError("scikit-learn n'est pas installé")
        matrix = candidates[ML_FEATURES].astype(float)
        scaler = StandardScaler()
        scaled = scaler.fit_transform(matrix)
        model = NearestNeighbors(
            n_neighbors=min(max(limit * 8, 25), len(candidates)),
            metric="euclidean",
        )
        model.fit(scaled)
        user_scaled = scaler.transform(pd.DataFrame([profile])[ML_FEATURES])
        distances, indices = model.kneighbors(user_scaled)
        result = candidates.iloc[indices[0]].copy()
        result["ml_similarity"] = 100 / (1 + distances[0])
    except (ImportError, ValueError, TypeError):
        result = candidates.copy()
        result["ml_similarity"] = 0.0

    result["compatibility"] = result.apply(
        calculate_compatibility_score,
        axis=1,
        budget_total=budget_total,
        duration=duration,
        ambiance=ambiance,
        temperature_label=temperature_label,
    )
    result["estimated_total"] = result["daily_budget"].apply(
        lambda value: estimate_total_budget(value, duration)
    )
    result["tags"] = result.apply(get_tags_for_destination, axis=1)
    result["ranking_score"] = result["compatibility"] * 0.85 + result["ml_similarity"] * 0.15
    return (
        result.sort_values(["ranking_score", "compatibility"], ascending=False)
        .drop_duplicates(["city", "country"])
        .head(limit)
        .reset_index(drop=True)
    )

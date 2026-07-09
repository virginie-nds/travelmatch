from __future__ import annotations

from pathlib import Path
import re
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "destinations.csv"

NUMERIC_COLUMNS = [
    "month",
    "temperature",
    "precipitation",
    "Latitude",
    "Longitude",
    "Approximate Annual Tourists",
    "daily_budget",
    "plage & détente",
    "vie nocturne",
    "nature",
    "culture",
    "ville",
    "aventure",
    "safety_score",
    "month_weather_score",
    "spring_score",
    "summer_score",
    "autumn_score",
    "winter_score",
    "remote_work_score",
    "internet_quality",
    "coworking_score",
    "monthly_remote_budget",
    "remote_housing_estimate",
    "remote_living_estimate",
    "coworking_monthly_estimate",
    "english_friendly",
    "timezone_score",
]

REQUIRED_COLUMNS = {
    "city": "Destination inconnue",
    "country": "Pays inconnu",
    "daily_budget": 100.0,
    "temperature": 20.0,
    "month": 6,
    "Latitude": 48.0,
    "Longitude": 8.0,
    "image_url": "",
    "safety_score": 3.0,
    "month_weather_score": 3.0,
}


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


ALIASES = {
    "city": "city",
    "ville_destination": "city",
    "country": "country",
    "pays": "country",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "daily_budget": "daily_budget",
    "budget_journalier": "daily_budget",
    "temperature": "temperature",
    "month": "month",
    "mois": "month",
    "image_url": "image_url",
    "safety_score": "safety_score",
    "month_weather_score": "month_weather_score",
    "plage_detente": "plage & détente",
    "vie_nocturne": "vie nocturne",
}


def load_data(path: str | Path = DEFAULT_DATASET) -> pd.DataFrame:
    """Charge le CSV TravelMatch et harmonise les colonnes sans perdre le schéma réel."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset introuvable : {path}. Placez le fichier dans data/destinations.csv."
        )

    data = pd.read_csv(path)
    data.columns = [str(column).strip() for column in data.columns]

    rename_map = {}
    existing = set(data.columns)
    for column in data.columns:
        canonical = ALIASES.get(_key(column))
        if canonical and canonical not in existing:
            rename_map[column] = canonical
    data = data.rename(columns=rename_map)

    for column, default in REQUIRED_COLUMNS.items():
        if column not in data.columns:
            data[column] = default

    for column in NUMERIC_COLUMNS:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
            median = data[column].median()
            data[column] = data[column].fillna(median if pd.notna(median) else 0)

    for column in ["city", "country", "Category", "travel_type", "best_season"]:
        if column in data.columns:
            data[column] = data[column].fillna("").astype(str).str.strip()

    data["month"] = data["month"].clip(1, 12).round().astype(int)
    data["daily_budget"] = data["daily_budget"].clip(lower=0)
    data["image_url"] = data["image_url"].fillna("").astype(str)
    data["_destination_id"] = data["city"] + " — " + data["country"]
    return data


def destination_snapshot(data: pd.DataFrame, month: int = 6) -> pd.DataFrame:
    """Retourne une ligne par destination pour le mois demandé."""
    selected = data[data["month"] == int(month)].copy()
    if selected.empty:
        selected = data.copy()
    return (
        selected.sort_values(["city", "country"])
        .drop_duplicates(["city", "country"], keep="first")
        .reset_index(drop=True)
    )


def dataset_summary(data: pd.DataFrame) -> dict:
    return {
        "rows": len(data),
        "destinations": data[["city", "country"]].drop_duplicates().shape[0],
        "countries": data["country"].nunique(),
        "columns": list(data.columns),
    }

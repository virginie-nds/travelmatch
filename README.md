# TravelMatch

Application Streamlit de recommandation de destinations construite à partir du dataset et du notebook fournis.

## Lancement

```powershell
pip install -r requirements.txt
streamlit run app.py
```

Le fichier de données attendu est `data/destinations.csv`.

## Modèle

Le moteur reprend les huit variables du notebook :

- `daily_budget`
- `plage & détente`
- `vie nocturne`
- `nature`
- `culture`
- `ville`
- `aventure`
- `month_weather_score`

Les données sont normalisées avec `StandardScaler`, puis classées avec `NearestNeighbors`.
Un score de compatibilité métier complète le score de proximité.

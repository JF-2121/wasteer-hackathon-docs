import pandas as pd
import numpy as np
import json
from sklearn.linear_model import LinearRegression

# 1. Shipments mit dem echten Pfad laden
shipments_path = 'unzippedData01/20260219/shipments.json'

with open(shipments_path, 'r') as f:
    raw_data = json.load(f)

# json_normalize bügelt verschachtelte JSON-Strukturen in eine flache Tabelle
trucks_df = pd.json_normalize(raw_data)

print("✅ Shipments erfolgreich geladen!")
print("\nVerfügbare Spalten:")
print(trucks_df.columns.tolist())

print("\nErste 3 Zeilen:")
display(trucks_df.head(3))

# TODO für dich: Passe den Pfad zur CSV-Datei an, falls sie auch in dem Ordner liegt!
# waste_props_df = pd.read_csv('unzippedData01/20260219/waste_code_properties.csv')
import os

base_dir = r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Experts"

for root, dirs, files in os.walk(base_dir):
    for file in files:
        if file.endswith(".ini"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8-sig") as f:
                content = f.read()

            # Ersetze BOM (\ufeff) falls vorhanden
            content = content.replace('\ufeff', '')

            # Optional: UTF-16 speichern, falls MT5 das verlangt
            with open(path, "w", encoding="utf-16") as f:
                f.write(content)

            print(f"✔️ Datei bereinigt: {path}")

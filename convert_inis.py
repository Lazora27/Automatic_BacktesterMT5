import os
from pathlib import Path

# Basis-Verzeichnis, wo Batch_0001 bis Batch_0060 liegen
BASE_DIR = r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Experts"

# Alle Batch-Ordner
BATCH_FOLDERS = [f"Batch_{str(i).zfill(4)}" for i in range(1, 61)]

# Funktion: Konvertiere Datei in UTF-16 LE BOM
def convert_to_utf16_le(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(file_path, 'w', encoding='utf-16') as f:
            f.write(content)
        print(f"✅ Erfolgreich konvertiert: {file_path}")
    except Exception as e:
        print(f"❌ Fehler bei {file_path}: {e}")

# Funktion: Prüfe ob Datei UTF-16 LE BOM ist
def check_utf16_le(file_path):
    try:
        with open(file_path, 'rb') as f:
            bom = f.read(2)
            if bom == b'\xff\xfe':
                return True
            else:
                return False
    except Exception as e:
        print(f"❌ Fehler beim Prüfen von {file_path}: {e}")
        return False

# Durchlaufe alle Batch-Ordner und konvertiere alle INIs
def process_all_inis():
    for batch_folder in BATCH_FOLDERS:
        batch_path = os.path.join(BASE_DIR, batch_folder)
        if not os.path.exists(batch_path):
            continue

        # Suche alle EA-Unterordner
        for ea_folder in os.listdir(batch_path):
            ea_path = os.path.join(batch_path, ea_folder)
            if os.path.isdir(ea_path):
                ini_path = os.path.join(ea_path, 'ini')
                if os.path.exists(ini_path):
                    for ini_file in os.listdir(ini_path):
                        if ini_file.lower().endswith('.ini'):
                            full_ini_path = os.path.join(ini_path, ini_file)
                            convert_to_utf16_le(full_ini_path)
                            if check_utf16_le(full_ini_path):
                                print(f"✅ UTF-16 LE BOM korrekt: {full_ini_path}")
                            else:
                                print(f"❌ WARNUNG: {full_ini_path} ist NICHT UTF-16 LE BOM!")

if __name__ == "__main__":
    process_all_inis()

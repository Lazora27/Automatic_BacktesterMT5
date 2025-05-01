import os
import shutil
import time
from datetime import datetime

# === Konfiguration ===
MT5_REPORT_FOLDER = r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\Reports"
INI_FOLDER = r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Experts"
OUTPUT_FOLDER = r"C:\Users\nikol\Desktop\#3 Test Good\AI_Trader\StructuredReports"
CHECK_INTERVAL = 5  # in Sekunden

# === Hilfsfunktion zum Mapping ===
def extract_info_from_filename(filename):
    name = os.path.splitext(filename)[0]  # z.B. Absorption_AUDCAD_H1
    parts = name.split("_")
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]  # EA, Symbol, Timeframe
    return None, None, None 

def find_ea_name(symbol, timeframe):
    for root, dirs, files in os.walk(INI_FOLDER):
        for file in files:
            if file.endswith(".ini") and symbol in file and timeframe in file:
                return file.split("_")[0]  # Extrahiere EA-Name
    return "UnknownEA"

def move_and_rename_report(file_path):
    filename = os.path.basename(file_path)
    ea, symbol, tf = extract_info_from_filename(filename)

    if not ea or not symbol or not tf:
        print(f"❌ Kann Info aus {filename} nicht lesen.")
        return

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"{ea}_{symbol}_{tf}_Report_{now}{os.path.splitext(filename)[1]}"
    target_dir = os.path.join(OUTPUT_FOLDER, ea, f"Run_{datetime.now().date()}", symbol, tf)
    os.makedirs(target_dir, exist_ok=True)
    shutil.move(file_path, os.path.join(target_dir, new_filename))
    print(f"✅ {filename} gespeichert unter {new_filename}")

# === Hauptüberwachung ===
print("🔍 Report-Watcher gestartet. Drücke STRG+C zum Beenden.")
processed_files = set()

try:
    while True:
        for file in os.listdir(MT5_REPORT_FOLDER):
            if file.endswith((".xml", ".html", ".csv", ".png")):
                full_path = os.path.join(MT5_REPORT_FOLDER, file)
                if file not in processed_files:
                    move_and_rename_report(full_path)
                    processed_files.add(file)
        time.sleep(CHECK_INTERVAL)
except KeyboardInterrupt:
    print("🛑 Beendet durch Benutzer.")

import os

# Basis-Verzeichnis
root_path = r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Experts"

# Alle Batch_0001 bis Batch_0060 Ordner durchgehen
for batch_folder in os.listdir(root_path):
    batch_folder_path = os.path.join(root_path, batch_folder)
    if os.path.isdir(batch_folder_path) and batch_folder.startswith("Batch_"):
        for ea_folder in os.listdir(batch_folder_path):
            ini_folder_path = os.path.join(batch_folder_path, ea_folder, "ini")
            if os.path.isdir(ini_folder_path):
                for file in os.listdir(ini_folder_path):
                    if file.endswith(".ini"):
                        ini_file_path = os.path.join(ini_folder_path, file)
                        print(f"🔧 Repariere Datei: {ini_file_path}")

                        # UTF-16 lesen
                        with open(ini_file_path, "r", encoding="utf-16") as f:
                            content = f.read()

                        # Entferne alle überflüssigen Leerzeichen zwischen Buchstaben
                        repaired_content = content.replace(' ', '').replace('\n\n', '\n')

                        # Datei sauber neu speichern in UTF-16 LE
                        with open(ini_file_path, "w", encoding="utf-16") as f:
                            f.write(repaired_content)

print("✅ Alle INI-Dateien wurden erfolgreich repariert und gespeichert!")

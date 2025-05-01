import os

# Basis-Pfad zum Experts-Ordner
root_path = r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Experts"

# Gehe durch alle Batch_XXXX Ordner
for batch_num in range(1, 61):
    batch_folder = os.path.join(root_path, f"Batch_{batch_num:04d}")
    
    if os.path.isdir(batch_folder):
        for ea_folder in os.listdir(batch_folder):
            ea_path = os.path.join(batch_folder, ea_folder)
            ini_path = os.path.join(ea_path, "ini")
            
            if os.path.isdir(ini_path):
                for ini_file in os.listdir(ini_path):
                    if ini_file.endswith(".ini"):
                        ini_full_path = os.path.join(ini_path, ini_file)
                        
                        # EA-Name automatisch aus INI-Dateinamen extrahieren
                        ea_name = ini_file.split('_')[0]
                        expert_file = f"{ea_name}.ex5"
                        
                        # Debug-Ausgabe
                        print(f"🔧 Bearbeite: {ini_full_path}")
                        print(f"   ➡️  Setze EA-Datei: {expert_file}")

                        try:
                            with open(ini_full_path, "r", encoding="utf-16") as f:
                                lines = f.readlines()

                            with open(ini_full_path, "w", encoding="utf-16") as f:
                                for line in lines:
                                    if line.strip().startswith("Expert="):
                                        f.write(f"Expert={expert_file}\n")
                                    else:
                                        f.write(line)
                        except Exception as e:
                            print(f"⚠️ Fehler bei {ini_full_path}: {e}")

print("\n✅ Fertig: Alle INI-Dateien wurden erfolgreich korrigiert!")

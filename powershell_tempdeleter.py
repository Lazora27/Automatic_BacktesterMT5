$basePath = "C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Experts"

# Für alle Batch_0001 bis Batch_0060
1..60 | ForEach-Object {
    $batchName = "Batch_{0:D4}" -f $_
    $fullPath = Join-Path $basePath $batchName

    if (Test-Path $fullPath) {
        # Lösche alle Dateien und Ordner, die mit "temp" beginnen
        Get-ChildItem $fullPath -Filter "temp*" -Force -Recurse |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
}

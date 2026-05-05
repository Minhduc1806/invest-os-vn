$ErrorActionPreference = "Stop"
Set-Location "C:\Users\DUC\.openclaw\workspace\invest-os-vn"

$logDir = "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$log = Join-Path $logDir "phase6_daily_refresh_$stamp.log"

function Run-Step($name, $cmd) {
  Write-Output "=== $name ===" | Tee-Object -FilePath $log -Append
  Write-Output $cmd | Tee-Object -FilePath $log -Append
  cmd /c $cmd 2>&1 | Tee-Object -FilePath $log -Append
  if ($LASTEXITCODE -ne 0) { throw "$name failed with exit code $LASTEXITCODE" }
}

# TE direct HTTP often 403. If browser-extracted cache already fresh, macro parser validates it.
Run-Step "macro parser" "python scripts\macro_rates_parser.py --merge-live"
Run-Step "market snapshot" "python scripts\data_adapters.py --market --tickers PNJ,FPT,MWG,VCB,SSI,HPG,TCB,MBB,VIC,VHM,GVR,STB,VPB,CTG,ACB,MSN,VNM,GAS,PLX,SAB,VRE,VJC,POW,SHB,TPB,HDB,LPB,VIB,BCM,BID"
Run-Step "HOSE EOD" "python scripts\fdata_hose_universe.py --timeframe EOD"
Run-Step "investable universe" "python scripts\fdata_universe_filter.py"
Run-Step "news refresh" "python scripts\refresh_news_live.py --allow-partial"
Run-Step "audit" "python scripts\phase4_real_data_gap_audit.py --mode eod"
Run-Step "E2E" "python scripts\phase4_e2e.py"
Run-Step "validate reports" "python scripts\validate_phase5_reports.py"

Write-Output "PHASE6_DAILY_REFRESH_OK" | Tee-Object -FilePath $log -Append

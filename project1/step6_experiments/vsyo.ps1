# Zapusk vsey ocheredi + zapret zasypaniya na vremya raboty.
# Kod tolko latinicey, teksty - v Write-Host. Fayl sohranen v UTF-8 s BOM.

Add-Type -Name Power -Namespace Win32 -MemberDefinition @'
[DllImport("kernel32.dll", SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@

# PowerShell 5.1 chitaet 0x80000000 kak Int32 i poluchaet -2147483648,
# poetomu pryamoe privedenie k uint32 padaet. Pishem desyatichnym chislom.
$CONT = [uint32]2147483648   # ES_CONTINUOUS      = 0x80000000
$SYS  = [uint32]1            # ES_SYSTEM_REQUIRED = 0x00000001

# Poka rabotaet etot skript, sistema ne uydet v son.
[void][Win32.Power]::SetThreadExecutionState($CONT -bor $SYS)

Set-Location -Path $PSScriptRoot
$log = Join-Path $PSScriptRoot "log_vsyo.txt"
"=== $(Get-Date) ===" | Out-File -FilePath $log -Encoding utf8

function Shag($nomer, $chto, $cmd) {
    Write-Host ""
    Write-Host "[$nomer] $chto" -ForegroundColor Cyan
    "" | Out-File -FilePath $log -Append -Encoding utf8
    "=== [$nomer] $chto" | Out-File -FilePath $log -Append -Encoding utf8
    Invoke-Expression $cmd 2>&1 | Tee-Object -FilePath $log -Append
}

try {
    Shag 1 "sborka datasetov" 'python ..\step2_dataset\prepare_data.py --seed 5 --drop-clips ryabinnik2686 --val-clips snegir2692,ryabinnik2686,kormushka2729'
    Shag 2 "bez drozda v obuchenii" 'python ..\step4_baseline_model\train.py --exp frozen --aug off --data datasets\birds_v1_course3_drop --tag drop'
    Shag 3 "drugoy vid v proverke" 'python ..\step4_baseline_model\train.py --exp frozen --aug off --data datasets\birds_v1_fixval --tag fixval'
    Shag 4 "shest melkih klassov" 'python ..\step4_baseline_model\train.py --exp base --data datasets\birds_v1_fine'
    Shag 5 "razbor po klipam" 'python ..\step5_metrics\po_klipam.py --weights runs\classify\frozen_ep10\weights\best.pt --data datasets\birds_v1_episode'
    Shag 6 "svodka" 'python ..\step5_metrics\svodka.py'
}
finally {
    # Vernut obychnoe povedenie pitaniya.
    [void][Win32.Power]::SetThreadExecutionState($CONT)
    Write-Host ""
    Write-Host "Gotovo. Ves vyvod v log_vsyo.txt" -ForegroundColor Green
    Write-Host "Rezhim sna vernut v obychnyy."
}

# Ustanovka vsego, chto nuzhno dlya Proekta 1 i paneli Proekta 2.
#
#     powershell -ExecutionPolicy Bypass -File setup_windows.ps1
#
# ROS 2 etim skriptom NE stavitsya - on ne stavitsya cherez pip.
# Pro nego otdelno v USTANOVKA.ru.md.
#
# Fayl sohranyon v UTF-8 s BOM: bez BOM Windows PowerShell 5.1 chitaet ego
# kak ANSI i lomaet kirillicu v soobscheniyah.

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Step($text) {
    Write-Host ""
    Write-Host ("=" * 66) -ForegroundColor Cyan
    Write-Host $text -ForegroundColor Cyan
    Write-Host ("=" * 66) -ForegroundColor Cyan
}

Step "1. Проверяю питон"
$py = "python"
& $py --version
if ($LASTEXITCODE -ne 0) {
    $py = "py"
    & $py --version
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Питон не найден." -ForegroundColor Red
        Write-Host "Поставь с python.org версию 3.10-3.12 и отметь галочку" -ForegroundColor Red
        Write-Host "Add python.exe to PATH при установке." -ForegroundColor Red
        exit 1
    }
}
Write-Host "использую: $py"
& $py -m pip install --upgrade pip

Step "2. Основное: обучение, экспорт, панель"
Write-Host "ultralytics тянет за собой torch, это около 2 ГБ. Остальное мелочь."
& $py -m pip install ultralytics onnx onnxruntime clearml gradio opencv-python pillow
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Установка отвалилась. Частая причина - права." -ForegroundColor Yellow
    Write-Host "Попробуй ту же команду с флагом --user:" -ForegroundColor Yellow
    Write-Host "  $py -m pip install --user ultralytics onnx onnxruntime clearml gradio opencv-python pillow"
    exit 1
}

Step "3. Проверяю, что всё встало"
& $py check_env.py

Step "Готово"
Write-Host "Дальше по порядку:" -ForegroundColor Green
Write-Host "  1. clearml-init                 ключи берутся на app.clear.ml"
Write-Host "  2. split_by_clip в dataset.py    это пишешь ты"
Write-Host "  3. $py dataset.py --check"
Write-Host "  4. $py train.py --exp small --frac 0.33"

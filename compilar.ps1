# Compila el APK de Conteo Vehicular.
#
# Existe como script y no como un comando a mano porque hay tres cosas que si se
# olvidan producen fallos que no se parecen a su causa:
#
#   1. Compilar FUERA de OneDrive. OneDrive bloquea archivos mientras Gradle
#      escribe los miles de intermedios de build/, y la compilacion muere con
#      "El proceso no tiene acceso al archivo porque esta siendo utilizado por
#      otro proceso".
#   2. Copiar config_sheets.py. No esta en el repositorio (lleva la URL y el
#      token de la planilla), y sin el la app compila pero queda sin
#      sincronizacion, lo que solo se nota mirando el dialogo Resumen.
#   3. Pasar --org cl.indata. Sin eso el paquete queda com.flet.* y Android lo
#      instala como una app DISTINTA en vez de actualizar la que ya esta.
#   4. Firmar con la clave propia de la app (desde la 1.1.0). Un APK con otra
#      firma -la debug de este PC, por ejemplo- no se instala encima del que
#      ya esta en el telefono. La clave NO esta en el repo: se copia desde el
#      PC donde se creo (ver README) a %USERPROFILE%\conteo_vehicular_firma.
#
# Uso:   .\compilar.ps1
#
# Al terminar imprime la ruta del APK.

$ErrorActionPreference = "Stop"

$fuente = $PSScriptRoot
$taller = Join-Path $env:USERPROFILE "builds\conteo_vehicular_app"
$firma  = if ($env:FIRMA_DIR) { $env:FIRMA_DIR } else { Join-Path $env:USERPROFILE "conteo_vehicular_firma" }
$jks    = Join-Path $firma "conteo_vehicular_release.jks"
$clave  = Join-Path $firma "password.txt"

Write-Host "== Conteo Vehicular: compilacion del APK ==" -ForegroundColor Cyan
Write-Host "fuente: $fuente"
Write-Host "taller: $taller  (fuera de OneDrive)"
Write-Host ""

# --- 1. Demonios de Gradle vivos de compilaciones anteriores ---------------
# Solo los java de Gradle: cerrar todos los java del equipo mataria tambien
# Android Studio u otros programas abiertos.
$gradle = @(Get-CimInstance Win32_Process -Filter "Name = 'java.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match 'gradle' })
if ($gradle.Count -gt 0) {
    Write-Host "Cerrando $($gradle.Count) demonio(s) de Gradle que podrian tener archivos tomados..."
    $gradle | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

# --- 2. Copiar el fuente al taller ----------------------------------------
$modulos = @("main.py", "modelos.py", "almacenamiento.py", "tema.py",
             "config_sheets.py", "requirements.txt")

$faltan = @()
foreach ($m in $modulos) {
    if (-not (Test-Path (Join-Path $fuente $m))) { $faltan += $m }
}
if ($faltan.Count -gt 0) {
    Write-Host ""
    Write-Host "FALTAN ARCHIVOS: $($faltan -join ', ')" -ForegroundColor Red
    if ($faltan -contains "config_sheets.py") {
        Write-Host "Copia config_sheets.ejemplo.py como config_sheets.py y pon la URL y el token." -ForegroundColor Yellow
    }
    exit 1
}

if (-not ((Test-Path $jks) -and (Test-Path $clave))) {
    Write-Host ""
    Write-Host "FALTA LA CLAVE DE FIRMA en $firma" -ForegroundColor Red
    Write-Host "Copia ahi conteo_vehicular_release.jks y password.txt (ver README)." -ForegroundColor Yellow
    Write-Host "Sin ella el APK saldria con otra firma y no se instalaria encima." -ForegroundColor Yellow
    exit 1
}

New-Item -ItemType Directory -Force -Path $taller | Out-Null
foreach ($m in $modulos) { Copy-Item (Join-Path $fuente $m) $taller -Force }
Remove-Item (Join-Path $taller "assets") -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $fuente "assets") $taller -Recurse -Force
Write-Host "Copiados $($modulos.Count) modulos + assets/" -ForegroundColor Green

# --- 3. Compilar -----------------------------------------------------------
# El numero de compilacion es la fecha y hora (aaMMddHH): asi cada APK lleva un
# versionCode mayor que el anterior, y `adb shell dumpsys package` dice de
# cuando es el que esta instalado. Antes todos salian como 1 / 1.0.0 y no
# habia forma de distinguirlos sin abrir el APK.
$version = "1.1.0"
$numero  = Get-Date -Format "yyMMddHH"
Write-Host "version $version, compilacion $numero"

$pass = (Get-Content $clave -Raw).Trim()
$env:FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD = $pass
$env:FLET_ANDROID_SIGNING_KEY_PASSWORD = $pass

Push-Location $taller
try {
    Write-Host ""
    Write-Host "Compilando. La primera vez se demora bastante (Gradle y Flutter)..." -ForegroundColor Cyan
    flet build apk `
        --org cl.indata `
        --product "Conteo Vehicular" `
        --build-version $version `
        --build-number $numero `
        --android-permissions android.permission.MANAGE_EXTERNAL_STORAGE=true `
        --android-adaptive-icon-background "#FFFFFF" `
        --splash-color "#000000" `
        --splash-dark-color "#000000" `
        --android-signing-key-store $jks `
        --android-signing-key-alias upload
    $codigo = $LASTEXITCODE
} finally {
    Pop-Location
    Remove-Item Env:FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:FLET_ANDROID_SIGNING_KEY_PASSWORD -ErrorAction SilentlyContinue
}

Write-Host ""
if ($codigo -ne 0) {
    Write-Host "La compilacion FALLO (codigo $codigo)." -ForegroundColor Red
    Write-Host "Si el error menciona 'esta siendo utilizado por otro proceso',"
    Write-Host "vuelve a correr este script: cierra los demonios de Gradle al partir."
    exit $codigo
}

$apk = Get-ChildItem (Join-Path $taller "build\apk\*.apk") -ErrorAction SilentlyContinue |
       Select-Object -First 1
if (-not $apk) {
    Write-Host "Compilo sin error pero no encuentro el APK en build\apk" -ForegroundColor Red
    exit 1
}

Write-Host "APK listo:" -ForegroundColor Green
Write-Host "  $($apk.FullName)"
Write-Host "  $([math]::Round($apk.Length / 1MB)) MB"
Write-Host ""
Write-Host "Instalar encima con: adb install -r `"$($apk.FullName)`"" -ForegroundColor Yellow

#!/usr/bin/env bash
# Compila el APK firmado desde el commit actual (HEAD), en Linux.
#
# - Exige que no haya cambios sin commitear: cada APK corresponde a un commit exacto.
# - Compila desde una copia limpia (git archive) FUERA del repo, con solo los
#   módulos de la app, más config_sheets.py (que no está en el repo).
# - Firma con la clave propia de la app. Desde la 1.1.0 TODAS las versiones deben
#   ir firmadas con ella: un APK con otra firma no se instala encima del anterior.
#
# Requisitos (ver README, "Compilar el APK"):
#   FLET      ejecutable de flet 0.85.3   (por defecto ~/.venvs/timer_aeropuerto/bin/flet)
#   FIRMA_DIR carpeta con la clave de firma, FUERA del repo
#             (por defecto ~/In-data/conteo_vehicular_firma), con:
#               conteo_vehicular_release.jks  y  password.txt
set -euo pipefail

VERSION="1.1.0"                       # subir con cada cambio relevante

REPO="$(cd "$(dirname "$0")" && pwd)"
FLET="${FLET:-$HOME/.venvs/timer_aeropuerto/bin/flet}"
FIRMA_DIR="${FIRMA_DIR:-$HOME/In-data/conteo_vehicular_firma}"
SALIDA="${SALIDA:-$(dirname "$REPO")/conteo_vehicular_build}"

cd "$REPO"
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    echo "ERROR: hay cambios sin commitear. Haz commit antes de compilar." >&2
    exit 1
fi
[[ -x "$FLET" ]] || { echo "ERROR: no encuentro flet en $FLET" >&2; exit 1; }
[[ -f "$FIRMA_DIR/conteo_vehicular_release.jks" && -f "$FIRMA_DIR/password.txt" ]] || {
    echo "ERROR: falta la clave de firma en $FIRMA_DIR" >&2; exit 1; }
[[ -f config_sheets.py ]] || {
    echo "ERROR: falta config_sheets.py (copia config_sheets.ejemplo.py y pon la URL y el token)." >&2
    exit 1; }

COMMIT="$(git rev-parse --short HEAD)"
# versionCode: fecha y hora de compilación, siempre mayor que la anterior.
NUMERO="$(date +%y%m%d%H)"

DIR="$SALIDA/conteo_vehicular_app"
rm -rf "$DIR"
mkdir -p "$DIR"
git archive HEAD main.py modelos.py almacenamiento.py tema.py requirements.txt assets \
    | tar -x -C "$DIR"
cp config_sheets.py "$DIR/"

echo "Compilando v$VERSION (build $NUMERO) desde $COMMIT en $DIR"
cd "$DIR"
PASS="$(cat "$FIRMA_DIR/password.txt")"
FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD="$PASS" \
FLET_ANDROID_SIGNING_KEY_PASSWORD="$PASS" \
"$FLET" build apk --yes --no-rich-output \
    --org cl.indata \
    --product "Conteo Vehicular" \
    --build-version "$VERSION" \
    --build-number "$NUMERO" \
    --android-permissions android.permission.MANAGE_EXTERNAL_STORAGE=true \
    --android-adaptive-icon-background "#FFFFFF" \
    --splash-color "#000000" \
    --splash-dark-color "#000000" \
    --android-signing-key-store "$FIRMA_DIR/conteo_vehicular_release.jks" \
    --android-signing-key-alias upload

APK="$SALIDA/conteo_vehicular_v${VERSION}_${COMMIT}.apk"
cp "$DIR/build/apk/conteo_vehicular_app.apk" "$APK"
echo "APK listo: $APK"

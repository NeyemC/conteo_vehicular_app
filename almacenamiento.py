"""
Persistencia local (JSON) y exportación a CSV.

En Android se prefiere la carpeta externa propia del app
(/storage/emulated/0/Android/data/<pkg>/files/...), porque es la única que el
encuestador puede alcanzar para sacar los CSV del teléfono (por cable, o desde
un explorador de archivos) y que además no exige permisos en Android 10+.
Si el sistema no la deja escribir, se cae a la carpeta interna del app, que
siempre funciona aunque no sea alcanzable por el usuario.
En Windows/Mac se usa ~/conteo_vehicular.
"""

import json
import csv
import re as _re
import tempfile
from pathlib import Path
from modelos import (SesionConteo, Vehiculo, combinaciones,
                     etiqueta_tipo, etiqueta_ejes)

NOMBRE_CARPETA = "conteo_vehicular"


def _escribible(carpeta: Path) -> bool:
    """Comprueba con una escritura real, no solo con os.access()."""
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        prueba = carpeta / ".escritura_ok"
        prueba.write_text("ok", encoding="utf-8")
        prueba.unlink()
        return True
    except Exception:
        return False


def _candidatas(ruta_modulo: str) -> list[tuple[Path, bool]]:
    """Carpetas a intentar, de más a menos alcanzable por el usuario."""
    lista: list[tuple[Path, bool]] = []

    # En Android el app corre en /data/user/0/<pkg>/ o /data/data/<pkg>/
    m = _re.search(r'^(/data/(?:user/\d+|data)/([^/]+))', ruta_modulo)
    if m:
        raiz_app, paquete = Path(m.group(1)), m.group(2)
        lista += [
            # Descargas primero: es la carpeta que el encuestador sabe abrir y la
            # que aparece al conectar el teléfono por cable. Exige el permiso
            # "Acceso a todos los archivos" (ver README); si no está concedido,
            # el mkdir falla y se sigue con las siguientes.
            (Path("/storage/emulated/0/Download") / NOMBRE_CARPETA, True),
            (Path("/sdcard/Download") / NOMBRE_CARPETA, True),
            (Path("/storage/emulated/0/Documents") / NOMBRE_CARPETA, True),
            # Carpeta externa propia del app. En la práctica falla, porque el
            # directorio padre /Android/data/<pkg> solo lo crea el sistema.
            (Path(f"/storage/emulated/0/Android/data/{paquete}/files")
             / NOMBRE_CARPETA, True),
            (Path(f"/sdcard/Android/data/{paquete}/files") / NOMBRE_CARPETA, True),
            # Interna: siempre escribible, pero inalcanzable desde afuera.
            (raiz_app / "files" / NOMBRE_CARPETA, False),
        ]
    else:
        # Path.home() puede lanzar RuntimeError si no hay HOME (pasa en Android).
        try:
            lista.append((Path.home() / NOMBRE_CARPETA, True))
        except Exception:
            pass

    # Respaldos que no dependen del entorno: la carpeta del propio módulo
    # (si Python pudo importar desde ahí, existe) y el directorio temporal.
    for base, alcanzable in ((Path(ruta_modulo).parent, False),
                             (Path(tempfile.gettempdir()), False)):
        try:
            lista.append((base / NOMBRE_CARPETA, alcanzable))
        except Exception:
            pass
    return lista


def _elegir_carpeta(ruta_modulo: str | None = None) -> tuple[Path, bool, str | None]:
    """
    Retorna (carpeta, es_alcanzable_por_el_usuario, error_o_None).

    NUNCA lanza excepción: esto corre al importar el módulo, así que un fallo
    acá impediría que arranque la app y dejaría la pantalla en negro sin
    ninguna pista de lo ocurrido.
    `ruta_modulo` existe para poder probar la rama de Android desde el escritorio.
    """
    if ruta_modulo is None:
        try:
            ruta_modulo = str(Path(__file__))
        except Exception:
            ruta_modulo = "."

    intentos = []
    try:
        candidatas = _candidatas(ruta_modulo)
    except Exception as ex:
        return Path("."), False, f"No pude listar carpetas candidatas: {ex!r}"

    for carpeta, alcanzable in candidatas:
        try:
            if _escribible(carpeta):
                return carpeta, alcanzable, None
            intentos.append(f"{carpeta} (no escribible)")
        except Exception as ex:
            intentos.append(f"{carpeta} ({type(ex).__name__})")

    return (Path("."), False,
            "Ninguna carpeta resultó escribible. Intenté: " + " | ".join(intentos))


CARPETA_DATOS, CARPETA_ALCANZABLE, CARPETA_ERROR = _elegir_carpeta()

# Para que la app pueda explicar qué hacer si no logró usar Descargas.
EN_DESCARGAS = "Download" in str(CARPETA_DATOS) or "Documents" in str(CARPETA_DATOS)
EN_ANDROID = bool(_re.search(r'^/data/(?:user/\d+|data)/', str(Path(__file__))))

AYUDA_PERMISO = (
    "Para que los CSV queden en Descargas hay que conceder el permiso una vez:\n"
    "Ajustes → Aplicaciones → Conteo Vehicular → Permisos → "
    "Acceso a todos los archivos → Permitir.\n"
    "Mientras no esté concedido, los datos igual se guardan y se sincronizan "
    "con Google Sheets, pero no se pueden sacar por cable."
)


def ruta_sesion(sesion_id: str) -> Path:
    return CARPETA_DATOS / f"sesion_{sesion_id}.json"


def guardar(sesion: SesionConteo):
    """Guarda la sesión completa como JSON (sobreescribe si existe)."""
    with open(ruta_sesion(sesion.id), "w", encoding="utf-8") as f:
        json.dump(sesion.to_dict(), f, ensure_ascii=False, indent=2)


def cargar(sesion_id: str) -> SesionConteo | None:
    ruta = ruta_sesion(sesion_id)
    if not ruta.exists():
        return None
    with open(ruta, encoding="utf-8") as f:
        return SesionConteo.from_dict(json.load(f))


def listar_sesiones() -> list[dict]:
    """
    Metadatos de las sesiones guardadas, de la más reciente a la más antigua.

    Se ordena por la hora del último vehículo registrado, no por la fecha: en
    una jornada puede haber varias sesiones del mismo día, y la que le interesa
    al encuestador es la que estaba usando cuando se cerró la app.
    Nunca lanza: un archivo corrupto se salta en silencio.
    """
    sesiones = []
    try:
        archivos = list(CARPETA_DATOS.glob("sesion_*.json"))
    except Exception:
        return []

    for archivo in archivos:
        try:
            with open(archivo, encoding="utf-8") as f:
                d = json.load(f)
            vehiculos = d.get("vehiculos", [])
            marcas = [v["registrado_en"] for v in vehiculos if v.get("registrado_en")]
            sesiones.append({
                "id": d["id"],
                "aeropuerto": d["aeropuerto"],
                "posicion": d["posicion"],
                "encuestador": d["encuestador"],
                "fecha": d["fecha"],
                "total": sum(1 for v in vehiculos if not v["anulado"]),
                "ultima_actividad": max(marcas) if marcas else d["fecha"],
            })
        except Exception:
            pass
    return sorted(sesiones, key=lambda s: s["ultima_actividad"], reverse=True)


# ---------------------------------------------------------------------------
# Exportación a CSV
# ---------------------------------------------------------------------------

COLUMNAS_DETALLE = [
    "sesion_id", "fecha", "aeropuerto", "posicion", "encuestador",
    "veh_id", "numero", "grupo_ejes", "tipo", "sentido",
    "hora", "timestamp", "nota", "anulado",
]

COLUMNAS_RESUMEN = [
    "sesion_id", "fecha", "aeropuerto", "posicion",
    "sentido", "grupo_ejes", "tipo", "cantidad",
]


def _prefijo(sesion: SesionConteo) -> str:
    codigo = sesion.aeropuerto.split(" - ")[0]
    return f"conteo_{codigo}_pos{sesion.posicion}_{sesion.fecha}_{sesion.id}"


def _fila_detalle(sesion: SesionConteo, v: Vehiculo) -> dict:
    return {
        "sesion_id":   sesion.id,
        "fecha":       sesion.fecha,
        "aeropuerto":  sesion.aeropuerto,
        "posicion":    sesion.posicion,
        "encuestador": sesion.encuestador,
        "veh_id":      v.id,
        "numero":      v.numero,
        "grupo_ejes":  v.etiqueta_ejes(),
        "tipo":        v.etiqueta(),
        "sentido":     v.sentido,
        "hora":        v.hora(),
        "timestamp":   v.registrado_en,
        "nota":        v.nota,
        "anulado":     "Sí" if v.anulado else "No",
    }


def exportar_csv(sesion: SesionConteo) -> Path:
    """Un registro por vehículo, incluidos los anulados (marcados como tal)."""
    ruta = CARPETA_DATOS / f"{_prefijo(sesion)}_detalle.csv"
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS_DETALLE)
        writer.writeheader()
        for v in sorted(sesion.vehiculos, key=lambda v: v.registrado_en):
            writer.writerow(_fila_detalle(sesion, v))
    return ruta


def _filas_resumen(sesion: SesionConteo) -> list[dict]:
    """Agrega los vigentes por sentido × grupo de ejes × tipo."""
    cuenta: dict[tuple[str, str, str], int] = {}
    for v in sesion.vigentes():
        clave = (v.sentido, v.grupo_ejes, v.tipo)
        cuenta[clave] = cuenta.get(clave, 0) + 1

    orden = combinaciones()          # (grupo_ejes, tipo) en el orden de la grilla
    claves = sorted(cuenta, key=lambda k: (k[0], orden.index((k[1], k[2]))))
    return [
        {
            "sesion_id":  sesion.id,
            "fecha":      sesion.fecha,
            "aeropuerto": sesion.aeropuerto,
            "posicion":   sesion.posicion,
            "sentido":    sentido,
            "grupo_ejes": etiqueta_ejes(grupo),
            "tipo":       etiqueta_tipo(tipo),
            "cantidad":   cuenta[(sentido, grupo, tipo)],
        }
        for sentido, grupo, tipo in claves
    ]


def exportar_resumen_csv(sesion: SesionConteo) -> Path:
    """Conteos agregados por sentido, tipo y número de ejes.
    Para agrupar por tramos horarios, usar la columna `timestamp` del detalle."""
    ruta = CARPETA_DATOS / f"{_prefijo(sesion)}_resumen.csv"
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS_RESUMEN)
        writer.writeheader()
        writer.writerows(_filas_resumen(sesion))
    return ruta


# ---------------------------------------------------------------------------
# Sincronización con Google Sheets (opcional)
# ---------------------------------------------------------------------------
# CONFIGURAR ANTES DE TERRENO (ver apps_script.gs y el README):
#   1. Pegar en _GAS_URL la URL /exec del Apps Script desplegado sobre la
#      planilla de ESTE estudio. Mientras esté vacía la app exporta solo a CSV
#      y no menciona Sheets.
#   2. _GAS_TOKEN debe ser idéntico al TOKEN del script, para que nadie que
#      encuentre la URL pueda escribir en la planilla.
# Las credenciales viven en config_sheets.py, que NO va al repositorio: el repo
# es público y con la URL más el token cualquiera podría escribir en la planilla.
# Si el archivo no está, la app exporta solo a CSV y lo indica en el Resumen.
# Ver config_sheets.ejemplo.py.
_GAS_URL = ""
_GAS_TOKEN = ""
try:
    from config_sheets import GAS_URL as _GAS_URL, GAS_TOKEN as _GAS_TOKEN
except Exception:
    pass

# Se sincroniza el DETALLE, no el resumen: cada fila tiene un veh_id único, así
# que el script puede hacer upsert y volver a exportar es inocuo. Eso permite
# sincronizar varias veces durante la jornada como respaldo, y que una anulación
# posterior corrija la fila ya enviada en vez de duplicarla. El resumen se
# reconstruye en la planilla con una tabla dinámica.
_CLAVE_SYNC = "veh_id"


def sheets_configurado() -> bool:
    return bool(_GAS_URL)


def sincronizar_sheets(sesion: SesionConteo) -> dict:
    """
    Envía el detalle de la sesión al Apps Script que lo escribe en Sheets.
    Usa urllib (stdlib) para evitar dependencias nativas en Android.
    Retorna {"nuevas": n, "actualizadas": m, "total": t} según el script.
    """
    import urllib.request

    if not _GAS_URL:
        raise RuntimeError(
            "No hay URL de Google Apps Script configurada en almacenamiento.py")

    filas = [[str(_fila_detalle(sesion, v)[col]) for col in COLUMNAS_DETALLE]
             for v in sorted(sesion.vehiculos, key=lambda v: v.registrado_en)]
    if not filas:
        return {"nuevas": 0, "actualizadas": 0, "total": 0}

    payload = json.dumps({
        "token":    _GAS_TOKEN,
        "clave":    _CLAVE_SYNC,
        "columnas": COLUMNAS_DETALLE,
        "filas":    filas,
    }).encode("utf-8")
    req = urllib.request.Request(
        _GAS_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        cuerpo = resp.read().decode("utf-8").strip()

    try:
        datos = json.loads(cuerpo)
    except ValueError:
        raise RuntimeError(f"Respuesta inesperada del script: {cuerpo[:200]}")
    if isinstance(datos, dict) and datos.get("error"):
        raise RuntimeError(datos["error"])
    return datos

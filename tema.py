"""
Paleta de la app, en modo oscuro.

Dos razones para el negro real (#000000) en los fondos grandes: en la pantalla
AMOLED del teléfono los píxeles negros están apagados y no consumen batería, y
en terreno de noche no encandila al encuestador.

Todos los pares texto/fondo de esta paleta están medidos contra WCAG AA
(4.5:1 para texto normal, 3:1 para texto grande y elementos de interfaz).
La verificación vive en las pruebas: si se cambia un color y baja del umbral,
la prueba falla.
"""

# ── Fondos ─────────────────────────────────────────────────────────────────
FONDO         = "#000000"   # pantalla; negro real para ahorrar batería
SUPERFICIE    = "#17171D"   # tarjetas, encabezado, paneles
SUPERFICIE_2  = "#24242E"   # campos, chips sin seleccionar
BORDE         = "#3A3A46"   # bordes visibles
BORDE_SUAVE   = "#2A2A34"   # separadores

# ── Texto ──────────────────────────────────────────────────────────────────
TEXTO         = "#F2F2F6"   # principal
TEXTO_2       = "#BFBFCB"   # secundario
TEXTO_3       = "#9A9AA6"   # terciario (mínimo legible, no bajar más)
TEXTO_SOBRE_ACENTO = "#0B0B10"  # sobre fondos de acento claros

# ── Acentos ────────────────────────────────────────────────────────────────
# Claros a propósito: un indigo oscuro sobre negro no se distingue.
PRIMARIO      = "#A3B1FF"
ENTRADA       = "#6FE39B"
SALIDA        = "#FFB472"
ERROR         = "#FF9A90"
ERROR_FONDO   = "#2A1416"

# ── Grupos de ejes ─────────────────────────────────────────────────────────
# El color separa los dos bloques de la grilla de un vistazo, que es lo que
# importa cuando se está tocando botones rápido.
COLOR_EJES = {
    "2":  "#A3B1FF",
    "3+": "#FFBE7D",
}

# ── Sentidos (solo posición 5) ──────────────────────────────────────────────
COLOR_SENTIDO = {
    "Izquierda": "#6FE39B",
    "Derecha":   "#8FD6FF",
}

# ── Medidas de la grilla ────────────────────────────────────────────────────
# La posición 5 dibuja la grilla dos veces, una por sentido, así que con las
# medidas amplias no cabe en pantalla. En las posiciones 1-4 hay un solo bloque
# y sobra espacio, así que ahí los botones van más grandes y se tocan mejor.
MEDIDAS = {
    "amplio": {
        "icono": 27, "cuenta": 24, "etiqueta": 11, "titulo": 14,
        "pad_arriba": 12, "pad_abajo": 10, "sep_interno": 3,
        "radio": 12, "sep_botones": 7, "sep_bloques": 8,
    },
    "compacto": {
        "icono": 20, "cuenta": 18, "etiqueta": 10, "titulo": 12,
        "pad_arriba": 7, "pad_abajo": 5, "sep_interno": 1,
        "radio": 10, "sep_botones": 5, "sep_bloques": 5,
    },
}


def medidas(compacto: bool) -> dict:
    return MEDIDAS["compacto" if compacto else "amplio"]


def con_alfa(hex_color: str, alfa: float) -> str:
    """
    Mezcla un color con el fondo en vez de usar transparencia real.
    Sobre negro, un color al 12% de opacidad se ve casi negro; mezclarlo
    explícitamente da un resultado predecible y medible.
    """
    c = hex_color.lstrip("#")
    f = FONDO.lstrip("#")
    mezcla = tuple(
        round(int(c[i:i + 2], 16) * alfa + int(f[i:i + 2], 16) * (1 - alfa))
        for i in (0, 2, 4)
    )
    return "#%02X%02X%02X" % mezcla


# ── Utilidades de contraste (usadas por las pruebas) ───────────────────────

def _luminancia(hex_color: str) -> float:
    c = hex_color.lstrip("#")
    canales = []
    for i in (0, 2, 4):
        v = int(c[i:i + 2], 16) / 255
        canales.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    r, g, b = canales
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(color_a: str, color_b: str) -> float:
    """Razón de contraste WCAG entre dos colores (1.0 a 21.0)."""
    la, lb = _luminancia(color_a), _luminancia(color_b)
    claro, oscuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (oscuro + 0.05)

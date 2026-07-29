"""
Modelos de datos para la app de conteo vehicular en aeropuertos.

El conteo es por toques: cada botón de la grilla registra un vehículo con su
tipo, su grupo de ejes y —solo en la posición 5— el sentido. Se guarda el
timestamp absoluto de cada registro, así que cualquier agrupación temporal
(flujo por hora, por tramos de 15 minutos) se calcula después sobre el CSV.
"""

from datetime import datetime
import uuid

# ---------------------------------------------------------------------------
# Catálogo
#
# La grilla tiene dos bloques por sentido, uno por grupo de ejes. Cada bloque
# lista sus tipos y todos los botones comparten el ancho de su fila.
# ---------------------------------------------------------------------------

TIPOS_VEHICULO = {
    "auto_furgon": "Auto/furgón",
    "bus":         "Bus",
    "camion":      "Camión",
    "moto":        "Moto",
    "trolley":     "Trolley",
}

# clave → (etiqueta, tipos del bloque)
# Todos los botones son del mismo ancho: se reparten el espacio de su fila.
GRUPOS_EJES = {
    "2":  ("Vehículo de 2 ejes",
           ["auto_furgon", "bus", "camion", "moto", "trolley"]),
    "3+": ("Vehículo de 3 o más ejes",
           ["camion", "bus", "trolley"]),
}

ETIQUETA_EJES = {"2": "2 ejes", "3+": "3 o más ejes"}

# ---------------------------------------------------------------------------
# Posiciones
#
# En la 5 se cuentan los dos sentidos por separado (las dos flechas de la
# maqueta). En el resto hay un solo flujo y el sentido no aplica.
# ---------------------------------------------------------------------------

POSICIONES = ["1", "2", "3", "4", "5"]
POSICION_DOS_SENTIDOS = "5"
SENTIDOS_DOBLES = ["Izquierda", "Derecha"]
SIN_SENTIDO = ""


def sentidos_de(posicion: str) -> list[str]:
    """Sentidos a registrar en una posición. Una sola entrada si no aplica."""
    if str(posicion) == POSICION_DOS_SENTIDOS:
        return list(SENTIDOS_DOBLES)
    return [SIN_SENTIDO]


def tiene_dos_sentidos(posicion: str) -> bool:
    return str(posicion) == POSICION_DOS_SENTIDOS


AEROPUERTOS = [
    "ANF - Antofagasta",
    "ARI - Arica",
    "BBA - Balmaceda",
    "CPO - Copiapó",
    "LSC - La Serena",
    "PUQ - Punta Arenas",
]


def etiqueta_tipo(tipo: str) -> str:
    return TIPOS_VEHICULO[tipo]


def etiqueta_ejes(grupo: str) -> str:
    return ETIQUETA_EJES[grupo]


def combinaciones() -> list[tuple[str, str]]:
    """Todos los (grupo_ejes, tipo) válidos, en el orden de la grilla."""
    return [(grupo, t) for grupo, (_, tipos) in GRUPOS_EJES.items()
            for t in tipos]


# ---------------------------------------------------------------------------
# Clase Vehiculo
# ---------------------------------------------------------------------------

class Vehiculo:
    """
    Un vehículo registrado con un toque. Los errores se marcan como anulados en
    vez de borrarse, para que el CSV conserve la traza de lo ocurrido en terreno.
    """

    def __init__(self, tipo: str, grupo_ejes: str, sentido: str, numero: int,
                 nota: str = "", extra: dict | None = None):
        self.id = str(uuid.uuid4())[:6].upper()
        self.tipo = tipo
        self.grupo_ejes = grupo_ejes
        self.sentido = sentido
        self.numero = numero          # correlativo dentro de la sesión
        self.nota = nota
        self.extra = extra or {}
        self.anulado = False
        self.registrado_en = datetime.now().isoformat()

    # --- Consulta --------------------------------------------------------

    def etiqueta(self) -> str:
        return etiqueta_tipo(self.tipo)

    def etiqueta_ejes(self) -> str:
        return etiqueta_ejes(self.grupo_ejes)

    def descripcion(self) -> str:
        d = f"{self.etiqueta()} · {self.etiqueta_ejes()}"
        if self.sentido:
            d += f" · {self.sentido}"
        return d

    def hora(self) -> str:
        return datetime.fromisoformat(self.registrado_en).strftime("%H:%M:%S")

    # --- Mutación --------------------------------------------------------

    def anular(self):
        self.anulado = True

    # --- Serialización ---------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "grupo_ejes": self.grupo_ejes,
            "sentido": self.sentido,
            "numero": self.numero,
            "nota": self.nota,
            "extra": self.extra,
            "anulado": self.anulado,
            "registrado_en": self.registrado_en,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Vehiculo":
        v = cls(d["tipo"], d["grupo_ejes"], d["sentido"], d["numero"],
                d.get("nota", ""), d.get("extra", {}))
        v.id = d["id"]
        v.anulado = d["anulado"]
        v.registrado_en = d["registrado_en"]
        return v


# ---------------------------------------------------------------------------
# Clase SesionConteo
# ---------------------------------------------------------------------------

class SesionConteo:
    """Agrupa todo el conteo de una jornada en una posición."""

    def __init__(self, aeropuerto: str, encuestador: str, posicion: str,
                 fecha: str | None = None):
        self.id = str(uuid.uuid4())[:8].upper()
        self.aeropuerto = aeropuerto
        self.encuestador = encuestador
        self.posicion = str(posicion)
        self.fecha = fecha or datetime.now().strftime("%Y-%m-%d")
        self.vehiculos: list[Vehiculo] = []
        self._contador = 0

    # --- Mutación --------------------------------------------------------

    def agregar_vehiculo(self, tipo: str, grupo_ejes: str,
                         sentido: str = SIN_SENTIDO, nota: str = "",
                         extra: dict | None = None) -> Vehiculo:
        self._contador += 1
        v = Vehiculo(tipo, grupo_ejes, sentido, self._contador, nota, extra)
        self.vehiculos.append(v)
        return v

    def deshacer(self) -> Vehiculo | None:
        """Anula el último registro vigente. Devuelve el anulado, o None."""
        v = self.ultimo()
        if v is not None:
            v.anular()
        return v

    # --- Consulta --------------------------------------------------------

    def vigentes(self) -> list[Vehiculo]:
        return [v for v in self.vehiculos if not v.anulado]

    def total(self) -> int:
        return len(self.vigentes())

    def ultimo(self) -> Vehiculo | None:
        for v in reversed(self.vehiculos):
            if not v.anulado:
                return v
        return None

    def sentidos(self) -> list[str]:
        return sentidos_de(self.posicion)

    def dos_sentidos(self) -> bool:
        return tiene_dos_sentidos(self.posicion)

    def total_sentido(self, sentido: str) -> int:
        return sum(1 for v in self.vigentes() if v.sentido == sentido)

    def cuenta(self, tipo: str, grupo_ejes: str,
               sentido: str = SIN_SENTIDO) -> int:
        """Conteo de una casilla de la grilla: lo que se muestra en su botón."""
        return sum(1 for v in self.vigentes()
                   if v.tipo == tipo and v.grupo_ejes == grupo_ejes
                   and v.sentido == sentido)

    def totales_por_tipo(self) -> dict[tuple[str, str], int]:
        """{(grupo_ejes, tipo): n} en el orden de la grilla, solo los usados."""
        cuenta: dict[tuple[str, str], int] = {}
        for v in self.vigentes():
            k = (v.grupo_ejes, v.tipo)
            cuenta[k] = cuenta.get(k, 0) + 1
        return {k: cuenta[k] for k in combinaciones() if k in cuenta}

    def totales_por_ejes(self) -> dict[str, int]:
        cuenta = {g: 0 for g in GRUPOS_EJES}
        for v in self.vigentes():
            cuenta[v.grupo_ejes] += 1
        return cuenta

    # --- Serialización ---------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "aeropuerto": self.aeropuerto,
            "encuestador": self.encuestador,
            "posicion": self.posicion,
            "fecha": self.fecha,
            "contador": self._contador,
            "vehiculos": [v.to_dict() for v in self.vehiculos],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SesionConteo":
        s = cls(d["aeropuerto"], d["encuestador"], d["posicion"], d["fecha"])
        s.id = d["id"]
        s._contador = d["contador"]
        s.vehiculos = [Vehiculo.from_dict(v) for v in d["vehiculos"]]
        return s

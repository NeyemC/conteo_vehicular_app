"""
Pruebas de la lógica de la app (sin interfaz).

    python -m unittest discover pruebas

No van en el APK: compilar.ps1 copia solo los módulos de la app.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import almacenamiento as A  # noqa: E402
import modelos as M  # noqa: E402
import tema as T  # noqa: E402


class Contraste(unittest.TestCase):
    """Cada par texto/fondo que usa la interfaz, contra WCAG AA (4,5:1)."""

    PARES = {
        "texto / fondo":            (T.TEXTO, T.FONDO),
        "texto / superficie 2":     (T.TEXTO, T.SUPERFICIE_2),
        "texto 2 / superficie":     (T.TEXTO_2, T.SUPERFICIE),
        "texto 3 / fondo":          (T.TEXTO_3, T.FONDO),
        "texto 3 / superficie":     (T.TEXTO_3, T.SUPERFICIE),
        "texto 3 / superficie 2":   (T.TEXTO_3, T.SUPERFICIE_2),
        "sobre acento / primario":  (T.TEXTO_SOBRE_ACENTO, T.PRIMARIO),
        "sobre acento / entrada":   (T.TEXTO_SOBRE_ACENTO, T.ENTRADA),
        "sobre acento / salida":    (T.TEXTO_SOBRE_ACENTO, T.SALIDA),
        "sobre acento / error":     (T.TEXTO_SOBRE_ACENTO, T.ERROR),
        "error / fondo de error":   (T.ERROR, T.ERROR_FONDO),
        "en la planilla / tarjeta": (T.ENTRADA, T.SUPERFICIE),
        "falta subir / tarjeta":    (T.SALIDA, T.SUPERFICIE),
        "texto 2 / fondo de error": (T.TEXTO_2, T.ERROR_FONDO),
        "primario / su chip":       (T.PRIMARIO, T.con_alfa(T.PRIMARIO, 0.28)),
        **{f"ejes {g} / botón": (c, T.SUPERFICIE_2)
           for g, c in T.COLOR_EJES.items()},
        **{f"sentido {s} / su franja": (c, T.con_alfa(c, 0.18))
           for s, c in T.COLOR_SENTIDO.items()},
    }

    def test_pares_sobre_el_minimo(self):
        for nombre, (a, b) in self.PARES.items():
            with self.subTest(nombre):
                self.assertGreaterEqual(T.contraste(a, b), 4.5)

    def test_contraste_extremos(self):
        self.assertAlmostEqual(T.contraste("#FFFFFF", "#000000"), 21.0)
        self.assertAlmostEqual(T.contraste("#777777", "#777777"), 1.0)


class Modelo(unittest.TestCase):

    def test_veh_id_unico_dentro_de_la_sesion(self):
        s = M.SesionConteo("ANF - Antofagasta", "x", "1")
        # Forzar que uuid repita el mismo id: agregar_vehiculo debe esquivarlo.
        ids = iter(["AAAAAA", "AAAAAA", "AAAAAA", "BBBBBB"])
        with mock.patch.object(M, "_id_corto", lambda n: next(ids)):
            a = s.agregar_vehiculo("bus", "2")
            b = s.agregar_vehiculo("bus", "2")
        self.assertEqual((a.id, b.id), ("AAAAAA", "BBBBBB"))

    def test_posiciones_de_dos_sentidos_segun_aeropuerto(self):
        # En Calama la 4 y la 5; en el resto solo la 5.
        for aero, dobles in (("CJC - Calama", {"4", "5"}),
                             ("ANF - Antofagasta", {"5"}),
                             ("PUQ - Punta Arenas", {"5"})):
            for p in M.POSICIONES:
                with self.subTest(aero=aero, posicion=p):
                    s = M.SesionConteo(aero, "x", p)
                    self.assertEqual(s.dos_sentidos(), p in dobles)
                    self.assertEqual(s.sentidos(),
                                     M.SENTIDOS_DOBLES if p in dobles
                                     else [M.SIN_SENTIDO])

    def test_calama_en_la_lista(self):
        self.assertIn("CJC - Calama", M.AEROPUERTOS)
        self.assertEqual(M.AEROPUERTOS, sorted(M.AEROPUERTOS))

    def test_deshacer_anula_el_ultimo_vigente(self):
        s = M.SesionConteo("ANF - Antofagasta", "x", "5")
        s.agregar_vehiculo("bus", "2", "Izquierda")
        b = s.agregar_vehiculo("moto", "2", "Derecha")
        self.assertIs(s.deshacer(), b)
        self.assertEqual(s.total(), 1)
        self.assertEqual(s.total_sentido("Derecha"), 0)
        s.deshacer()
        self.assertIsNone(s.deshacer())

    def test_ida_y_vuelta_json(self):
        s = M.SesionConteo("ANF - Antofagasta", "x", "5")
        s.agregar_vehiculo("camion", "3+", "Derecha", nota="n")
        s.deshacer()
        s.agregar_vehiculo("bus", "2", "Izquierda")
        r = M.SesionConteo.from_dict(json.loads(json.dumps(s.to_dict())))
        self.assertEqual(r.to_dict(), s.to_dict())
        # El correlativo sigue donde iba al reanudar.
        self.assertEqual(r.agregar_vehiculo("bus", "2", "Izquierda").numero, 3)


class Almacenamiento(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.carpeta = Path(self._tmp.name)
        self._parche = mock.patch.object(A, "CARPETA_DATOS", self.carpeta)
        self._parche.start()

    def tearDown(self):
        self._parche.stop()
        self._tmp.cleanup()

    def _sesion(self):
        s = M.SesionConteo("CPO - Copiapó", "Ana", "5")
        s.agregar_vehiculo("bus", "2", "Izquierda")
        s.agregar_vehiculo("camion", "3+", "Derecha")
        return s

    def test_guardar_y_cargar(self):
        s = self._sesion()
        A.guardar(s)
        self.assertEqual(A.cargar(s.id).to_dict(), s.to_dict())
        self.assertEqual(list(self.carpeta.glob("*.tmp")), [])

    def test_guardado_interrumpido_no_trunca_el_json(self):
        s = self._sesion()
        A.guardar(s)
        antes = A.ruta_sesion(s.id).read_text(encoding="utf-8")
        s.agregar_vehiculo("moto", "2", "Izquierda")
        with mock.patch.object(A.json, "dump", side_effect=OSError("disco lleno")):
            with self.assertRaises(OSError):
                A.guardar(s)
        self.assertEqual(A.ruta_sesion(s.id).read_text(encoding="utf-8"), antes)

    def test_listar_incluye_sesiones_con_todo_anulado(self):
        s = self._sesion()
        s.deshacer()
        s.deshacer()
        A.guardar(s)
        (self.carpeta / "sesion_ROTO.json").write_text("{", encoding="utf-8")
        [meta] = A.listar_sesiones()
        self.assertEqual((meta["total"], meta["registros"]), (0, 2))

    def test_csv(self):
        s = self._sesion()
        s.deshacer()
        det = A.exportar_csv(s).read_text(encoding="utf-8-sig").splitlines()
        self.assertEqual(det[0].split(","), A.COLUMNAS_DETALLE)
        self.assertEqual(len(det), 3)            # los anulados también van
        res = A.exportar_resumen_csv(s).read_text(encoding="utf-8-sig")
        self.assertIn("Izquierda,2 ejes,Bus,1", res)
        self.assertNotIn("Camión", res)          # anulado: no suma

    def test_sincronizar_manda_llave_compuesta_y_anulados(self):
        s = self._sesion()
        s.deshacer()
        s.deshacer()
        enviado = {}

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return b'{"nuevas": 0, "actualizadas": 2, "total": 2}'

        def urlopen(req, timeout):
            enviado.update(json.loads(req.data))
            return Resp()

        with mock.patch.object(A, "_GAS_URL", "https://ejemplo"), \
             mock.patch("urllib.request.urlopen", urlopen):
            A.sincronizar_sheets(s)
        self.assertEqual(enviado["clave"], ["sesion_id", "veh_id"])
        self.assertEqual(len(enviado["filas"]), 2)
        i = A.COLUMNAS_DETALLE.index("anulado")
        self.assertEqual({f[i] for f in enviado["filas"]}, {"Sí"})


class EstadoSubida(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._parche = mock.patch.object(A, "CARPETA_DATOS", Path(self._tmp.name))
        self._parche.start()
        self.s = M.SesionConteo("CJC - Calama", "Ana", "4")
        self.s.agregar_vehiculo("bus", "2", "Izquierda")

    def tearDown(self):
        self._parche.stop()
        self._tmp.cleanup()

    def _sincronizar(self, falla=None):
        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def read(self): return b'{"nuevas": 1, "actualizadas": 0, "total": 1}'

        def urlopen(req, timeout):
            if falla:
                raise falla
            return Resp()

        with mock.patch.object(A, "_GAS_URL", "https://ejemplo"), \
             mock.patch("urllib.request.urlopen", urlopen):
            A.sincronizar_sheets(self.s)

    def _estado_listado(self):
        [meta] = A.listar_sesiones()
        return meta["subida"]

    def test_sesion_anterior_a_la_marca_no_tiene_estado(self):
        (A.ruta_sesion(self.s.id)).write_text(
            json.dumps(self.s.to_dict()), encoding="utf-8")
        self.assertIsNone(self._estado_listado())

    def test_ciclo_pendiente_subida_pendiente(self):
        A.guardar(self.s)
        self.assertEqual(self._estado_listado(), A.PENDIENTE)
        self._sincronizar()
        self.assertEqual(self._estado_listado(), A.SUBIDA)
        # Guardar de nuevo no borra la marca de lo ya subido.
        A.guardar(self.s)
        self.assertEqual(self._estado_listado(), A.SUBIDA)
        # Un cambio posterior (registro o anulación) la deja pendiente otra vez.
        self.s.deshacer()
        A.guardar(self.s)
        self.assertEqual(self._estado_listado(), A.PENDIENTE)

    def test_envio_fallido_queda_pendiente(self):
        import urllib.error
        A.guardar(self.s)
        with self.assertRaises(urllib.error.URLError):
            self._sincronizar(urllib.error.URLError(OSError(7, "No address")))
        self.assertEqual(self._estado_listado(), A.PENDIENTE)

    def test_mensajes_de_error(self):
        import socket
        import urllib.error
        sin_red = "Sin conexión a internet, o la señal es muy débil."
        for ex in (urllib.error.URLError(socket.gaierror(7, "x")),
                   TimeoutError("timed out"), socket.timeout()):
            with self.subTest(ex=ex):
                self.assertEqual(A.mensaje_error_sync(ex), sin_red)
        http = urllib.error.HTTPError("u", 500, "x", None, None)
        self.assertIn("HTTP 500", A.mensaje_error_sync(http))
        self.assertEqual(A.mensaje_error_sync(RuntimeError("Token inválido")),
                         "Token inválido")


class Carpeta(unittest.TestCase):

    def test_android_prefiere_descargas_y_cae_a_la_interna(self):
        ruta = "/data/user/0/cl.indata.conteo_vehicular_app/files/flet/app/x.py"
        candidatas = A._candidatas(ruta)
        self.assertEqual(candidatas[0],
                         (Path("/storage/emulated/0/Download/conteo_vehicular"), True))
        self.assertIn((Path("/data/user/0/cl.indata.conteo_vehicular_app/files/"
                            "conteo_vehicular"), False), candidatas)

    def test_elegir_carpeta_nunca_lanza(self):
        with mock.patch.object(A, "_escribible", side_effect=RuntimeError):
            carpeta, alcanzable, error = A._elegir_carpeta("/x/y.py")
        self.assertEqual((carpeta, alcanzable), (Path("."), False))
        self.assertIn("RuntimeError", error)


if __name__ == "__main__":
    unittest.main()

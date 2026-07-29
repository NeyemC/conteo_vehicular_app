"""
App de Conteo Vehicular Aeroportuario

El conteo es por toques: la pantalla principal es una grilla de botones, uno por
combinación de tipo y grupo de ejes. Cada toque registra un vehículo. En la
posición 5 la grilla se duplica, un bloque por sentido.
"""

import traceback
import flet as ft

# Los imports van protegidos porque un fallo acá ocurre ANTES de que exista la
# app: en Android eso se ve como una pantalla en negro, sin ninguna pista. Así
# el error queda guardado y se muestra en pantalla más abajo.
_ERROR_ARRANQUE = None
try:
    import tema as T
    from modelos import (SesionConteo, GRUPOS_EJES, POSICIONES, AEROPUERTOS,
                         etiqueta_tipo)
    from almacenamiento import (guardar, cargar, listar_sesiones,
                                exportar_csv, exportar_resumen_csv,
                                sincronizar_sheets, sheets_configurado,
                                CARPETA_DATOS, CARPETA_ALCANZABLE, CARPETA_ERROR,
                                EN_DESCARGAS, EN_ANDROID, AYUDA_PERMISO)
except Exception:
    _ERROR_ARRANQUE = traceback.format_exc()

ICONO_TIPO = {
    "auto_furgon": ft.Icons.DIRECTIONS_CAR,
    "bus":         ft.Icons.DIRECTIONS_BUS,
    "camion":      ft.Icons.LOCAL_SHIPPING,
    "moto":        ft.Icons.TWO_WHEELER,
    "trolly":      ft.Icons.LUGGAGE,
}

ICONO_SENTIDO = {"Izquierda": ft.Icons.ARROW_BACK, "Derecha": ft.Icons.ARROW_FORWARD}


def _borde(w, color):
    s = ft.BorderSide(w, color)
    return ft.Border(left=s, top=s, right=s, bottom=s)


def _pantalla_error(page: ft.Page, titulo: str, detalle: str):
    """
    Muestra el error en pantalla. Sin esto, cualquier excepción al arrancar deja
    el teléfono en negro y no hay forma de saber qué pasó sin conectar el cable.
    """
    page.title = "Error"
    page.bgcolor = T.FONDO if T else "#000000"
    page.padding = 0
    page.floating_action_button = None
    page.controls.clear()
    page.controls.append(ft.Container(
        expand=True,
        padding=ft.Padding(20, 28, 20, 20),
        content=ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, controls=[
            ft.Row(spacing=10, controls=[
                ft.Icon(ft.Icons.ERROR_OUTLINE, color=T.ERROR, size=30),
                ft.Text(titulo, size=19, weight=ft.FontWeight.BOLD,
                        color=T.ERROR, expand=True),
            ]),
            ft.Text("Muestra esta pantalla a quien mantiene la app.",
                    size=13, color=T.TEXTO_2),
            ft.Container(
                bgcolor=T.SUPERFICIE_2,
                border_radius=8,
                padding=ft.Padding(12, 12, 12, 12),
                content=ft.Text(detalle, size=11, selectable=True,
                                font_family="monospace", color=T.TEXTO)),
        ]),
    ))
    page.update()


async def main(page: ft.Page):
    if _ERROR_ARRANQUE:
        _pantalla_error(page, "No se pudieron cargar los módulos", _ERROR_ARRANQUE)
        return
    try:
        await _app(page)
    except Exception:
        _pantalla_error(page, "Error al iniciar la app", traceback.format_exc())


async def _app(page: ft.Page):
    page.title = "Conteo Vehicular"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    sesion: list[SesionConteo | None] = [None]

    # ── diálogos ──────────────────────────────────────────────────────────
    def abrir_dialogo(dlg): page.show_dialog(dlg)
    def cerrar_dialogo():   page.pop_dialog()

    def aviso(titulo: str, mensaje: str):
        abrir_dialogo(ft.AlertDialog(
            modal=False,
            title=ft.Text(titulo),
            content=ft.Text(mensaje),
            actions=[ft.TextButton("OK", on_click=lambda e: cerrar_dialogo())],
        ))

    # ══════════════════════════════════════════════════════════════════════
    # Pantalla de configuración
    # ══════════════════════════════════════════════════════════════════════
    def mostrar_setup():
        dd_aero = ft.Dropdown(
            label="Aeropuerto",
            options=[ft.dropdown.Option(a) for a in AEROPUERTOS],
            border_radius=12)
        campo_nombre = ft.TextField(
            label="Nombre del encuestador", hint_text="Ej: Juan Pérez",
            prefix_icon=ft.Icons.PERSON, border_radius=12)
        dd_posicion = ft.Dropdown(
            label="Posición",
            options=[ft.dropdown.Option(p, text=f"Posición {p}")
                     for p in POSICIONES],
            border_radius=12,
            leading_icon=ft.Icons.PLACE)
        nota_pos = ft.Text(
            "La posición 5 cuenta los dos sentidos por separado.",
            size=11, color=T.TEXTO_3, text_align=ft.TextAlign.CENTER)
        error = ft.Text("", color=T.ERROR, size=13)

        async def iniciar(e):
            if not dd_aero.value or not campo_nombre.value or not dd_posicion.value:
                error.value = "Completa aeropuerto, nombre y posición."
                page.update()
                return
            sesion[0] = SesionConteo(
                aeropuerto=dd_aero.value,
                encuestador=campo_nombre.value.strip(),
                posicion=dd_posicion.value,
            )
            guardar(sesion[0])
            mostrar_principal()

        # ── reanudar una sesión anterior ──────────────────────────────────
        # Sin esto, si Android mata la app en segundo plano (los Samsung lo
        # hacen seguido) la jornada queda en el disco pero sin forma de volver
        # a abrirla, y por lo tanto sin forma de sincronizarla nunca.
        def abrir_sesion(sid: str):
            try:
                s = cargar(sid)
            except Exception as ex:
                error.value = f"No se pudo abrir esa sesión: {ex}"
                page.update()
                return
            if s is None:
                error.value = "Esa sesión ya no está en el teléfono."
                page.update()
                return
            sesion[0] = s
            mostrar_principal()

        def tarjeta_sesion(meta: dict) -> ft.Container:
            hora = str(meta["ultima_actividad"])[11:16]
            detalle = meta["fecha"] + (f" · {hora}" if hora else "")
            detalle += f" · {meta['encuestador']}"
            async def _abrir(e, sid=meta["id"]):
                abrir_sesion(sid)

            return ft.Container(
                on_click=_abrir,
                bgcolor=T.SUPERFICIE, border_radius=10,
                padding=ft.Padding(14, 12, 12, 12),
                border=_borde(1, T.BORDE),
                content=ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10,
                    controls=[
                        ft.Column(spacing=2, expand=True, controls=[
                            ft.Text(f"Posición {meta['posicion']} · "
                                    f"{meta['aeropuerto'].split(' - ')[0]}",
                                    size=14, no_wrap=True,
                                    weight=ft.FontWeight.W_600, color=T.TEXTO),
                            ft.Text(detalle, size=11, color=T.TEXTO_3),
                        ]),
                        ft.Container(
                            bgcolor=T.con_alfa(T.PRIMARIO, 0.28), border_radius=8,
                            padding=ft.Padding(9, 4, 9, 4),
                            content=ft.Text(str(meta["total"]), size=14,
                                            weight=ft.FontWeight.BOLD,
                                            color=T.PRIMARIO)),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT, size=20, color=T.TEXTO_3),
                    ]),
            )

        try:
            guardadas = [m for m in listar_sesiones() if m["total"] > 0][:8]
        except Exception:
            guardadas = []

        bloque_reanudar = []
        if guardadas:
            bloque_reanudar = [
                ft.Divider(height=8),
                ft.Row(spacing=6, controls=[
                    ft.Icon(ft.Icons.HISTORY, size=17, color=T.TEXTO_2),
                    ft.Text("O continúa una sesión anterior", size=13,
                            weight=ft.FontWeight.W_500, color=T.TEXTO_2),
                ]),
                ft.Text("Al exportarla se sincroniza lo que falte en la "
                        "planilla. Reexportar no duplica.",
                        size=11, color=T.TEXTO_3),
                *[tarjeta_sesion(m) for m in guardadas],
            ]

        page.floating_action_button = None
        page.bgcolor = T.FONDO
        page.controls.clear()
        page.controls.append(
            ft.Container(
                expand=True, alignment=ft.Alignment(0, -1),
                padding=ft.Padding(32, 44, 32, 44),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=18, scroll=ft.ScrollMode.AUTO,
                    controls=[
                        ft.Icon(ft.Icons.DIRECTIONS_CAR, size=62, color=T.PRIMARIO),
                        ft.Text("Conteo Vehicular\nAeroportuario",
                                size=26, weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER, color=T.PRIMARIO),
                        ft.Divider(height=8),
                        dd_aero, campo_nombre, dd_posicion, nota_pos,
                        error,
                        # Un problema de almacenamiento tiene que verse antes de
                        # empezar a contar, no cuando ya hay datos que perder.
                        *([ft.Container(
                            bgcolor=T.ERROR_FONDO, border_radius=8,
                            padding=ft.Padding(12, 10, 12, 10),
                            content=ft.Column(spacing=4, controls=[
                                ft.Row(spacing=6, controls=[
                                    ft.Icon(ft.Icons.WARNING_AMBER,
                                            color=T.ERROR, size=18),
                                    ft.Text("No hay dónde guardar los datos",
                                            size=13, weight=ft.FontWeight.W_600,
                                            color=T.ERROR),
                                ]),
                                ft.Text(CARPETA_ERROR, size=10, selectable=True,
                                        color=T.TEXTO_2),
                            ]))] if CARPETA_ERROR else []),
                        ft.FilledButton(
                            "Iniciar Conteo", icon=ft.Icons.PLAY_ARROW,
                            on_click=iniciar,
                            style=ft.ButtonStyle(
                                padding=ft.Padding(40, 20, 40, 20),
                                shape=ft.RoundedRectangleBorder(radius=12),
                                bgcolor=T.PRIMARIO,
                                color=T.TEXTO_SOBRE_ACENTO)),
                        *bloque_reanudar,
                    ],
                ),
            )
        )
        page.update()

    # ══════════════════════════════════════════════════════════════════════
    # Pantalla de conteo: la grilla de botones
    # ══════════════════════════════════════════════════════════════════════
    def mostrar_principal():
        s = sesion[0]

        # Los textos que cambian con cada toque se guardan por clave para
        # actualizarlos en sitio, sin reconstruir la grilla completa: con 8 a 16
        # botones, redibujar todo en cada toque se siente lento.
        w_cuenta: dict[tuple[str, str, str], ft.Text] = {}
        w_total = ft.Text("0", size=28, weight=ft.FontWeight.BOLD, color=T.PRIMARIO)
        w_sentido: dict[str, ft.Text] = {}
        w_ultimo = ft.Text("Sin registros", size=12, color=T.TEXTO_3)
        btn_deshacer = ft.TextButton(
            "Deshacer", icon=ft.Icons.UNDO,
            style=ft.ButtonStyle(color=T.SALIDA),
            disabled=True)

        # ── refresco de contadores ────────────────────────────────────────
        def actualizar():
            for (grupo, tipo, sent), w in w_cuenta.items():
                w.value = str(s.cuenta(tipo, grupo, sent))
            w_total.value = str(s.total())
            for sent, w in w_sentido.items():
                w.value = str(s.total_sentido(sent))
            u = s.ultimo()
            if u is None:
                w_ultimo.value = "Sin registros"
                btn_deshacer.disabled = True
            else:
                w_ultimo.value = f"#{u.numero} · {u.descripcion()} · {u.hora()}"
                btn_deshacer.disabled = False
            page.update()

        def registrar(tipo: str, grupo: str, sent: str):
            s.agregar_vehiculo(tipo, grupo, sent)
            guardar(s)
            actualizar()

        def handler_boton(tipo: str, grupo: str, sent: str):
            async def _h(e):
                registrar(tipo, grupo, sent)
            return _h

        async def on_deshacer(e):
            v = s.deshacer()
            if v is not None:
                guardar(s)
                actualizar()

        btn_deshacer.on_click = on_deshacer

        # ── un botón de la grilla ─────────────────────────────────────────
        def boton(grupo: str, tipo: str, sent: str, ancho: bool) -> ft.Container:
            color = T.COLOR_EJES[grupo]
            w = ft.Text("0", size=19, weight=ft.FontWeight.BOLD, color=color)
            w_cuenta[(grupo, tipo, sent)] = w

            contenido = [
                ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=5,
                       controls=[
                           ft.Icon(ICONO_TIPO[tipo], size=15, color=T.TEXTO_2),
                           ft.Text(etiqueta_tipo(tipo), size=12,
                                   weight=ft.FontWeight.W_500, color=T.TEXTO,
                                   text_align=ft.TextAlign.CENTER),
                       ]),
                w,
            ]
            return ft.Container(
                on_click=handler_boton(tipo, grupo, sent),
                expand=True if not ancho else None,
                bgcolor=T.SUPERFICIE_2,
                border_radius=10,
                border=_borde(1, T.con_alfa(color, 0.45)),
                padding=ft.Padding(6, 10, 6, 8),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2, tight=True, controls=contenido),
            )

        # ── un bloque de grupo de ejes ────────────────────────────────────
        def bloque_grupo(grupo: str, sent: str) -> list:
            etiqueta, en_fila, anchos = GRUPOS_EJES[grupo]
            color = T.COLOR_EJES[grupo]
            filas = [
                ft.Text(etiqueta, size=14, weight=ft.FontWeight.W_600,
                        color=color),
                ft.Row(spacing=8, controls=[boton(grupo, t, sent, False)
                                            for t in en_fila]),
            ]
            for t in anchos:
                filas.append(ft.Row(controls=[boton(grupo, t, sent, False)]))
            return filas

        # ── la grilla de un sentido ───────────────────────────────────────
        def grilla(sent: str) -> ft.Container:
            hijos = []
            if sent:
                color = T.COLOR_SENTIDO[sent]
                w = ft.Text("0", size=14, weight=ft.FontWeight.BOLD, color=color)
                w_sentido[sent] = w
                hijos.append(ft.Container(
                    bgcolor=T.con_alfa(color, 0.18), border_radius=8,
                    padding=ft.Padding(10, 6, 10, 6),
                    content=ft.Row(spacing=8, controls=[
                        ft.Icon(ICONO_SENTIDO[sent], size=20, color=color),
                        ft.Text(sent, size=14, weight=ft.FontWeight.BOLD,
                                color=color, expand=True),
                        w,
                    ])))

            for grupo in GRUPOS_EJES:
                hijos.extend(bloque_grupo(grupo, sent))
            return ft.Container(
                content=ft.Column(spacing=8, controls=hijos))

        # ── encabezado ────────────────────────────────────────────────────
        encabezado = ft.Container(
            bgcolor=T.SUPERFICIE,
            border=ft.Border(bottom=ft.BorderSide(1, T.BORDE_SUAVE)),
            padding=ft.Padding(16, 12, 8, 12),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(spacing=2, expand=True, controls=[
                        ft.Text(f"Posición {s.posicion}  ·  "
                                f"{s.aeropuerto.split(' - ')[0]}",
                                color=T.TEXTO, size=15,
                                weight=ft.FontWeight.BOLD, no_wrap=True),
                        ft.Text(s.encuestador, color=T.TEXTO_3, size=11),
                    ]),
                    ft.Row(spacing=0, controls=[
                        w_total,
                        ft.IconButton(icon=ft.Icons.DOWNLOAD,
                                      icon_color=T.PRIMARIO,
                                      tooltip="Exportar CSV",
                                      on_click=accion_exportar),
                        ft.IconButton(icon=ft.Icons.INFO_OUTLINE,
                                      icon_color=T.PRIMARIO,
                                      tooltip="Resumen",
                                      on_click=mostrar_resumen),
                    ]),
                ]),
        )

        # ── barra inferior: último registro y deshacer ─────────────────────
        barra = ft.Container(
            bgcolor=T.SUPERFICIE,
            border=ft.Border(top=ft.BorderSide(1, T.BORDE_SUAVE)),
            padding=ft.Padding(14, 6, 6, 6),
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(spacing=0, expand=True, controls=[
                        ft.Text("Último", size=10, color=T.TEXTO_3),
                        w_ultimo,
                    ]),
                    btn_deshacer,
                ]),
        )

        # ── armado ────────────────────────────────────────────────────────
        grillas = []
        for i, sent in enumerate(s.sentidos()):
            if i:
                grillas.append(ft.Divider(height=18, color=T.BORDE_SUAVE))
            grillas.append(grilla(sent))

        page.floating_action_button = None
        page.bgcolor = T.FONDO
        page.controls.clear()
        page.controls.append(
            ft.Column(expand=True, spacing=0, controls=[
                encabezado,
                ft.Container(
                    expand=True,
                    padding=ft.Padding(12, 12, 12, 12),
                    content=ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO,
                                      controls=grillas)),
                barra,
            ]))
        actualizar()

    # ══════════════════════════════════════════════════════════════════════
    # Resumen
    # ══════════════════════════════════════════════════════════════════════
    async def mostrar_resumen(_e):
        s = sesion[0]

        filas = []
        por_ejes = s.totales_por_ejes()
        for grupo, (etiqueta, _, _) in GRUPOS_EJES.items():
            color = T.COLOR_EJES[grupo]
            filas.append(ft.Container(
                padding=ft.Padding(0, 6, 0, 2),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(etiqueta, size=12, expand=True,
                                weight=ft.FontWeight.W_600, color=color),
                        ft.Text(str(por_ejes[grupo]), size=13,
                                weight=ft.FontWeight.BOLD, color=color),
                    ])))
            usados = {t: n for (g, t), n in s.totales_por_tipo().items()
                      if g == grupo}
            if not usados:
                filas.append(ft.Text("   sin registros", size=12, italic=True,
                                     color=T.TEXTO_3))
                continue
            for tipo, n in usados.items():
                filas.append(ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        ft.Row(spacing=6, controls=[
                            ft.Container(width=8),
                            ft.Icon(ICONO_TIPO[tipo], size=15, color=T.TEXTO_2),
                            ft.Text(etiqueta_tipo(tipo), size=13),
                        ]),
                        ft.Text(str(n), size=13, weight=ft.FontWeight.BOLD),
                    ]))

        por_sentido = []
        if s.dos_sentidos():
            por_sentido = [
                ft.Divider(),
                ft.Text("Por sentido", size=13, weight=ft.FontWeight.W_600,
                        color=T.TEXTO_2),
                *[ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                    ft.Row(spacing=6, controls=[
                        ft.Icon(ICONO_SENTIDO[x], size=15,
                                color=T.COLOR_SENTIDO[x]),
                        ft.Text(x, size=13),
                    ]),
                    ft.Text(str(s.total_sentido(x)), size=13,
                            weight=ft.FontWeight.BOLD),
                ]) for x in s.sentidos()],
            ]

        abrir_dialogo(ft.AlertDialog(
            modal=False,
            title=ft.Text("Resumen de sesión"),
            content=ft.Container(width=420, content=ft.Column(
                tight=True, spacing=8, scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text(f"Aeropuerto: {s.aeropuerto}", size=13),
                    ft.Text(f"Posición:   {s.posicion}", size=13),
                    ft.Text(f"Encuestador: {s.encuestador}", size=13),
                    ft.Text(f"Fecha:      {s.fecha}", size=13),
                    ft.Divider(),
                    ft.Text(f"Total vigente: {s.total()}", size=14,
                            weight=ft.FontWeight.BOLD),
                    *por_sentido,
                    ft.Divider(),
                    *filas,
                    ft.Divider(),
                    ft.Text("Los datos se guardan solos en:", size=12,
                            color=T.TEXTO_2),
                    ft.Text(str(CARPETA_DATOS), size=11, color=T.TEXTO_3,
                            selectable=True),
                    ft.Text("✓ Alcanzable por cable." if CARPETA_ALCANZABLE
                            else "⚠ Carpeta interna: no se alcanza por cable.",
                            size=11,
                            color=T.ENTRADA if CARPETA_ALCANZABLE else T.SALIDA),
                    ft.Text("Sincroniza con Google Sheets al exportar."
                            if sheets_configurado() else
                            "Sin sincronización con Sheets: solo CSV local.",
                            size=11,
                            color=(T.ENTRADA if sheets_configurado()
                                   else T.SALIDA)),
                ])),
            actions=[ft.TextButton("Cerrar", on_click=lambda e: cerrar_dialogo())],
        ))

    # ══════════════════════════════════════════════════════════════════════
    # Exportar
    # ══════════════════════════════════════════════════════════════════════
    async def accion_exportar(_e):
        s = sesion[0]
        if not s.vigentes():
            aviso("Sin datos para exportar", "Aún no hay vehículos registrados.")
            return
        try:
            ruta_det = exportar_csv(s)
            ruta_res = exportar_resumen_csv(s)
            msg = (f"CSV guardados en:\n{CARPETA_DATOS}\n\n"
                   f"• {ruta_det.name}\n• {ruta_res.name}")
            if EN_DESCARGAS:
                msg += "\n\n✓ Están en Descargas: se ven al conectar el cable."
            elif not CARPETA_ALCANZABLE:
                msg += ("\n\n⚠ Esta carpeta es interna del teléfono: los CSV no "
                        "se pueden sacar por cable.")
                if EN_ANDROID:
                    msg += "\n\n" + AYUDA_PERMISO
            if sheets_configurado():
                try:
                    r = sincronizar_sheets(s)
                    msg += (f"\n\n✓ Google Sheets: {r.get('nuevas', 0)} fila(s) "
                            f"nuevas, {r.get('actualizadas', 0)} actualizada(s). "
                            f"Total en la planilla: {r.get('total', '?')}.")
                except Exception as ex_sheets:
                    msg += (f"\n\n⚠ No se pudo sincronizar con Sheets:\n"
                            f"{ex_sheets}\n\nLos CSV sí quedaron guardados. "
                            f"Puedes volver a exportar cuando haya señal: no "
                            f"se duplican los datos.")
            aviso("Exportado", msg)
        except Exception as ex:
            aviso("Error al exportar", str(ex))

    mostrar_setup()


if __name__ == "__main__":
    ft.run(main)

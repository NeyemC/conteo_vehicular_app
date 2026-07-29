# conteo_vehicular_app

Aplicación destinada al conteo vehicular en un aeropuerto, para un estudio sobre
el estado del pavimento. Registra cada vehículo con su tipo, número de ejes y
sentido de circulación, y exporta los conteos agregados por periodo.

Comparte arquitectura con `timer_aeropuerto_app` (Python + Flet, compilable a
APK Android).

## Estructura

| Archivo | Rol |
|---|---|
| `modelos.py` | Clases `SesionConteo` y `Vehiculo`, catálogo de tipos y cálculo de periodos |
| `almacenamiento.py` | Persistencia JSON, exportación a CSV y sincronización opcional con Google Sheets |
| `tema.py` | Paleta del modo oscuro, con utilidades de contraste que usan las pruebas |
| `main.py` | Interfaz Flet: setup, panel de conteo, diálogo de nueva entrada, resumen |
| `apps_script.gs` | Script que va pegado en la planilla de Google (no se ejecuta acá) |
| `assets/icon.png` | Icono de la app, 1024×1024. Flet lo toma de aquí por convención |
| `assets/splash.png` | Pantalla de carga, 1152×1152. Idem: por convención |
| `IN-DATA.png` | Logo original de la marca, fuente del icono. No se empaqueta en el APK |

## Clasificación de vehículos

Dos niveles: primero la **categoría**, que separa los vehículos según si su
presencia depende o no del flujo de pasajeros, y después el **tipo** específico
dentro de ella.

| Livianos y transporte de pasajeros | Carga y vehículos operacionales |
|---|---|
| *Dependientes del flujo de pasajeros* | *Independientes del flujo de pasajeros* |
| Auto particular | Camión liviano (courier) |
| Taxi | Camión mediano (reparto) |
| App (Uber, Cabify, DiDi) | Camión pesado (carga, contenedor) |
| Rent-a-car | Camión combustible (JET A-1) |
| Camioneta liviana | Articulado / semirremolque |
| Transfer / minibús | Catering |
| Bus | Mantención / servicios |
| Motocicleta | Emergencia / seguridad |
| | Concesionaria / administración |
| | Tractor de rampa / trolley |

El catálogo se define en un solo lugar, `TIPOS_VEHICULO` en `modelos.py`, donde
cada tipo declara su etiqueta, su categoría y sus ejes por defecto. Agregar o
mover un tipo es editar esa tabla; la UI y los CSV se ajustan solos.

## Trabajo sin internet

La sincronización **no envía un incremental: manda la sesión completa cada vez**,
y el Apps Script hace *upsert* por `veh_id`. De ahí salen dos propiedades que
importan en terreno:

- **Exportar sin señal no pierde nada.** Los CSV se escriben igual, y la
  siguiente exportación con red sube todo lo acumulado de una vez.
- **Reexportar nunca duplica.** Se puede apretar Exportar cuantas veces se
  quiera; las filas ya enviadas se actualizan, no se repiten.

Además, cada registro se guarda en el JSON local **en el momento**, sin esperar
a que se exporte.

### Reanudar una sesión

Si Android mata la app en segundo plano —los Samsung lo hacen seguido— la
pantalla inicial ofrece **continuar la sesión anterior**, con su punto, hora y
cantidad de vehículos. Sin esto la jornada quedaba en el disco pero sin forma de
volver a abrirla, y por lo tanto sin forma de sincronizarla nunca.

Se listan las 8 más recientes con al menos un vehículo, ordenadas por la hora del
último registro (no por fecha: en un día puede haber varias sesiones). Al
reanudar, el correlativo sigue donde iba.

## Flujo de uso

1. **Setup:** aeropuerto, nombre del encuestador y punto de conteo — o reanudar
   una sesión anterior.
2. **Conteo:** el botón `+` abre el diálogo en dos pasos — primero la categoría,
   después el tipo dentro de ella, más ejes, sentido y observación opcional.
   El diálogo recuerda el último sentido usado, porque en terreno se suelen
   registrar varios vehículos del mismo sentido seguidos. El panel superior
   muestra el total y el desglose entrada / salida.
3. **Exportar:** genera dos CSV — `_detalle` (un registro por vehículo) y
   `_resumen` (conteos por sentido × categoría × tipo × ejes).

## Modo oscuro

La app es oscura por defecto. Los fondos grandes van en **negro real**
(`#000000`): en la pantalla AMOLED del teléfono esos píxeles están apagados y no
consumen batería, y de noche no encandila.

La paleta vive completa en [tema.py](tema.py), no repartida por la interfaz.
**El contraste está medido, no supuesto**: `tema.py` incluye el cálculo de razón
de contraste WCAG y las pruebas verifican cada par texto/fondo. Los valores
actuales van de **5,5:1 a 18,8:1**, sobre el mínimo de 4,5:1 de WCAG AA. Si se
cambia un color y baja del umbral, la prueba falla.

Dos consecuencias del modo oscuro que no son obvias:

- **Los acentos son claros, no oscuros.** Un índigo oscuro desaparece sobre
  negro. Donde un chip queda seleccionado con fondo de acento claro, el texto
  pasa a tinta oscura — al revés que en modo claro.
- **El encabezado no va en color de acento.** Una franja brillante arriba
  encandila y, siendo grande y encendida, gasta batería.

El **splash** también es negro, con el logo recoloreado: el gris original daba
solo 2,90:1 sobre negro y el rojo 3,20:1, ambos insuficientes. El **icono** se
mantiene sobre blanco, porque es un área diminuta y ahí prima la marca.

## Criterios de diseño

- El **número de ejes** se captura por vehículo y no se deriva del tipo: es el
  dato que interesa para estimar solicitaciones sobre el pavimento. El tipo solo
  *propone* un valor por defecto, que el encuestador puede cambiar siempre.
- Todo lo que varía vehículo a vehículo (categoría, tipo, ejes, sentido) se
  pregunta **al registrar**, no en el setup: la pantalla inicial solo describe la
  jornada.
- El **color distingue la categoría**, no el tipo: con 18 tipos, lo que interesa
  leer de un vistazo en la lista es si el vehículo depende o no del flujo de
  pasajeros. La distinción fina la hace el icono y la etiqueta.
- Hasta que no se elige un tipo, el botón **Registrar** está deshabilitado: así
  un toque de más no puede contar un vehículo con un tipo por defecto.
- Se guarda el **timestamp absoluto** de cada registro. La app no agrupa por
  tramos horarios, pero cualquier agregación temporal (flujo por hora, por
  tramos de 15 minutos) se puede calcular después sobre la columna `timestamp`
  del CSV de detalle.
- Los errores se **anulan**, no se borran: quedan marcados en el CSV de detalle
  y dejan de sumar en los conteos.
- La sincronización con Sheets usa `urllib` de la stdlib contra un Google Apps
  Script, para no depender de librerías nativas en Android.
- Lo que se sincroniza es el **detalle**, no el resumen: cada fila tiene un
  `veh_id` único, así que el script hace *upsert* y **volver a exportar es
  inocuo** — no duplica. Eso permite sincronizar varias veces durante la jornada
  como respaldo, y que una anulación posterior corrija la fila ya enviada en vez
  de dejar un dato viejo. El resumen se reconstruye en la planilla con una tabla
  dinámica.
- Si la sincronización falla (sin señal), los CSV locales se escriben igual y la
  app lo dice: se puede reintentar más tarde sin miedo a duplicar.

## Dónde quedan los datos

Todo va a una sola carpeta, que la app muestra en el diálogo de Resumen:

- **Windows / Mac:** `~/conteo_vehicular`
- **Android:** `/storage/emulated/0/Android/data/<paquete>/files/conteo_vehicular`,
  que es alcanzable conectando el teléfono por cable. Si el sistema no deja
  escribir ahí, se cae a `/sdcard/Android/data/...` y por último a la carpeta
  interna del app — esa última **no** se puede alcanzar desde afuera, y en ese
  caso la app lo advierte al exportar y la sincronización con Sheets pasa a ser
  la única vía para recuperar los datos.

Tres archivos:

| Archivo | Cuándo se escribe |
|---|---|
| `sesion_<ID>.json` | Tras **cada** registro, sin apretar nada. Es el respaldo contra que se cierre la app o se acabe la batería. |
| `conteo_..._detalle.csv` | Al apretar Exportar. Un registro por vehículo. |
| `conteo_..._resumen.csv` | Al apretar Exportar. Conteos agregados. |

Los CSV van en UTF-8 con BOM, así que Excel los abre con los acentos correctos
de un doble clic.

## Configurar la planilla de Google

Sin esto la app funciona igual, pero exporta solo a CSV. Con esto, cada vez que
se aprieta Exportar los datos aparecen solos en la planilla.

1. Crear (o abrir) la planilla de Google donde quieres los datos.
2. En la planilla: menú **Extensiones → Apps Script**. Se abre el editor.
3. Borrar el contenido de `Código.gs` y pegar todo [apps_script.gs](apps_script.gs).
4. En la línea `const TOKEN = 'CAMBIA-ESTE-TOKEN';` poner una clave inventada
   (cualquier texto, ej. `conteo-puq-2026`). Guardar con el disquete.
5. Comprobar que escribe: en el selector de funciones elegir **`probar`** y
   apretar **Ejecutar**. La primera vez Google pide autorizar — hay que aceptar
   (aparece "Google no verificó esta aplicación" → *Configuración avanzada* →
   *Ir a … (no seguro)*; es tu propio script). Debe aparecer una fila `PRUEBA`
   en una hoja nueva llamada `conteo`. Bórrala a mano después.
6. Botón azul **Implementar → Nueva implementación**. En el engranaje elegir
   tipo **Aplicación web**, y configurar:
   - *Ejecutar como:* **Yo**
   - *Quién tiene acceso:* **Cualquier usuario**
     (necesario para que el teléfono pueda escribir sin iniciar sesión; el TOKEN
     es lo que impide que un tercero con la URL escriba en tu planilla)
7. Copiar la **URL de la aplicación web**, la que termina en `/exec`.
8. En [almacenamiento.py](almacenamiento.py), en el bloque de configuración:
   - `_GAS_URL` = la URL del paso 7
   - `_GAS_TOKEN` = **exactamente** el mismo texto del paso 4

Para verificarlo: abrir la app, registrar un vehículo, apretar Exportar. El
diálogo debe decir cuántas filas nuevas se enviaron. El Resumen también indica
si la sincronización está activa o si está en modo solo-CSV.

> Si más adelante editas el script, hay que hacer **Implementar → Gestionar
> implementaciones → editar → Nueva versión**, o la URL seguirá sirviendo el
> código viejo.

## Ejecutar

```bash
pip install -r requirements.txt
python main.py
```

## Compilar el APK

> ### Tres reglas que no son opcionales
>
> Estas tres cosas costaron una tarde de depuración. Saltarse cualquiera produce
> un fallo que **no** se parece a su causa.
>
> **1. Compilar FUERA de OneDrive.** OneDrive bloquea archivos mientras Gradle
> escribe los miles de intermedios de `build/`, y la compilación muere con
> `java.nio.file.FileSystemException: ... está siendo utilizado por otro
> proceso`. Copia el fuente a algo como `C:\Users\<usuario>\builds\` y compila
> ahí. También conviene matar los demonios de Gradle entre compilaciones
> (`Get-Process java | Stop-Process -Force`), porque quedan vivos y bloquean.
>
> **2. La versión de Flet debe estar FIJA** (ver `requirements.txt`). Si dice
> `>=`, pip instala la última dentro del APK mientras el CLI genera el cliente
> Dart con otra versión. Las dos mitades no se entienden: la app arranca,
> Python **no lanza ningún error**, y la pantalla queda oscura para siempre.
> Este fue exactamente el bug de la primera versión.
>
> **3. Pasar siempre `--org cl.indata`.** Sin eso el paquete queda
> `com.flet.conteo_vehicular_app` en vez de `cl.indata.conteo_vehicular_app`, y
> al instalar aparece como una **app distinta** al lado de la anterior en vez
> de actualizarla. Muy fácil de no notar, y lleva a probar la app equivocada.

Requisitos (verificados con `flutter doctor`): Android SDK 36.1.0 OK. El aviso
de *Visual Studio not installed* solo afecta compilar para Windows escritorio,
**no** el APK. Ojo: `flet build` usa su **propio** Flutter (3.41.7), no el que
esté en el PATH del sistema.

En **PowerShell**, desde la copia fuera de OneDrive (una sola línea):

```powershell
flet build apk --product "Conteo Vehicular" --org cl.indata --android-adaptive-icon-background "#FFFFFF" --splash-color "#FFFFFF" --splash-dark-color "#FFFFFF"
```

El APK queda en `build/apk/Conteo Vehicular.apk`. La primera compilación se
demora bastante (baja dependencias de Gradle y Flutter); las siguientes son
mucho más rápidas.

Para instalarlo, copia el APK al teléfono y ábrelo — hay que permitir
"instalar apps de origen desconocido". Con el teléfono conectado por USB y
depuración activada también sirve `adb install "build/apk/Conteo Vehicular.apk"`.

### Sobre los parámetros

| Parámetro | Para qué |
|---|---|
| `--product` | Nombre que aparece bajo el icono en el teléfono |
| `--org` | Base del bundle id (queda `cl.indata.conteo_vehicular`) |
| `--android-adaptive-icon-background` | Color con que Android rellena el fondo del adaptive icon |
| `--splash-color` / `--splash-dark-color` | Fondo de la pantalla de carga, en modo claro y oscuro |

- El **icono** sale de `assets/icon.png` y el **splash** de `assets/splash.png`.
  Flet los toma por convención: no van como parámetro. Si no hubiera
  `splash.png`, Flet usaría el `icon.png` como splash.
- Los dos PNG tienen el fondo blanco horneado y sin canal alfa. Por eso los
  colores de splash van en blanco: para que no se vea el borde del cuadrado.
  Si alguna vez cambias esos colores, hay que regenerar las imágenes con fondo
  transparente.
- Ojo con `--org`: los guiones no son válidos en un identificador de paquete
  Java, así que `cl.in-data` haría fallar la compilación.
- **No** hay que definir `JAVA_HOME`: Flutter usa el JDK que trae Android Studio
  (`C:\Program Files\Android\Android Studio\jbr`). En este equipo `java` no está
  en el PATH y aun así el toolchain de Android da OK.

## Estado

- ✅ **Sincronización con Sheets configurada y probada** (27-07-2026) contra la
  planilla real: primer envío, reenvío sin duplicar, corrección de una anulación
  ya sincronizada, y rechazo de token incorrecto.
- ✅ **Icono de la app** listo en `assets/icon.png`: el logo de In-Data centrado
  sobre blanco, verificado con recorte circular a 96 y 48 px (los iconos de
  Android son de 48 **dp**, que en un teléfono de densidad 2–3× son 96–144 px
  reales).
- ✅ **Pantalla de carga** en `assets/splash.png`. Aquí el logo se ve completo:
  el splash no tiene la restricción cuadrada ni el recorte circular del icono.

## Pendiente

- **Confirmar en el teléfono que los CSV llegan a Descargas.** La app los intenta
  guardar en `/storage/emulated/0/Download/conteo_vehicular`, pero en Android 11+
  eso exige el permiso **"Acceso a todos los archivos"**, que se concede a mano
  una vez por teléfono (Ajustes → Aplicaciones → Conteo Vehicular → Permisos).
  El permiso ya va declarado en el manifest, pero el sistema no lo otorga solo.
  Si falla, la app cae a la carpeta interna, lo dice en pantalla y muestra la
  ruta de Ajustes. El diálogo **Resumen** indica siempre qué carpeta quedó en uso.
  La carpeta externa propia del app (`/Android/data/<paquete>/`) se verificó que
  **no** sirve: el directorio padre solo lo crea el sistema.
- **Probar el flujo completo en terreno.** La preferencia por la
  carpeta externa está implementada con verificación de escritura y fallback,
  pero no se pudo probar en un dispositivo: hay que compilar el APK, exportar
  una vez y confirmar que los CSV aparecen al conectar el teléfono por cable.
  El diálogo de Resumen muestra la carpeta que quedó elegida.
- Confirmar la lista de aeropuertos con los requisitos del estudio.
- El catálogo no tiene una opción "Otro": si en terreno aparece un vehículo que
  no calza en ninguno de los 18 tipos, hoy hay que usar el tipo más cercano y
  anotarlo en el campo de observación.

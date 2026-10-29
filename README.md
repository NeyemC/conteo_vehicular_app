# conteo_vehicular_app

Aplicación destinada al conteo vehicular en un aeropuerto, para un estudio sobre
el estado del pavimento. El encuestador registra cada vehículo con **un toque**
en una grilla de botones, uno por combinación de tipo y grupo de ejes, y la app
guarda el detalle con su hora y lo sincroniza con una planilla de Google.

Comparte arquitectura con `timer_aeropuerto_app` (Python + Flet, compilable a
APK Android).

## Estructura

| Archivo | Rol |
|---|---|
| `modelos.py` | Clases `SesionConteo` y `Vehiculo`, catálogo de tipos, grupos de ejes y posiciones |
| `almacenamiento.py` | Persistencia JSON, exportación a CSV y sincronización opcional con Google Sheets |
| `tema.py` | Paleta del modo oscuro, medidas de la grilla y utilidades de contraste |
| `main.py` | Interfaz Flet: pantalla inicial, grilla de conteo, resumen y cierre |
| `apps_script.gs` | Script que va pegado en la planilla de Google (no se ejecuta acá) |
| `config_sheets.ejemplo.py` | Plantilla de `config_sheets.py` (URL y token, fuera del repo) |
| `build_apk.sh` | Compila el APK firmado en Linux desde el commit actual |
| `compilar.ps1` | Lo mismo, en Windows |
| `pruebas/` | Pruebas de la lógica, sin interfaz |
| `assets/icon.png` | Icono de la app, 1024×1024. Flet lo toma de aquí por convención |
| `assets/splash.png` | Pantalla de carga, 1152×1152. Idem: por convención |
| `IN-DATA.png` | Logo original de la marca, fuente del icono. No se empaqueta en el APK |

## Clasificación de vehículos

La grilla tiene dos bloques, uno por **grupo de ejes**, y en cada uno un botón
por **tipo**:

| Vehículo de 2 ejes | Vehículo de 3 o más ejes |
|---|---|
| Auto/furgón | Camión |
| Bus | Bus |
| Camión | Trolley |
| Moto | |
| Trolley | |

El catálogo se define en un solo lugar, `TIPOS_VEHICULO` y `GRUPOS_EJES` en
`modelos.py`. Agregar o mover un tipo es editar esas tablas (y su icono en
`ICONO_TIPO`, en `main.py`); la grilla y los CSV se ajustan solos.

### Posiciones y sentido

Hay 5 posiciones de conteo. En la mayoría hay un solo flujo y el sentido no se
registra. En las **posiciones de dos sentidos** se cuentan los dos por
separado: la grilla aparece dos veces, una para **Izquierda** y otra para
**Derecha**, cada una con su total. Cuáles son depende del aeropuerto:

| Aeropuerto | Posiciones de dos sentidos |
|---|---|
| CJC - Calama | 4 y 5 |
| Todos los demás | 5 |

Se define en `POSICIONES_DOS_SENTIDOS` en `modelos.py`, y la nota de la
pantalla inicial se ajusta al aeropuerto elegido. Como dos grillas no caben en
pantalla con las medidas normales, esas posiciones usan una versión compacta
(ver `MEDIDAS` en `tema.py`).

Aeropuertos: ANF Antofagasta, ARI Arica, BBA Balmaceda, CJC Calama,
CPO Copiapó, LSC La Serena y PUQ Punta Arenas (`AEROPUERTOS` en `modelos.py`).

## Flujo de uso

1. **Inicio:** aeropuerto, nombre del encuestador y posición — o continuar una
   sesión anterior.
2. **Conteo:** cada toque en un botón registra un vehículo, y el número del
   botón sube. Un aviso breve confirma el registro sin bloquear el siguiente
   toque. Arriba se ve el total; el icono ⓘ abre el **Resumen**.
3. **Deshacer último registro:** anula el último vehículo vigente. Se puede
   repetir para ir anulando hacia atrás.
4. **Finalizar conteo y guardar:** pide confirmación, escribe los CSV, envía la
   sesión a la planilla (con un indicador de "Enviando…" mientras dura) y
   vuelve a la pantalla inicial.

## Trabajo sin internet

La sincronización **no envía un incremental: manda la sesión completa cada vez**,
y el Apps Script hace *upsert* por la llave `sesion_id` + `veh_id`. De ahí salen
dos propiedades que importan en terreno:

- **Enviar sin señal no pierde nada.** Los CSV se escriben igual, y el siguiente
  envío con red sube todo lo acumulado de una vez.
- **Reenviar nunca duplica.** Las filas ya enviadas se actualizan, no se
  repiten.

Si al finalizar no hay señal, el aviso lo dice en palabras simples ("Sin
conexión a internet, o la señal es muy débil") y la sesión queda **pendiente**.
Desde la 1.2.1:

- **Cada sesión de "continuar" muestra si ya está en la planilla**: "En la
  planilla" (verde) o "Falta subir a la planilla" (naranjo). Se calcula
  comparando la huella guardada en `sesion_<ID>.subida` con lo que hay hoy en
  el teléfono, así que si después de subir se registra o anula algo, vuelve a
  quedar pendiente.
- **Las pendientes se muestran siempre**, aunque no estén entre las 8 más
  recientes.
- **Al abrir la app, las pendientes se suben solas** en segundo plano. Si no
  hay señal se deja de intentar hasta la próxima apertura; también se puede
  abrir la sesión y finalizarla de nuevo.
- **Las sesiones creadas antes de la 1.2.1 no muestran estado** ni se suben
  solas: no tienen marca, y pudieron borrarse de la planilla a propósito
  (sesiones de prueba). Si hace falta reenviar una, se abre y se finaliza.

Además, cada registro se guarda en el JSON y en el CSV de detalle **en el
momento**, sin esperar a finalizar. Si un guardado falla (disco lleno, por
ejemplo) el conteo sigue, la pantalla lo avisa en rojo, y el siguiente guardado
exitoso incluye lo que faltaba.

### Reanudar una sesión

Si Android mata la app en segundo plano —los Samsung lo hacen seguido— la
pantalla inicial ofrece **continuar la sesión anterior**, con su posición,
hora, cantidad de vehículos y si ya está en la planilla. Es también la forma
de reintentar a mano el envío de una sesión que se finalizó sin señal: se abre
y se vuelve a finalizar.

Se listan las 8 más recientes con al menos un registro (aunque esté anulado:
una sesión con todo anulado igual puede tener filas en la planilla que hay que
corregir), ordenadas por la hora del último registro. Al reanudar, el
correlativo sigue donde iba. Una sesión iniciada sin ningún toque no se guarda.

## Modo oscuro

La app es oscura por defecto. Los fondos grandes van en **negro real**
(`#000000`): en la pantalla AMOLED del teléfono esos píxeles están apagados y no
consumen batería, y de noche no encandila.

La paleta vive completa en [tema.py](tema.py), no repartida por la interfaz.
**El contraste está medido, no supuesto**: `tema.py` incluye el cálculo de razón
de contraste WCAG y `pruebas/test_app.py` verifica cada par texto/fondo. Los
valores actuales van de **5,5:1 a 18,8:1**, sobre el mínimo de 4,5:1 de WCAG AA.
Si se cambia un color y baja del umbral, la prueba falla.

Dos consecuencias del modo oscuro que no son obvias:

- **Los acentos son claros, no oscuros.** Un índigo oscuro desaparece sobre
  negro. Donde un botón o aviso tiene fondo de acento claro, el texto pasa a
  tinta oscura — al revés que en modo claro.
- **El encabezado no va en color de acento.** Una franja brillante arriba
  encandila y, siendo grande y encendida, gasta batería.

El **splash** también es negro, con el logo recoloreado: el gris original daba
solo 2,90:1 sobre negro y el rojo 3,20:1, ambos insuficientes. El **icono** se
mantiene sobre blanco, porque es un área diminuta y ahí prima la marca.

## Criterios de diseño

- **Un toque, un vehículo.** En terreno pasan varios vehículos por segundo: no
  hay diálogos al registrar, y la confirmación es un aviso que desaparece solo.
- El **grupo de ejes** es el dato que interesa para estimar solicitaciones sobre
  el pavimento, por eso es el primer nivel de la grilla y no un atributo del
  tipo: un bus o un camión aparece en los dos bloques.
- El **color distingue el grupo de ejes**, no el tipo: es lo que hay que
  separar de un vistazo al tocar rápido. La distinción fina la hacen el icono y
  la etiqueta.
- Se guarda el **timestamp absoluto** de cada registro. La app no agrupa por
  tramos horarios, pero cualquier agregación temporal (flujo por hora, por
  tramos de 15 minutos) se puede calcular después sobre la columna `timestamp`
  del CSV de detalle.
- Los errores se **anulan**, no se borran: quedan marcados en el CSV de detalle
  y en la planilla, y dejan de sumar en los conteos.
- La sincronización con Sheets usa `urllib` de la stdlib contra un Google Apps
  Script, para no depender de librerías nativas en Android. Corre en un hilo
  aparte, para que una red lenta no congele la app.
- Lo que se sincroniza es el **detalle**, no el resumen: cada fila tiene una
  llave única, así que el script hace *upsert* y **volver a enviar es inocuo**.
  Una anulación posterior corrige la fila ya enviada en vez de dejar un dato
  viejo. El resumen se reconstruye en la planilla con una tabla dinámica.
- La llave es **`sesion_id` + `veh_id`**, no `veh_id` solo. El `veh_id` tiene 6
  caracteres para que sea legible, y es único dentro de su sesión; pero en una
  planilla con miles de filas de muchas sesiones dos vehículos distintos
  chocarían, y el segundo pisaría al primero sin aviso (con 5.000 filas, ~50% de
  probabilidad).
- Las columnas llave se guardan en la planilla **como texto**. Si no, Sheets
  convierte un id como `012345` en el número 12345, deja de coincidir, y esa
  fila se duplica en cada reenvío.
- **Si cambian las columnas**, el script archiva la hoja anterior como
  `conteo_antigua` y crea una nueva con los encabezados correctos, avisándolo en
  el diálogo final. Escribir bajo encabezados que no corresponden desalinearía
  todas las filas nuevas en silencio, y borrar la hoja perdería lo anterior.
  Esto pasó al reemplazar el catálogo de vehículos. En cambio, **agregar
  columnas a mano a la derecha** (fórmulas, notas) es seguro: no archiva nada y
  la app no las toca.
- Si la sincronización falla (sin señal), los CSV locales se escriben igual y la
  app lo dice: se puede reintentar más tarde sin miedo a duplicar.

## Dónde quedan los datos

Todo va a una sola carpeta, que la app muestra en el diálogo de Resumen:

- **Windows / Mac / Linux:** `~/conteo_vehicular`
- **Android:** `/storage/emulated/0/Download/conteo_vehicular` (Descargas), que
  se alcanza conectando el teléfono por cable. Si el sistema no deja escribir
  ahí, la app prueba Documentos y por último la carpeta interna del app — esa
  última **no** se puede alcanzar desde afuera, y en ese caso la app lo advierte
  al finalizar y la planilla pasa a ser la única vía para recuperar los datos.

Cada carpeta candidata se prueba con una escritura real, no solo con
`os.access()`. La carpeta externa propia del app (`/Android/data/<paquete>/`)
está en la lista pero en la práctica falla: el directorio padre solo lo crea el
sistema.

Cuatro archivos por sesión:

| Archivo | Cuándo se escribe |
|---|---|
| `sesion_<ID>.json` | Tras **cada** registro. Es lo que permite reanudar la sesión. |
| `conteo_<AERO>_pos<N>_<fecha>_<ID>_detalle.csv` | Tras **cada** registro. Un registro por vehículo, incluidos los anulados. |
| `conteo_<AERO>_pos<N>_<fecha>_<ID>_resumen.csv` | Al finalizar. Conteos vigentes por sentido × grupo de ejes × tipo. |
| `sesion_<ID>.subida` | Con el primer registro (vacío) y tras cada envío exitoso: la huella de lo que llegó a la planilla. Ver "Trabajo sin internet". |

Los dos que se reescriben en cada registro se escriben primero en un temporal y
después se reemplazan, así que un cierre a media escritura nunca deja un archivo
truncado. Los CSV van en UTF-8 con BOM, así que Excel los abre con los acentos
correctos de un doble clic.

Columnas del detalle: `sesion_id, fecha, aeropuerto, posicion, encuestador,
veh_id, numero, grupo_ejes, tipo, sentido, hora, timestamp, nota, anulado`.

Para respaldar todo desde un computador con el teléfono conectado:

```bash
adb pull /storage/emulated/0/Download/conteo_vehicular ./respaldo
```

## Configurar la planilla de Google

Sin esto la app funciona igual, pero exporta solo a CSV. Con esto, cada vez que
se finaliza un conteo los datos aparecen solos en la planilla.

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
8. Copiar `config_sheets.ejemplo.py` como **`config_sheets.py`** y poner ahí:
   - `GAS_URL` = la URL del paso 7
   - `GAS_TOKEN` = **exactamente** el mismo texto del paso 4

   Ese archivo está en `.gitignore` porque el repositorio es público: con la URL
   y el token cualquiera podría escribir en la planilla. Por eso `apps_script.gs`
   tampoco lleva el token real — se pone solo en el editor de Apps Script.
   `compilar.ps1` copia `config_sheets.py` junto a los demás módulos, y se niega
   a compilar si no está.

Para verificarlo: abrir la app, registrar un vehículo y finalizar. El diálogo
final debe decir cuántas filas nuevas se enviaron. El Resumen también indica si
la sincronización está activa o si está en modo solo-CSV.

> ### Si se edita el script después
> Pegar el código nuevo **conservando el TOKEN real**, guardar, y hacer
> **Implementar → Gestionar implementaciones → editar (lápiz) → Versión: Nueva
> versión → Implementar**. La URL no cambia, pero si se omite este paso la app
> sigue hablando con el código viejo.

> ### Actualizarlo desde la terminal, con clasp
> El script está vinculado a la planilla, así que no aparece en Drive ni en
> `clasp list`: su ID está en el editor, en ⚙ *Configuración del proyecto*.
> En este PC ya hay un clon con el ID en
> `~/In-data/conteo_vehicular_apps_script_respaldo/trabajo/.clasp.json`.
> Para publicar un cambio: copiar `apps_script.gs` como `Código.js` en esa
> carpeta **reemplazando el TOKEN por el real**, y luego
> `clasp push --force` y `clasp deploy -i <id de la implementación> -d "..."`.
> El id de la implementación es el que va en la URL `/macros/s/<id>/exec` de
> `config_sheets.py`; con `-i` la URL no cambia. Hay otras dos
> implementaciones (`@HEAD` y `@2`) que la app no usa.

> ### Orden al actualizar: primero el script, después el APK
> Desde la versión 1.1.0 la app manda la llave como `["sesion_id", "veh_id"]`.
> El script nuevo acepta tanto eso como el `"veh_id"` de los APK anteriores,
> pero el script viejo **rechaza** la llave nueva ("no encuentro la columna
> llave"). Por eso hay que implementar el script nuevo antes de instalar el APK
> nuevo; los teléfonos que sigan con el APK viejo siguen funcionando.
>
> Las filas que ya estaban en la planilla se reconocen con la llave nueva sin
> hacer nada, porque `sesion_id` siempre se envió. La única excepción son las
> que Sheets ya había convertido a número (ids de solo dígitos con un cero
> adelante, ~0,6% de los registros): si se reenvía esa sesión antigua, esas
> filas aparecen una vez más.

## Ejecutar

```bash
pip install -r requirements.txt
python main.py
```

## Pruebas

```bash
python -m unittest discover pruebas
```

Cubren el modelo, el guardado atómico, los CSV, lo que se envía a la planilla,
la elección de carpeta en Android y el contraste de la paleta. No necesitan Flet
ni red, y no se empaquetan en el APK.

## Compilar el APK

> ### Cuatro reglas que no son opcionales
>
> Estas cosas costaron una tarde de depuración. Saltarse cualquiera produce
> un fallo que **no** se parece a su causa. `build_apk.sh` y `compilar.ps1` se
> encargan de todas: son la forma recomendada de compilar.
>
> **1. Compilar FUERA de OneDrive.** OneDrive bloquea archivos mientras Gradle
> escribe los miles de intermedios de `build/`, y la compilación muere con
> `java.nio.file.FileSystemException: ... está siendo utilizado por otro
> proceso`. El script copia el fuente a `%USERPROFILE%\builds\conteo_vehicular_app`
> y compila ahí, y antes cierra los demonios de Gradle que quedaron vivos de
> compilaciones anteriores (solo esos, no todos los `java` del equipo).
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
>
> **4. Firmar siempre con la clave de la app.** Android solo instala una versión
> encima de otra si las dos llevan la misma firma. Sin clave propia, Flet firma
> con la clave *debug* del PC que compila, que es distinta en cada PC: hasta la
> 1.0.0 la app iba firmada con la del PC con Windows, y para pasar a la clave
> propia (1.1.0) hubo que desinstalar una vez. Los dos scripts se niegan a
> compilar sin la clave.

### La clave de firma

Vive **fuera del repo**, en `~/In-data/conteo_vehicular_firma/` del equipo
Linux donde se creó (28-10-2026): `conteo_vehicular_release.jks` (alias
`upload`) y `password.txt`. Hay que respaldar los dos fuera de ese PC. **Si se
pierden, la siguiente versión no se podrá instalar encima**: habrá que
desinstalar en cada teléfono, y la app deja de ver sus archivos anteriores en
Descargas. Para compilar en Windows, copiarlos a
`%USERPROFILE%\conteo_vehicular_firma\`.

### En Linux

```bash
./build_apk.sh
```

Exige que no haya cambios sin commitear, así cada APK corresponde a un commit
exacto. Compila desde una copia limpia en `../conteo_vehicular_build/` y deja
el APK como `conteo_vehicular_v<versión>_<commit>.apk`. Usa el Flet 0.85.3 de
`~/.venvs/timer_aeropuerto` (otro se indica con `FLET=...`); el JDK y el SDK de
Android los instala Flet solo la primera vez.

### En Windows

Requisitos (verificados con `flutter doctor`): Android SDK 36.1.0 OK. El aviso
de *Visual Studio not installed* solo afecta compilar para Windows escritorio,
**no** el APK. Ojo: `flet build` usa su **propio** Flutter (3.41.7), no el que
esté en el PATH del sistema.

En **PowerShell**, desde la carpeta del repo, con la clave ya copiada:

```powershell
.\compilar.ps1
```

Al terminar imprime la ruta del APK. Lo que ejecutan los dos scripts por
dentro, desde la copia limpia, es:

```
flet build apk --org cl.indata --product "Conteo Vehicular" --build-version 1.2.1 --build-number <aaMMddHH> --android-permissions android.permission.MANAGE_EXTERNAL_STORAGE=true --android-adaptive-icon-background "#FFFFFF" --splash-color "#000000" --splash-dark-color "#000000" --android-signing-key-store <jks> --android-signing-key-alias upload
```

con las contraseñas en `FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD` y
`FLET_ANDROID_SIGNING_KEY_PASSWORD`.

La primera compilación se demora bastante (baja dependencias de Gradle y
Flutter); las siguientes son mucho más rápidas.

Para instalarlo, copia el APK al teléfono y ábrelo — hay que permitir
"instalar apps de origen desconocido". Con el teléfono conectado por USB y
depuración activada también sirve `adb install -r "<ruta del APK>"`.

### Sobre los parámetros

| Parámetro | Para qué |
|---|---|
| `--org` | Base del bundle id (queda `cl.indata.conteo_vehicular_app`) |
| `--product` | Nombre que aparece bajo el icono en el teléfono |
| `--build-version` | Versión visible (`versionName`). Subirla a mano en los dos scripts con cada cambio relevante |
| `--build-number` | `versionCode`. El script pone la fecha y hora de compilación (`aaMMddHH`) |
| `--android-permissions` | Declara "Acceso a todos los archivos" en el manifest (ver Pendiente) |
| `--android-signing-key-store` / `-alias` | La clave de firma (ver arriba) |
| `--android-adaptive-icon-background` | Color con que Android rellena el fondo del adaptive icon |
| `--splash-color` / `--splash-dark-color` | Fondo de la pantalla de carga, en modo claro y oscuro |

- El **icono** sale de `assets/icon.png` y el **splash** de `assets/splash.png`.
  Flet los toma por convención: no van como parámetro.
- Los dos PNG no tienen canal alfa. El icono tiene el **fondo blanco** horneado,
  por eso el fondo del adaptive icon va en blanco. El splash tiene el **fondo
  negro** horneado, por eso los colores de splash van en negro: así no se ve el
  borde del cuadrado. Si se cambia alguno de esos colores, hay que regenerar la
  imagen correspondiente.
- Ojo con `--org`: los guiones no son válidos en un identificador de paquete
  Java, así que `cl.in-data` haría fallar la compilación.
- **No** hay que definir `JAVA_HOME`: Flutter usa el JDK que trae Android Studio
  (`C:\Program Files\Android\Android Studio\jbr`). En este equipo `java` no está
  en el PATH y aun así el toolchain de Android da OK.

### Qué versión tiene el teléfono

```bash
adb shell dumpsys package cl.indata.conteo_vehicular_app | grep -E "versionName|versionCode|lastUpdateTime"
```

El `versionCode` es la fecha y hora de la compilación. Los APK anteriores a la
1.1.0 dicen todos `1` / `1.0.0`; para identificar uno de esos hay que sacar el
APK (`adb shell pm path …` y `adb pull`) y comparar los `.py` que trae en
`assets/flutter_assets/app/app.zip` con el repo.

## Estado

- ✅ **Sincronización con Sheets configurada y probada** (27-07-2026) contra la
  planilla real: primer envío, reenvío sin duplicar, corrección de una anulación
  ya sincronizada, y rechazo de token incorrecto.
- ✅ **Script 1.1.0 implementado** (28-10-2026, versión 3 de la implementación
  que usa la app). Probado contra la planilla real: rechaza un token malo, acepta
  la llave nueva y la antigua, y reenviar una sesión ya sincronizada actualizó
  sus 10 filas sin agregar ninguna. Antes se respaldó el código anterior y se
  hizo una copia de la planilla en Drive.
- ✅ **Sesiones pendientes (1.2.1) probadas en el teléfono** (29-10-2026): con
  modo avión, finalizar mostró "Sin conexión a internet…" y la tarjeta quedó en
  "Falta subir a la planilla"; al quitar el modo avión y reabrir la app, la
  sesión se subió sola y pasó a "En la planilla". Las filas de prueba se
  borraron después (la planilla volvió a 15.701 filas).
- ✅ **Los CSV llegan a Descargas** (verificado el 28-10-2026 en un Samsung
  SM-A176B): `Download/conteo_vehicular` tenía las sesiones de julio y agosto.
  Funcionó **sin** conceder "Acceso a todos los archivos": desde Android 11 una
  app puede crear sus propios archivos en Descargas sin ese permiso.
- ✅ **La hora se registra en hora local** (America/Santiago), verificado contra
  la hora de modificación de los archivos en el teléfono.
- ✅ **Icono de la app** listo en `assets/icon.png`: el logo de In-Data centrado
  sobre blanco, verificado con recorte circular a 96 y 48 px (los iconos de
  Android son de 48 **dp**, que en un teléfono de densidad 2–3× son 96–144 px
  reales).
- ✅ **Pantalla de carga** en `assets/splash.png`. Aquí el logo se ve completo:
  el splash no tiene la restricción cuadrada ni el recorte circular del icono.

## Pendiente

- **Desinstalar pierde el acceso a los CSV viejos.** Android asocia cada
  archivo de Descargas a la instalación que lo creó; actualizar (`adb install
  -r`, o abrir el APK nuevo encima) lo conserva, desinstalar no. Pasó una vez,
  al cambiar a la clave de firma propia (28-10-2026): las sesiones anteriores
  quedaron respaldadas en `~/In-data/respaldo_conteo_vehicular_2026-10-28/` y
  siguen en Descargas, pero la app ya no las lista en "continuar". Para que las
  vuelva a ver habría que conceder "Acceso a todos los archivos" (Ajustes →
  Aplicaciones → Conteo Vehicular → Permisos), que va declarado en el manifest
  pero se concede a mano.
- **Probar el flujo completo en terreno** con el APK 1.2.1.
- Confirmar la lista de aeropuertos con los requisitos del estudio.
- El catálogo no tiene una opción "Otro": si en terreno aparece un vehículo que
  no calza en ninguno de los tipos, hoy hay que usar el más cercano.
- `MANAGE_EXTERNAL_STORAGE` está bien para instalar el APK a mano, pero Google
  Play lo rechazaría sin justificación si algún día se publica ahí.

/**
 * Webhook de Google Apps Script para la app de Conteo Vehicular Aeroportuario.
 *
 * Recibe el detalle de una sesión y lo escribe en la planilla haciendo UPSERT
 * por la llave (sesion_id + veh_id): las filas nuevas se agregan y las que ya
 * estaban se actualizan. Por eso volver a exportar es inocuo — no duplica — y
 * una anulación hecha después de una exportación anterior corrige la fila ya
 * enviada.
 *
 * INSTALACIÓN: ver el README (sección "Configurar la planilla de Google").
 * Recuerda que TOKEN debe ser idéntico a GAS_TOKEN en config_sheets.py.
 */

// Poner acá el mismo texto que GAS_TOKEN en config_sheets.py.
// Este archivo SÍ va al repositorio (que es público), así que el token real no
// se escribe aquí: se pone en el editor de Apps Script de la planilla.
const TOKEN = 'CAMBIA-ESTE-TOKEN';
const HOJA = 'conteo';

// Columnas que se guardan como TEXTO. Sin esto Sheets interpreta lo que llega
// como si se tipeara a mano: el id "012345" queda como el número 12345, ya no
// coincide al reexportar, y la fila se duplica en cada exportación.
const COLUMNAS_TEXTO = ['sesion_id', 'veh_id'];


function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return respuesta({error: 'sin cuerpo en la solicitud'});
    }

    const cuerpo = JSON.parse(e.postData.contents);

    if (cuerpo.token !== TOKEN) {
      return respuesta({error: 'token invalido'});
    }

    const columnas = cuerpo.columnas || [];
    const filas = cuerpo.filas || [];

    // La app nueva manda una lista de columnas llave; las versiones anteriores
    // mandan solo 'veh_id'. Se aceptan las dos para que un teléfono sin
    // actualizar siga pudiendo exportar.
    const nombresClave = Array.isArray(cuerpo.clave) ? cuerpo.clave : [cuerpo.clave];
    const iClaves = nombresClave.map(function (c) { return columnas.indexOf(c); });
    if (!iClaves.length || iClaves.indexOf(-1) >= 0) {
      return respuesta({error: 'no encuentro la columna llave: ' + nombresClave});
    }
    function llaveDe(fila) {
      return iClaves.map(function (i) { return normalizar(fila[i]); }).join('|');
    }
    if (!filas.length) {
      return respuesta({nuevas: 0, actualizadas: 0, total: 0});
    }

    // Sin lock, dos teléfonos exportando a la vez pueden pisarse.
    const lock = LockService.getScriptLock();
    lock.waitLock(30000);
    try {
      const avisos = [];
      const hoja = obtenerHoja(columnas, avisos);

      // Se lee TODO el bloque de datos una vez y se modifica en memoria.
      //
      // Antes se hacía un setValues por cada fila actualizada, y en Apps Script
      // eso es carísimo: reexportar 800 registros eran 800 llamadas, decenas de
      // segundos con el lock tomado. Con el lock retenido tanto rato, un segundo
      // teléfono exportando a la vez se topaba con el límite de 30 s del
      // waitLock y fallaba, y encima se acercaba al tope de 6 minutos de
      // ejecución de Apps Script.
      const ancho = columnas.length;
      const ultima = hoja.getLastRow();
      var datos = [];
      if (ultima > 1) {
        datos = hoja.getRange(2, 1, ultima - 1, ancho).getValues();
      }

      // llave -> posición en `datos`, guardada +1 para que el índice 0 no se
      // confunda con "no está".
      const indice = {};
      for (var i = 0; i < datos.length; i++) {
        indice[llaveDe(datos[i])] = i + 1;
      }

      const base = datos.length;          // filas que ya estaban en la hoja
      const cambiadas = [];
      for (var j = 0; j < filas.length; j++) {
        const fila = filas[j];
        const llave = llaveDe(fila);
        const encontrado = indice[llave];
        if (encontrado) {
          datos[encontrado - 1] = fila;
          if (encontrado - 1 < base) { cambiadas.push(encontrado - 1); }
        } else {
          datos.push(fila);
          indice[llave] = datos.length;   // por si la llave se repite en el envío
        }
      }
      const nuevas = datos.length - base;

      // Una hoja nueva trae 1000 filas, y getRange no puede pasar de ahí: sin
      // agrandarla, la exportación que cruza la fila 1000 falla.
      const necesarias = 1 + datos.length;
      if (necesarias > hoja.getMaxRows()) {
        hoja.insertRowsAfter(hoja.getMaxRows(), necesarias - hoja.getMaxRows());
      }
      formatearTexto(hoja, columnas);

      // Las actualizaciones se escriben por tramos de filas CONTIGUAS. Un solo
      // tramo de la primera a la última reescribiría también las filas de otros
      // teléfonos que quedaron intercaladas (convirtiendo en valor cualquier
      // fórmula que tuvieran); filas sueltas serían una llamada por fila.
      // Una sesión suele estar en uno o pocos tramos.
      escribirTramos(hoja, datos, cambiadas, ancho);
      if (nuevas) {
        hoja.getRange(2 + base, 1, nuevas, ancho).setValues(datos.slice(base));
      }

      return respuesta({
        nuevas: nuevas,
        actualizadas: cambiadas.length,
        total: datos.length,
        aviso: avisos.join(' ')
      });
    } finally {
      lock.releaseLock();
    }
  } catch (err) {
    return respuesta({error: String(err)});
  }
}


/**
 * Texto comparable de una celda llave. Las filas escritas antes de existir
 * COLUMNAS_TEXTO pueden haber quedado como número ("123456" → 123456); String()
 * las devuelve iguales siempre que no tuvieran un cero inicial.
 */
function normalizar(x) {
  return String(x).trim();
}


function formatearTexto(hoja, columnas) {
  const filas = hoja.getMaxRows() - 1;
  if (filas < 1) { return; }
  COLUMNAS_TEXTO.forEach(function (c) {
    const i = columnas.indexOf(c);
    if (i >= 0) {
      hoja.getRange(2, i + 1, filas, 1).setNumberFormat('@');
    }
  });
}


function escribirTramos(hoja, datos, indices, ancho) {
  if (!indices.length) { return; }
  indices.sort(function (a, b) { return a - b; });
  var desde = indices[0], previo = indices[0];
  for (var n = 1; n <= indices.length; n++) {
    const k = indices[n];
    if (n < indices.length && k === previo) { continue; }   // repetida
    if (n < indices.length && k === previo + 1) {
      previo = k;
      continue;
    }
    hoja.getRange(2 + desde, 1, previo - desde + 1, ancho)
        .setValues(datos.slice(desde, previo + 1));
    desde = previo = k;
  }
}


/**
 * Devuelve la hoja de destino con los encabezados correctos.
 *
 * Si la hoja existe pero sus encabezados NO coinciden con las columnas que manda
 * la app (pasa cuando cambia el modelo de datos), la hoja vieja se ARCHIVA con
 * otro nombre y se crea una nueva. Escribir igual desalinearía todas las filas
 * nuevas en silencio, y borrarla perdería los datos anteriores.
 *
 * Solo se comparan las primeras columnas, tantas como manda la app: una columna
 * agregada a mano a la derecha (una fórmula, una nota) no debe archivar la hoja.
 * La app solo escribe esas primeras columnas, así que las de más se conservan.
 *
 * `avisos` es un arreglo donde se deja constancia, para que la app lo muestre.
 */
function obtenerHoja(columnas, avisos) {
  const libro = SpreadsheetApp.getActiveSpreadsheet();
  var hoja = libro.getSheetByName(HOJA);

  if (hoja && hoja.getLastRow() > 0) {
    const ancho = Math.max(columnas.length, 1);
    const actuales = hoja.getRange(1, 1, 1, ancho)
                         .getValues()[0]
                         .map(function (x) { return String(x).trim(); });
    if (actuales.join('|') !== columnas.join('|')) {
      var nombreArchivo = HOJA + '_antigua';
      var n = 2;
      while (libro.getSheetByName(nombreArchivo)) {
        nombreArchivo = HOJA + '_antigua_' + n;
        n++;
      }
      hoja.setName(nombreArchivo);
      avisos.push('Las columnas cambiaron: la hoja anterior se archivó como "' +
                  nombreArchivo + '" y se creó una nueva "' + HOJA + '".');
      hoja = null;   // se crea limpia más abajo
    }
  }

  if (!hoja) {
    hoja = libro.getSheetByName(HOJA) || libro.insertSheet(HOJA);
  }
  if (hoja.getLastRow() === 0) {
    hoja.getRange(1, 1, 1, columnas.length).setValues([columnas]);
    hoja.getRange(1, 1, 1, columnas.length).setFontWeight('bold');
    hoja.setFrozenRows(1);
  }
  return hoja;
}


function respuesta(obj) {
  return ContentService
      .createTextOutput(JSON.stringify(obj))
      .setMimeType(ContentService.MimeType.JSON);
}


/**
 * Ejecuta esto una vez desde el editor (menú Ejecutar) para comprobar que el
 * script escribe en la planilla, sin necesidad del teléfono. Debe aparecer una
 * fila de prueba en la hoja "conteo"; bórrala después a mano.
 */
function probar() {
  const columnas = ['sesion_id', 'fecha', 'aeropuerto', 'posicion',
                    'encuestador', 'veh_id', 'numero', 'grupo_ejes', 'tipo',
                    'sentido', 'hora', 'timestamp', 'nota', 'anulado'];
  const fila = ['PRUEBA', '2026-07-29', 'ANF - Antofagasta', '5',
                'Prueba', 'TEST01', '1', '2 ejes', 'Auto/furgón',
                'Izquierda', '10:00:00',
                '2026-07-29T10:00:00', 'fila de prueba', 'No'];
  const salida = doPost({postData: {contents: JSON.stringify({
    token: TOKEN, clave: ['sesion_id', 'veh_id'], columnas: columnas,
    filas: [fila]
  })}});
  Logger.log(salida.getContent());
}

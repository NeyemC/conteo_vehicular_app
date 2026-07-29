/**
 * Webhook de Google Apps Script para la app de Conteo Vehicular Aeroportuario.
 *
 * Recibe el detalle de una sesión y lo escribe en la planilla haciendo UPSERT
 * por veh_id: las filas nuevas se agregan y las que ya estaban se actualizan.
 * Por eso volver a exportar es inocuo — no duplica — y una anulación hecha
 * después de una exportación anterior corrige la fila ya enviada.
 *
 * INSTALACIÓN: ver el README (sección "Configurar la planilla de Google").
 * Recuerda que TOKEN debe ser idéntico a _GAS_TOKEN en almacenamiento.py.
 */

// Poner acá el mismo texto que GAS_TOKEN en config_sheets.py.
// Este archivo SÍ va al repositorio (que es público), así que el token real no
// se escribe aquí: se pone en el editor de Apps Script de la planilla.
const TOKEN = 'CAMBIA-ESTE-TOKEN';
const HOJA = 'conteo';


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
    const iClave = columnas.indexOf(cuerpo.clave);
    if (iClave < 0) {
      return respuesta({error: 'no encuentro la columna llave: ' + cuerpo.clave});
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

      // Se lee TODO el bloque de datos una vez, se modifica en memoria y se
      // escribe de vuelta en una sola llamada.
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
        indice[String(datos[i][iClave])] = i + 1;
      }

      const nuevas = [];
      var actualizadas = 0;
      var desde = -1, hasta = -1;
      for (var j = 0; j < filas.length; j++) {
        const fila = filas[j];
        const llave = String(fila[iClave]);
        const encontrado = indice[llave];
        if (encontrado) {
          const k = encontrado - 1;
          datos[k] = fila;
          actualizadas++;
          if (desde < 0 || k < desde) { desde = k; }
          if (k > hasta) { hasta = k; }
        } else {
          nuevas.push(fila);
        }
      }

      // Una sola escritura para todas las actualizaciones: solo el tramo que
      // realmente cambió, para no reescribir filas de sesiones anteriores.
      if (actualizadas > 0) {
        hoja.getRange(2 + desde, 1, hasta - desde + 1, ancho)
            .setValues(datos.slice(desde, hasta + 1));
      }
      if (nuevas.length) {
        hoja.getRange(2 + datos.length, 1, nuevas.length, ancho)
            .setValues(nuevas);
      }

      return respuesta({
        nuevas: nuevas.length,
        actualizadas: actualizadas,
        total: datos.length + nuevas.length,
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
 * Devuelve la hoja de destino con los encabezados correctos.
 *
 * Si la hoja existe pero sus encabezados NO coinciden con las columnas que manda
 * la app (pasa cuando cambia el modelo de datos), la hoja vieja se ARCHIVA con
 * otro nombre y se crea una nueva. Escribir igual desalinearía todas las filas
 * nuevas en silencio, y borrarla perdería los datos anteriores.
 *
 * `avisos` es un arreglo donde se deja constancia, para que la app lo muestre.
 */
function obtenerHoja(columnas, avisos) {
  const libro = SpreadsheetApp.getActiveSpreadsheet();
  var hoja = libro.getSheetByName(HOJA);

  if (hoja && hoja.getLastRow() > 0) {
    const actuales = hoja.getRange(1, 1, 1, hoja.getLastColumn())
                         .getValues()[0]
                         .map(function (x) { return String(x).trim(); })
                         .filter(function (x) { return x !== ''; });
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
    token: TOKEN, clave: 'veh_id', columnas: columnas, filas: [fila]
  })}});
  Logger.log(salida.getContent());
}

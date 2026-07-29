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

      // Índice de lo que ya está en la planilla: llave -> número de fila real.
      const ultima = hoja.getLastRow();
      const posicion = {};
      if (ultima > 1) {
        const llaves = hoja.getRange(2, iClave + 1, ultima - 1, 1).getValues();
        for (var i = 0; i < llaves.length; i++) {
          posicion[String(llaves[i][0])] = i + 2;
        }
      }

      const nuevas = [];
      var actualizadas = 0;
      for (var j = 0; j < filas.length; j++) {
        const fila = filas[j];
        const llave = String(fila[iClave]);
        if (posicion[llave]) {
          hoja.getRange(posicion[llave], 1, 1, columnas.length).setValues([fila]);
          actualizadas++;
        } else {
          nuevas.push(fila);
        }
      }

      if (nuevas.length) {
        hoja.getRange(hoja.getLastRow() + 1, 1, nuevas.length, columnas.length)
            .setValues(nuevas);
      }

      return respuesta({
        nuevas: nuevas.length,
        actualizadas: actualizadas,
        total: hoja.getLastRow() - 1,
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

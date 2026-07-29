"""
Plantilla de las credenciales de Google Sheets.

Cópiala como `config_sheets.py` y pon los valores reales. Ese archivo está en
.gitignore a propósito: el repositorio es público y con la URL más el token
cualquiera podría escribir en la planilla.

Sin `config_sheets.py` la app funciona igual, pero exporta solo a CSV y lo
indica en el diálogo Resumen ("Sin sincronización con Sheets").

Cómo obtener la URL: ver el README, sección "Configurar la planilla de Google".
"""

# URL /exec del Apps Script desplegado como aplicación web.
GAS_URL = ""

# Debe ser idéntico al TOKEN del script en la planilla.
GAS_TOKEN = "CAMBIA-ESTE-TOKEN"

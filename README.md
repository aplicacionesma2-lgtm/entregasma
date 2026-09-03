# Panel de documentos pendientes de atención

App en Streamlit que lee tus registros desde Google Sheets y te deja
filtrar por fecha de vencimiento, "De código de almacén" y "Código de
almacén", con métricas arriba y dos tablas (detalle y resumen).

## 1. Sube los datos a Google Sheets

Ya te dejé el archivo `registros_filtrados.xlsx` con todos los registros
excepto los que cumplen: Status de documento = C, CantidadPendiente > 0
y CantidadAtendida = 0 (esos quedaron fuera). Solo tienes que:

1. Crear una hoja de cálculo nueva en Google Sheets.
2. Archivo → Importar → subir `registros_filtrados.xlsx` → "Reemplazar
   hoja de cálculo" (o pegar los datos en una hoja llamada `Sheet1`).
3. Verifica que la primera fila tenga exactamente estos encabezados:
   `Número de documento, Status de documento, Fecha de vencimiento,
   Número de artículo, Descripción del artículo, Cantidad,
   De código de almacén, Código de almacén, CantidadAtendida,
   CantidadPendiente`.
4. Decide si la hoja será **pública** ("Cualquier persona con el
   enlace" → Lector) o **privada**. La opción pública es la más simple
   para arrancar; puedes pasar a privada más adelante sin cambiar el
   código de la app.
5. Copia la URL de la hoja (la de la barra de direcciones).

## 2. Configura la conexión

Copia `secrets.toml.example` a `.streamlit/secrets.toml` y pega tu URL
en `spreadsheet`. Si la hoja es privada, sigue la Opción B del archivo
de ejemplo (necesitas una cuenta de servicio de Google Cloud con
permiso de lector sobre la hoja).

## 3. Instala dependencias y ejecuta

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notas

- La app vuelve a excluir (Status C, pendiente > 0, atendida = 0) al
  leer los datos, así que aunque subas la hoja completa sin filtrar,
  igual va a mostrar solo lo relevante.
- Los datos se cachean 5 minutos (`ttl=300`); si actualizas la hoja y
  quieres verlo al instante, usa el menú ⋮ → "Rerun" o espera esos 5
  minutos.
- Si cambias el nombre de la pestaña dentro de Google Sheets, actualiza
  `worksheet="Sheet1"` en `app.py`.

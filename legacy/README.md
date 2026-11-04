# `legacy/` — script original

`consulta_vinculaciones.py` es el script con el que empezó el proyecto: un CLI con
login, pool de conexiones `psycopg2` y una consulta de llamadas entre dos números.

## Por qué no se usa

- Contraseñas de base de datos y de usuarios **en el código**.
- Hash de contraseñas con SHA-256 sin salt.
- Consulta columnas que no existen en los Excel actuales (`imei`, `destino_cod`,
  `fecha_txt`, `hora_txt`).
- Sin paginación ni límites.
- No carga datos: asume una tabla `llamadas` ya poblada.

## Qué se conservó

- La idea de consultar comunicaciones entre dos líneas en ambos sentidos
  (implementada en `src/cargadatos/consultas.py` → `vincular`).
- El nombre de la base (`comunicaciones`) y de la tabla (`llamadas`).
- Los campos `titular`, `destino`, `origen`, `fecha`, `hora`, `duracion_seg`,
  `tipo` y `sentido`.

## Credenciales eliminadas

La contraseña de PostgreSQL y los hashes de los usuarios se quitaron de este
archivo antes de publicarlo. El script ya no puede autenticarse: es solo una
referencia histórica.

## Cómo se ejecutaba

```powershell
pip install psycopg2-binary
python legacy/consulta_vinculaciones.py
```

No lo ejecutes con datos reales: el login y la configuración están obsoletos.

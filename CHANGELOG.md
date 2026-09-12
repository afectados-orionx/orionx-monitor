# Changelog

## 2026-09-12: informe público de destinos y scripts reproducibles

- `informes/2026-09-11_destinos_Binance_Ethereum.md/.pdf`: versión pública del barrido
  de salidas ETH/USDT/USDC. Solo muestra direcciones vigiladas por el monitor y las dos
  billeteras calientes de Binance con etiqueta pública; 28 direcciones de destino van
  codificadas (`D-01`…) porque son, en su mayoría, depósitos de clientes en exchanges.
- `scripts/destinos/`: los tres scripts que generan el análisis (solo stdlib, sin
  claves), con README de uso y reglas para publicar resultados.
- `README.md`: nueva sección "Informes".

## 2026-09-11 (noche): destinos en Binance y Bitfinex desde el circuito Ethereum

Fuente: barrido de todas las salidas de ETH, USDT y USDC de las 20 direcciones
Ethereum del monitor, agrupadas por destino y clasificadas según el siguiente
salto (informe `orionx-rastreo/binance_destinos/` en el repo de trabajo del
grupo; se publicará aquí una versión sin direcciones de depósito de clientes).

Agregadas (7, todas con transacción directa con una dirección confirmada):

- `0x5557e7ee…` **orionx**: billetera caliente anterior (2018-2021); traspasó
  497 ETH a la caliente actual en 7 tx (ene-feb 2021).
- `0x3f8f72ff…` **orionx**: recolector principal hacia la central
  (6.750 ETH + 969 k USDT + 234 k USDC, 2021-2026).
- `0xe93a2ab5…` **desvío**: depósito de Binance (barre a Binance 14); recibió
  108 ETH + 26,8 M USDT + 1,08 M USDC en 298 transferencias desde caliente,
  central y operativa (nov-2024 a ago-2026). Titular por establecer.
- `0x398781cc…` **desvío**: depósito de Binance; 8,85 M USDT desde la caliente
  en 68 tx desde el 5-ago-2025.
- `0x003740c4…` **desvío**: depósito de Bitfinex (etiqueta comunitaria,
  confianza media); 223 ETH + 8,22 M USDT desde la caliente, 2024-2026.
- `0x4def7506…` y `0xad1618f3…` **atribuidas** (confianza media): destinos sin
  etiqueta que recibieron 14,0 M y 9,85 M USDT desde la caliente y los
  reenvían a racimos de direcciones con sufijo repetido.

Descartada (editada, no borrada):

- `0x36da0bfe…` (estaba "relacionada"): mueve miles de millones de USDT/USDC,
  recibe de Circle y barre a depósitos de Binance y Coinbase. Es
  infraestructura de stablecoins, no una billetera de OrionX.

Nota de redacción: los depósitos de exchange se etiquetan por lo que son
(depósito de Binance/Bitfinex) y su titular solo lo puede establecer el
exchange ante un oficio de la Fiscalía. Ningún registro afirma quién es.

## 2026-09-11 — Revisión de la fuente única y falsas alertas de Tron

Revisión de la versión "fuente única" antes de publicarla:

- Se comprobó registro por registro que `direcciones.json` contiene exactamente las
  35 direcciones vigiladas de `billeteras.json` (mismo orden, mismos campos), las 45
  fichas de `atribuciones.json` y la descartada de `descartadas.json`. Único cambio:
  la dirección EVM `0x5528…` pasa a minúsculas en sus 3 filas (misma dirección).
- **Falsas alertas de Tron**: el 10 y 11 de septiembre el contador
  `totalTransactionCount` de Tronscan osciló (137970 → 137968 → 137970) sin que la
  billetera tuviera ninguna transacción nueva (la última real es del 8-sep 12:01 UTC)
  y el monitor avisó dos veces "nuevas transacciones sin cambio de saldo". Ahora un
  cambio solo en el contador se anota únicamente si también cambió la última actividad.
  Las 2 líneas falsas se retiraron de `historial.jsonl` (quedan en el historial de git).
- `MEJORAS.md` (informe de trabajo de la migración) no se publica; su contenido
  útil está en este archivo y en `CONTRIBUTING.md`.

## 2026-09-10 — Saneamiento (bugs del análisis + endurecimiento)

Correcciones sobre deuda previa, en el mismo lote que la fuente única:

- **Discord (B1)**: `discord()` usaba `get()`, que hacía `json.load` sobre el
  204 de Discord y reintentaba el POST → cada aviso llegaba **3 veces** y
  siempre se logueaba un error. Nueva función `post()`: un intento, sin parsear
  la respuesta, no lanza nunca.
- **`AVISAR_ERRORES` (B2)**: el aviso de errores llamaba `get()` sin `try` → una
  API caída tumbaba `monitor.py` y esa hora no se guardaba `data.json`. Ahora
  usa `post()` (no lanza).
- **Precios sin fallback (B6)**: si CoinGecko no responde, se reutilizan los
  precios del `data.json` anterior y se marca `precios_antiguos: true`; la web
  avisa "precios sin actualizar". Antes `total_clp` quedaba en 0 sin aviso.
- **Fuga de webhook (B8)**: `get()` metía `url[:60]` (con el token del webhook)
  en el `RuntimeError`. `post()` no incluye la URL en sus mensajes.
- **Re-anotar movimientos (B9)**: antes de escribir en `historial.jsonl` se
  descartan los eventos ya presentes (clave por contenido, sin la fecha), por si
  una corrida anterior no llegó a hacer `push`.
- **`TypeError` latente (B10)**: la detección de movimiento ahora exige también
  `saldo` actual no nulo, evitando un `f-string` con `None`.
- **`get()` (B12)**: no espera tras el último intento fallido.
- **Umbral duplicado (B5)**: `index.html` mostraba eventos con su propia
  heurística (`Math.abs(...) >= 0.001 || ...`). Ahora confía en `monitor.py`:
  muestra los eventos con `valor_usd != null`. Las 2 líneas de polvo de pruebas
  viejas en `historial.jsonl` (sin `valor_usd`) quedan ocultas sin tocar el
  ledger.
- **XSS almacenado (B7)**: `index.html` inyectaba campos de texto sin escapar.
  Nueva función `esc()` aplicada a todo campo de JSON, más un
  `<meta http-equiv="Content-Security-Policy">` restrictivo
  (`default-src 'none'`, `connect-src 'self'`).
- **`LICENSE`**: añadido el texto CC0 1.0 (antes solo una frase en el README).
- **`validate_data.py`**: exige `vigilar` (bool), `nota` (texto) y el metadato
  `fuente`; `cargar_wallets()` usa `.get()` (no `KeyError` con un registro
  incompleto).
- **`validate.yml`**: el chequeo de JSON no fallaba bajo `bash -e`
  (gotcha de `&&`); corregido.

## 2026-09-10 — Fuente única de direcciones

Antes había tres archivos con las mismas direcciones y esquemas distintos,
sincronizados a mano: `billeteras.json` (vigiladas), `atribuciones.json`
(propuestas + verificación) y `descartadas.json` (retiradas). Empezaban a
divergir (p. ej. la hot wallet EVM `0x5528…` estaba con mayúsculas en uno y
minúsculas en otro), y `descartadas.json` era "honor system": `monitor.py`
nunca lo leía.

Ahora la única fuente es **`direcciones.json`**: 51 registros (35 con
`monitorear: true`, 2 con `descartada: true`, el resto en evaluación o
relacionadas). Un registro por `(red, direccion)` reúne todos los campos de los
tres archivos anteriores. Las direcciones descartadas quedan **en el mismo
archivo** con `descartada: true` y su `motivo` — un registro, no un archivo
aparte.

Migración sin pérdida de información:

- La fusión y su reverso se comprobaron entrada por entrada y campo por campo
  antes de borrar nada: cero pérdidas. Único cambio intencional: las 3 filas de
  la dirección EVM `0x5528d82423d91da8e8fe8066fab15cc014ebd5e2` quedaron en
  minúsculas.
- `historial.jsonl` y `data.json` no se tocaron.
- `billeteras.json`, `atribuciones.json` y `descartadas.json` **se eliminaron**:
  ya nada del repo los leía y todo su contenido está en `direcciones.json`.

Cambios de código:

- `monitor.py`: lee `direcciones.json` (`monitorear: true`) en vez de
  `billeteras.json`; la forma de `data.json` no cambia. Nueva función `krd()`
  que normaliza la clave `(red, direccion)` con EVM en minúsculas, para que la
  detección de movimientos no se corte en la transición.
- `index.html`: la pestaña Atribuciones lee `direcciones.json` e incluye las
  descartadas, mostrando el motivo. El resto de pestañas no cambia (leen
  `data.json` / `precios_cierre.json`).
- `.github/workflows/monitor.yml`: `git pull --rebase --autostash` antes del
  `git push` (no falla si se mergeó un PR en el intertanto).
- `.github/workflows/validate.yml` (nuevo): en cada Pull Request valida el JSON
  y el esquema de `direcciones.json`.
- `scripts/validate_data.py` (nuevo): validador de esquema.
- `CONTRIBUTING.md`, `MEJORAS.md` (nuevos).

GitHub Pages sigue sirviéndose desde `main` / `/ (root)`: los forks no cambian
nada de su configuración.

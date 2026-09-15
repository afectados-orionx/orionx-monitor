# Changelog

## 2026-09-15: activos de clientes en las billeteras de OrionX (DAI, XAUT, DOT, ADA, SOL…)

Un afectado señaló en el issue #1 que la billetera caliente EVM `0x5528…` vale bastante
más de lo que mostraba el monitor, porque tiene activos en varias redes. El monitor ya
seguía esa dirección en Ethereum, BSC y Polygon, pero solo contaba el nativo, USDT y USDC.
Al revisar sus tokens aparecieron los activos que OrionX vendía a sus clientes: 33.474 DAI
y 2,61 XAUT (oro tokenizado) en Ethereum, y en BSC 29.748 DOT, 11.579 ADA y 108,6 SOL como
tokens Binance-Peg. Con eso la dirección pasa de ≈US$ 63.500 a ≈US$ 150.000 (el "net worth"
de Bscscan, ≈175.000, suma además tokens sin mercado).

- `monitor.py`: nueva tabla `TOKENS_ORIONX` que se consulta solo en las billeteras
  `tipo: orionx` (DAI y XAUT en Ethereum; DOT, ADA, SOL, XRP, LTC, TRX, ETH, BTCB y DAI en
  BSC; DAI en Polygon). Precios nuevos desde CoinGecko: `dai`, `tether-gold`, `polkadot`,
  `cardano`, `solana` (BTCB al precio de `bitcoin`).
- Como los tokens nuevos no estaban en la corrida anterior, la primera corrida no los
  reporta como movimiento (regla del 14 sep); desde la segunda, cualquier salida ≥ US$ 1
  queda en `historial.jsonl` y pasa por `scripts/alertas.py`.
- Las demás billeteras EVM (atribuidas y de desvío) siguen con nativo + USDT + USDC.


## 2026-09-14: el monitor también sigue USDC

El 14 de septiembre a las 18:09 UTC la dirección atribuida `0xad1618f3…` convirtió
28.000 USDT en 27.856 USDC a través de Uniswap V4, sin que los fondos salieran de la
dirección. La alerta funcionó (issue #2), pero el monitor solo consultaba USDT en las
redes EVM: los 29.749 USDC que quedaron ahí eran invisibles para él.

- `monitor.py`: en Ethereum, BSC y Polygon consulta ahora USDT **y USDC** (tabla
  `TOKENS`; en Polygon suma el USDC nativo y el USDC.e puenteado bajo el mismo
  símbolo). En Tron lee también el USDC TRC-20 si Tronscan lo informa. Precio de USDC
  desde CoinGecko (`usd-coin`).
- La comparación de tokens entre corridas es genérica y solo considera los tokens
  presentes en las dos fotos, para que un token recién agregado no aparezca como
  "entrada" de todo su saldo. El detalle de cada movimiento de token incluye el
  saldo resultante (`-28,000.00 USDT (saldo 11,782.58)`).
- Efecto en la página: aparece una línea `USDC` bajo el saldo de cada dirección EVM
  y el total "Localizable hoy" sube ≈US$ 35.500, que es el USDC ya existente en las
  direcciones vigiladas (29.749 en `0xad1618f3…`, 3.930 en la caliente en Polygon,
  1.677 en la caliente en Ethereum y montos menores). `scripts/alertas.py` ya
  contemplaba USDC en sus umbrales; no cambia.
- `scripts/validate_data.py`: admite `moneda: "USDC"` en `direcciones.json`.

## 2026-09-13: alertas automáticas cuando una dirección se mueve

Hasta ahora un movimiento quedaba solo en `historial.jsonl` y nadie se enteraba salvo
que mirara la web. Nuevo aviso automático, con la misma regla de siempre: solo
librería estándar y ninguna clave de terceros en el repositorio.

- `scripts/alertas.py` (nuevo): compara el `data.json` de la corrida anterior con el
  nuevo y levanta una alerta cuando el saldo cambia más que el umbral de esa moneda
  (0,01 BTC · 0,5 ETH · 1.000 XRP · 1.000 USDT/USDC · 5 LTC · 500 TRX; en BSC y
  Polygon, ≈US$ 500 al precio del momento, configurables con `ALERTA_UMBRALES`), y
  **sin umbral** cuando sale cualquier cantidad de una dirección `desvio` o
  `atribuida` con rol de almacenamiento en frío. Los cambios por debajo de 0,000001
  unidades se ignoran: son los redondeos de las APIs que ya habían dado falsas
  alertas en Tron. `monitor.py` no cambia: sigue anotando todo desde US$ 1.
- Por cada alerta se abre un **Issue** con etiqueta `movimiento` (título
  `Movimiento: <red> <dirección abreviada> <±monto> <fecha UTC>`; cuerpo con la
  etiqueta pública, saldo antes y después, valor aproximado en dólares, enlaces al
  explorador y al monitor y la frase "Dato en cadena; la Fiscalía debe establecer
  responsabilidades"). Si ya hay un issue abierto de esa dirección de las últimas
  24 h, se comenta ahí en vez de abrir otro. Usa el `GITHUB_TOKEN` del workflow.
- Telegram opcional y desacoplado: con los secretos `TELEGRAM_BOT_TOKEN` y
  `TELEGRAM_CHAT_ID` se manda el mismo texto; sin ellos el paso se salta sin fallar.
  Ni el token del bot ni la URL del webhook aparecen en los mensajes de error.
- `alertas.json` (nuevo): las últimas 50 alertas, más los umbrales vigentes. La
  pestaña **Movimientos** de `index.html` las muestra arriba de la lista completa,
  con el motivo y el enlace al explorador. Se lee con `fetch` del mismo origen, así
  que la CSP (`connect-src 'self'`) no cambia.
- `.github/workflows/monitor.yml`: guarda una foto de `data.json` antes de consultar,
  corre `alertas.py` después de `monitor.py`, hace commit también de `alertas.json` y
  **recién después** avisa (`if: always()`), para que el issue apunte a datos ya
  publicados y un aviso que falle no tumbe la corrida. Nuevo permiso `issues: write`.
- `.github/workflows/validate.yml`: `alertas.json` entra en el chequeo de JSON.

## 2026-09-13: vista previa al compartir y metadatos

- `og.png` (1200x630), `favicon.png` y `apple-touch-icon.png`: al compartir el enlace del
  monitor en WhatsApp, Discord, Facebook o X ahora aparece una tarjeta con imagen.
- `index.html`: título orientado a búsqueda, canonical, Open Graph, Twitter card grande y
  JSON-LD (`WebApplication`) con el contacto del grupo. Sin cambios funcionales.

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

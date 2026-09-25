# Changelog

## 2026-09-25: el monitor deja de seguir a los servicios de alto volumen

Entre el 12 y el 25-sep el monitor emitió 469 alertas y **427 fueron de direcciones descubiertas**,
casi todas mesas o procesadores de terceros a dos saltos del caso: `0x58b704…9025` (1.721
transferencias y US$ 110 M en 24 h), `0x8bc2ab7e…1731`, `0xd4a0669d…8810` y `0x74aa5387…6828`
movían más en un día que todo el descalce de OrionX. Ninguna de las 25 billeteras de OrionX se movió.

- `detectar_servicios()`: una descubierta seguida que en 24 h (mirando los últimos 7 días del
  historial) mueve **US$ 5 M** (`UMBRAL_SERVICIO_USD_24H`) o hace **50 transferencias**
  (`UMBRAL_SERVICIO_TX_24H`) queda con `servicio: true`, deja de seguirse y sus destinos vigilados
  solos también. Se conserva en `descubiertas.json` para no volver a seguirla si reaparece, y un
  destino suyo ya no se vigila solo. Con el historial actual: 6 servicios, 40 → 9 seguidas.
- `alertas.py`: el "fondeo de gas" ya no se evalúa en descubiertas (`0xd4e8d5f8…0901` recibió ≈500
  depósitos chicos de ETH en una semana y dio 102 alertas).
- La pestaña de descubiertas muestra la marca "servicio de alto volumen: no se sigue".

Las direcciones del caso (`orionx`, `querella`, `desvio`, `atribuida`) no cambian: se siguen igual.

## 2026-09-22: avisos de Discord en palabras simples y un resumen diario

El canal de Discord recibía ≈15 avisos al día, casi todos de la mesa OTC y de direcciones
descubiertas ("EOA con delegación EIP-7702", "destino de una salida"), sin ningún movimiento de
las billeteras de OrionX. Para quien no rastrea cadenas eso era ruido y parecía que "se estaba
yendo la plata". Ahora (`DISCORD_MODO=resumen`, por defecto):

- **Aviso inmediato solo si importa:** se mueve una billetera de OrionX o citada en la querella
  (`tipo` `orionx`/`querella`) o un emisor congela fondos. El texto dice qué salió, cuánto en
  dólares y hacia quién ("Gate.io (depósito)", "una dirección sin nombre público").
- **Resumen diario a las 20:00 de Chile** (`RESUMEN_HORA_CHILE`): estado de las 25 billeteras de
  OrionX y, para el racimo de terceros, solo lo que entra desde afuera y sale hacia afuera,
  agrupado por entidad con nombre. Lo que circula entre direcciones vigiladas no se suma dos veces.
  La fecha del último resumen queda en `data.json` (`resumen_discord`).
- `ENTIDADES` nombra dos destinos identificados a mano: el contrato verificado **CircleDeposit**
  `0x6d89f703…a585` (su `owner` es `0x55fe002a…44b8`, etiqueta pública "Circle"; recibió
  ≈US$ 12 M en USDC el 22-sep desde `0xd4a0669d…`) y el depósito de **Gate.io** `0x81ce974e…c5b8`.
- `DISCORD_MODO=detalle` vuelve al aviso técnico por corrida. El historial, `data.json`, los
  issues y el Telegram del rock no cambian.

## 2026-09-20: una corrida colgada dejó la web 3 h sin actualizar

La corrida de las 08:19 UTC quedó **3 h 20 min** pidiendo datos a fuentes que no respondían desde
el runner de GitHub (13 direcciones BTC con `Network is unreachable` hacia mempool.space y un 429
de Tronscan; cada petición reintenta tres veces con 40 s de espera). Como `concurrency: monitor`
serializa las corridas, las de 09:17 y 10:17 quedaron en cola y se cancelaron, y la de 11:17
arrancó junto con el final de la lenta: las dos partían del mismo commit, el `git pull --rebase`
chocó (`CONFLICT` en `data.json`, `historial.jsonl` y `descubiertas.json`) y esa corrida murió sin
publicar. Resultado: `data.json` en Pages con marca de las 08:19 hasta pasadas las 12:00 UTC.
La vigilancia no se interrumpió: el rock siguió consultando cada 10 min sin errores.

Tres cambios para que no se repita:

- **Presupuesto de tiempo en `monitor.py`** (`LIMITE_MINUTOS`, por defecto 15). Agotado, `get()`
  deja de intentar: las direcciones pendientes conservan el valor de la corrida anterior y quedan
  listadas en `errores`, igual que cuando una fuente falla. Mejor una foto parcial y puntual que
  una completa tres horas tarde.
- **`timeout-minutes: 22` en el workflow.** Ninguna corrida puede volver a bloquear la cola.
- **`scripts/publicar.sh`** reemplaza al `git pull --rebase` del workflow. Si el remoto avanzó,
  rehace el commit sobre `origin/main`: en `data.json`, `alertas.json` y `descubiertas.json` (fotos
  completas) gana lo recién generado, y `historial.jsonl` (registro que solo crece) conserva las
  líneas de ambas corridas sin repetir. Hasta tres intentos.

## 2026-09-17: el monitor sigue solo a dónde va el dinero (y deja de confundir billeteras con contratos)

Las 12 alertas del 16-sep dejaron a la vista un hueco: el monitor avisaba de la salida, anotaba el
destino en `descubiertas.json` con `seguir: false` y ahí se detenía. Si ese destino volvía a mover
los fondos entre corridas, no había aviso. Tres cambios en `monitor.py`:

**1. Vigilancia automática de destinos.** Un destino queda en `seguir: true` sin esperar validación
humana cuando recibe **US$ 10.000 o más** (`UMBRAL_SEGUIR_USD`, configurable por entorno) de una
dirección de tipo `orionx`/`desvio`/`atribuida`/`querella`/`puente`/`descubierta`, **no** tiene
etiqueta pública de exchange (ahí lo que sirve es oficiar, no vigilar) y está a **dos saltos o
menos** de la lista (`MAX_SALTOS`; cada registro trae ahora `salto`, `valor_usd_max` y
`seguir_motivo`). Sigue rigiendo `MAX_SEGUIDAS = 40`. Vigilar no es atribuir: estas direcciones no
entran a `direcciones.json` sin que una persona valide la liga.

**2. Las EOA con delegación EIP-7702 ya no se descartan como contratos.** `es_contrato()` daba por
contrato a toda dirección con código, y las billeteras que pagan la comisión de red con el token
(EIP-7702, código `0xef0100…` + el contrato delegado) tienen código. Por eso quedaron fuera
justamente los tres destinos más grandes del 16-sep. Ahora `codigo_evm()` cachea el código,
`delegado_7702()` extrae el contrato delegado y el motivo del registro lo anota.

**3. Frenos contra el ruido, medidos en una corrida real.** Al probarlo, `0x8bc2ab7e…` repartió
**US$ 2,8 M a once destinos en una sola corrida**: es un agregador que mueve dinero de terceros, no
una billetera personal. Dos reglas nuevas:

- `MAX_AUTO_POR_ORIGEN = 3`: si un origen reparte a más destinos grandes en una corrida, ninguno de
  esos destinos se vigila solo; quedan anotados con el reparto en `seguir_motivo` y el origen
  marcado `agregador: true`, para que los revise una persona.
- Los **avisos** (líneas `MOV` que lee el rock para Telegram, y el webhook de Discord) dejan fuera
  el goteo de las descubiertas bajo `UMBRAL_AVISO_DESCUBIERTA_USD` (US$ 50.000) y agrupan en una
  línea con el neto a la dirección que hizo más de tres movimientos en la corrida. En `data.json`,
  en `historial.jsonl` y en la web siguen estando todos. Medido sobre la corrida de prueba: **57
  movimientos → 1 aviso**. `scripts/alertas.py` usa el mismo umbral de US$ 50.000 para las
  direcciones de tipo `descubierta` (`ALERTA_UMBRAL_DESCUBIERTA_USD`).

La corrida completa pasó de ≈2 min a **4 min 20 s** con 51 direcciones (45 vigiladas + 6
descubiertas seguidas). El timer del rock corre cada 10 minutos: hay margen, pero conviene mirarlo
si el cupo de seguidas crece.

**Las seis direcciones que recibieron fondos el 16-sep quedaron en vigilancia** (≈US$ 1,08 M en
total). Las tres que el filtro dejaba fuera, agregadas a mano con su hash:

| Dirección | Recibió (16-sep) | Desde | Delegado EIP-7702 |
|---|---|---|---|
| `0x573f5081…` | 850.000 USDT | `0xad1618f3…` | `0xa34e1e38…` |
| `0x5b50619e…` | 100.000 USDT | `0xfd56ef36…` | `0xa34e1e38…` |
| `0x8bc2ab7e…` | 42.000 + 14.742 USDT y 27.309 USDC | `0x55903d69…` | `0x0000fb77…` |

`0x573f5081…` y `0x5b50619e…` comparten el mismo contrato delegado, o sea la misma infraestructura
de billetera por dos vías; `0x8bc2ab7e…` usa el mismo delegado que `0x55903d69…` (el
"UniversalGaslessDelegate" ya descrito el 15-sep). Las otras tres, ya anotadas y ahora seguidas:
`0xa28bd32c…` (28.428 USDC), `0xd4e8d5f8…` (8.090 USDT en dos salidas) y `0x43d891ff…` (5.333 USDT);
las dos últimas van bajo el umbral, activadas a mano.

Corrección de dato: los destinos que el mensaje del 16-sep describía como "contratos sin nombre" no
son contratos, son cuentas de persona con gas patrocinado.

## 2026-09-15 (noche, 2): `0xfd56ef36…` no era liga indirecta, es destino directo de la caliente

Al rastrear el origen de los 200.000 USDT del movimiento de la tarde apareció el hallazgo del día:
`0xfd56ef36…`, que se había agregado como atribuida con liga indirecta, **recibió 5.244.503 USDT
directamente de la billetera caliente `0x5528d824…` en 47 transferencias entre el 18-ene-2024 y el
29-ene-2026** (ejemplo `0x576adfef…`), en un solo sentido. Es la cuarta de las "cadenas OTC" que el
informe del 11 de septiembre dejó sin identificar. Pasa a **desvío**, liga confirmada, confianza alta.

Con eso, las **dos mayores cadenas OTC del informe** (`0xad1618f3…`, 9,85 M USDT, y `0xfd56ef36…`,
5,24 M USDT: 15,1 M USDT salidos de OrionX) resultan ser contrapartes entre sí: desde el 3-jul-2026,
21 envíos por 5.342.000 USDT de la segunda a la primera. No prueba desvío —el dinero pasa por Binance
entre medio y la fungibilidad rompe la trazabilidad—, pero es la estructura que conviene oficiar.

Perfil de `0xfd56ef36…`: activa desde el 13-dic-2023, 57,94 M USDT de entrada y 57,54 M de salida
(no acumula), 83 contrapartes relevantes, montos redondos, días hábiles. En jul-sep 2026 el **89 %**
de su USDT entrante viene de billeteras calientes de **Binance** con etiqueta pública (14, 15, 16, 17
y 18); el 15-sep repuso los 200.000 USDT **34 minutos** después de enviarlos. El cierre del 3-sep no
la frenó: su salida media diaria subió de 99.835 a 206.843 USDT.

Correcciones de dato en el mismo registro y en `0x55903d69…`:

- `0x55903d69…` **no es un contrato desplegado** sino una **EOA con delegación EIP-7702** (código
  delegado a `0x0000Fb7702…`, "UniversalGaslessDelegate": transferencias con gas patrocinado).
  Funciona como recolector: barre lo que recibe hacia `0x8bc2ab7e…`, otra EOA con el mismo delegado,
  normalmente al día siguiente. Al cierre del día retenía 47.110,37 USDT y 27.308,72 USDC.
- El aviso del 14-sep (−28.000 USDT) **no fue una salida de fondos**: fue un cambio de USDT a USDC en
  Uniswap v4; el dinero quedó en la misma dirección.

**Envenenamiento de direcciones, alcance real.** Medido sobre 500 transferencias de `0xad1618f3…`: por
cada contraparte real hay **5 a 8 clones** con los mismos 4 primeros y 4 últimos caracteres, más tokens
imitadores con símbolo visualmente idéntico a USDT/USDC. La billetera caliente de OrionX también lo
sufre: tienen clones circulando incluso el depósito de Bitfinex `0x003740c4…2663` y el de Binance
`0xe93a2ab5…372e` citados en el informe. Dos consecuencias: **cotejar carácter por carácter toda
dirección antes de citarla** en un escrito, y leer siempre por contrato, nunca por símbolo. Verificado
que ninguna de las 32 direcciones EVM del monitor es clon de otra.

Aguas abajo (registrado, no incorporado al monitor por estar a tres o más saltos): `0x55903d69…` →
`0x8bc2ab7e…` → `0xff9f8615…` (tránsito puro, 16,2 M USD en 8 tx) → `0x300471d9…` → `0x04eb04eb…`
(retiene 1.825.564 USDC); y `0x14b97ecc…` (agregador, 8,44 M de entrada y 10,39 M de salida entre el
11 y el 15-sep) → `0x44b0bd8a…`, que trocea en importes exactos de 1.000.000 USD hacia direcciones
nuevas que reenvían en minutos a un mismo concentrador. **Ninguna de las ~360 contrapartes rastreadas
tiene etiqueta pública de exchange**: el dinero no llega a un exchange identificable donde pedir
congelamiento, se dispersa entre concentradores anónimos.

## 2026-09-15 (noche): tres direcciones nuevas por el movimiento de 0xad1618

Por el movimiento del 15-sep en la atribuida `0xad1618f3…` entran a vigilancia, con liga indirecta:
`0xfd56ef36…` (atribuida: envió los 200.000 USDT; guarda ≈399.000 USDT), `0x55903d69…` (desvío: recibió
27.308,72 USDC; es un contrato tipo billetera inteligente) y `0x628e3983…` (desvío: recibió 100 USDT,
monto de prueba, sin vigilancia prioritaria). Evidencia: los hashes del issue #3. 45 direcciones en monitor.

## 2026-09-15 (tarde): versión 3 del monitor, de saldos a transacciones

Hasta hoy el monitor comparaba saldos de una lista fija de tokens. Con eso veía *que* algo se
movió, pero no *a dónde*, no veía tokens que no estuvieran en la lista y no distinguía una
transferencia real de una falsa. La misma tarde del cambio la dirección atribuida `0xad1618f3…`
recibió 200.000 USDT (18:14 UTC), envió 27.308,72 USDC y 100 USDT, y en el intertanto recibió una
docena de transferencias de valor cero y de tokens falsos "USDT"/"USDC" desde direcciones parecidas
(envenenamiento de direcciones). El monitor viejo vio solo los cambios de saldo.

- **Transferencias con hash y contraparte** en todas las redes: `eth_getLogs` filtrando solo por
  tema en Ethereum (Tenderly, mevblocker), Polygon (Tenderly) y BSC (bloXroute y 1rpc, por partes);
  Tronscan para TRC-20 y TRX; xrpscan para pagos XRP; mempool.space y litecoinspace para BTC y LTC.
  Cada evento lleva `hash`, `hash_url`, `contraparte`, `contraparte_etiqueta`, `fecha_cadena`.
- **Tokens descubiertos, no listados**: en EVM cuenta cualquier token que haya tocado la dirección
  (por los logs) o que Blockscout vea en ella (inventario diario en Ethereum y Polygon), pero solo
  si tiene **precio por contrato** (CoinGecko; Blockscout de respaldo). Un "USDT" imitador no tiene
  precio y no cuenta ni como saldo ni como movimiento. En Tron cuentan todos los TRC-20 con precio
  en Tronscan. `TOKENS_ORIONX` queda como semilla de las billeteras `orionx` (BSC no tiene Blockscout).
- **Señales previas al movimiento**: aprobaciones ERC-20 (`Approval`) desde una dirección vigilada,
  cambio de permisos owner/active en Tron, y en `scripts/alertas.py` el "fondeo de gas" (entrada
  pequeña de nativo en una dirección con tokens por más de US$ 1.000). Se avisan sin umbral.
- **Congelamiento**: cada hora se consulta `isBlackListed` (USDT) e `isBlacklisted` (USDC) por
  dirección; el campo `congelada` va en `data.json`, la web lo marca y el cambio de estado alerta.
- **Etiquetas de contrapartes**: `etiquetas_publicas.json` (copia comunitaria filtrada a exchanges,
  puentes, mezcladores y protocolos; 6.100 direcciones) más `direcciones.json` y `descubiertas.json`.
- **`descubiertas.json`** (nuevo, lo escribe el robot y lo commitea el workflow): destinos de
  salidas y, en BTC/LTC, direcciones que gastan junto a una vigilada o reciben el posible vuelto.
  Las "misma billetera" se siguen en cada corrida y aparecen en la tabla como "Descubierta".
- **Alertas** (`scripts/alertas.py`): cuerpo con las transacciones (hash, contraparte, etiqueta),
  clases nuevas (`aprobacion`, `permisos`, `congelamiento`, `gas`), umbral ≈US$ 500 para cualquier
  token con precio, y copia fechada en Wayback Machine cuando Save Page Now responde.
- **Rendimiento**: las consultas EVM de cada dirección van en un solo lote JSON-RPC (saldo, nonce,
  `balanceOf` de cada token y lista negra) en vez de una llamada por dato. El congelamiento se
  revisa una vez por hora aunque el monitor corra cada 10 minutos.
- **Web**: los movimientos enlazan a la transacción y muestran la contraparte; las alertas muestran
  su clase y sus transacciones; badge "CONGELADA"; tabla de direcciones descubiertas; los tokens sin
  precio se cuentan aparte ("+N tokens sin precio, no contados").
- Regla de la primera corrida: cursores, tokens y direcciones nuevos fijan su punto de partida sin
  generar movimientos. Los eventos con hash se deduplican por `(red, dirección, hash, moneda)`.


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

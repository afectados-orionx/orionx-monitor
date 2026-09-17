# Monitor de billeteras OrionX

**Página en vivo: https://afectados-orionx.github.io/orionx-monitor/**

Muestra saldo, valor en pesos y última actividad de las billeteras vinculadas a OrionX en Bitcoin, XRP, Tron, Litecoin, Ethereum, BSC y Polygon, y registra cada movimiento con fecha y hora. Se actualiza sola cada hora. Tiene cinco pestañas: **Resumen** (en lenguaje simple), **Billeteras vigiladas**, **Atribuciones** (todas las direcciones atribuidas a OrionX por afectados, con nivel de confianza, tipo de evidencia y nuestra verificación en cadena), **Precios al cierre** (última operación de cada mercado en OrionX el 3 de septiembre de 2026) y **Movimientos** (arriba, los movimientos con alerta: los grandes para su red y cualquier salida desde almacenamiento en frío). Lo mantienen clientes afectados por el cierre del 3 de septiembre de 2026; no tiene relación con la empresa.

Todo es verificable: cada dirección enlaza a su explorador público y `direcciones.json` anota qué transacción la vincula a OrionX.

## Ten tu propia copia (10 minutos, gratis, sin servidor)

Cuantas más copias existan, más difícil es que el registro desaparezca. Cada copia consulta y guarda los datos por su cuenta.

1. Crea una cuenta en github.com si no tienes.
2. Arriba a la derecha de esta página pulsa **Fork** y confirma. Ya tienes tu copia en `github.com/TU_USUARIO/orionx-monitor`.
3. En tu copia: **Settings → Pages → Source: "Deploy from a branch" → Branch: `main`, carpeta `/ (root)` → Save**. En dos minutos tu página estará en `https://TU_USUARIO.github.io/orionx-monitor/`.
4. **Settings → Actions → General → Workflow permissions → marca "Read and write permissions" → Save.** Sin esto el robot no puede guardar los datos.
5. Pestaña **Actions**. Si aparece un aviso para habilitar workflows, acéptalo. Entra en **monitor → Run workflow → Run workflow**. Desde ahí corre sola cada hora.

Con eso también funcionan las alertas: cada movimiento grande abre un **Issue** en tu copia (ver "Alertas" más abajo). Si no quieres esos avisos, en **Settings → General → Features** desmarca *Issues* y el monitor seguirá funcionando igual.

Opcional, avisos a Discord: un administrador del servidor crea un webhook (Ajustes del canal → Integraciones → Webhooks → Nuevo webhook → Copiar URL). En tu copia: **Settings → Secrets and variables → Actions → New repository secret**, nombre `DISCORD_WEBHOOK`, valor la URL. Cada movimiento detectado se publicará en ese canal.

Para recibir las billeteras nuevas que se agreguen aquí, en tu copia pulsa **Sync fork → Update branch** de vez en cuando.

## Aportar una billetera

Si reconoces una dirección del monitor como tuya (por ejemplo, un retiro propio), avisa y se retira. Las direcciones retiradas quedan registradas en `direcciones.json` con `descartada: true` y el motivo, para no volver a agregarlas y para dejar constancia.

Solo se agregan direcciones con una transacción pública que las ancle a OrionX (un retiro que la empresa te pagó, un depósito que le hiciste, o una salida desde una billetera ya confirmada). Abre un **Issue** en este repositorio con: red, dirección, el hash de esa transacción y una frase de qué es. No pongas datos personales.

Si sabes editar JSON, propón el cambio directamente en **`direcciones.json`** con un Pull Request (ver `CONTRIBUTING.md`). Es el único archivo que se edita a mano. Campos de un registro: `red` (BTC, XRP, TRX, LTC, ETH, BSC, POLYGON — las direcciones EVM van en minúsculas), `direccion`, `monitorear` (true = se consulta cada hora), `descartada` (true = registro de retirada), `estado` (`monitor` / `evaluacion` / `relacionada` / `descartada`), `tipo`, `etiqueta`, `nota`, y los de atribución (`rol`, `confianza`, `evidencia`, `verificada`, `liga_confirmada`, `liga_indirecta`, `etiqueta_publica`, `saldo_observado`, `moneda`). Tipos: `orionx` (billetera de la empresa, confirmada o con transacción directa con una confirmada), `atribuida` (saldo relevante con liga solo indirecta; se vigila pero no se afirma que sea de OrionX), `desvio` (destino de fondos salidos de OrionX), `querella` (citada en la querella), `puente` (recolección o paso histórico de fondos).

**Criterio para pasar de "atribuida" o "en evaluación" a `orionx`:** una transacción pública directa con una billetera ya confirmada, o una etiqueta pública en un explorador (xrpscan, etherscan). `direcciones.json` guarda todas las direcciones propuestas con su confianza, evidencia y estado; la pestaña Atribuciones lo muestra. Las que no cumplen el criterio quedan con `monitorear: false` y `estado: evaluacion`, para no meter ruido en la investigación.

## Alertas: que alguien se entere cuando algo se mueve

Antes, un movimiento solo quedaba anotado en `historial.jsonl` y había que acordarse de mirar. Ahora `scripts/alertas.py` compara el `data.json` de la corrida anterior con el nuevo y levanta una **alerta** cuando:

- el saldo cambia más que el umbral de esa moneda: **0,01 BTC · 0,5 ETH · 1.000 XRP · 1.000 USDT/USDC · 5 LTC · 500 TRX**, y en **BSC y Polygon** lo que equivalga a **≈US$ 500** al precio del momento; o
- **sale cualquier cantidad** de una dirección de tipo `desvio` o `atribuida` cuyo rol declarado es almacenamiento en frío. Ahí no hay umbral: que se mueva ya es la noticia; o
- (desde el 15-sep-2026) aparece una **señal previa al movimiento**, también sin umbral: una **aprobación** ERC-20 desde la dirección (autoriza a un contrato o a otra dirección a mover sus tokens), un **cambio de permisos** de la cuenta en Tron (cambio de quién controla las llaves), un **congelamiento** por el emisor de la stablecoin (Tether o Circle pusieron la dirección en lista negra) o un **fondeo de gas**: una entrada pequeña de ETH, BNB, POL o TRX en una dirección que guarda tokens por más de US$ 1.000, que es lo que se hace justo antes de vaciarla. Para cualquier otro token con precio (DAI, XAUT, DOT…) el umbral es ≈US$ 500.

Cada alerta trae, cuando la red lo permite, **las transacciones con hash y contraparte** que explican el cambio, con la etiqueta pública de la contraparte si es un exchange, un puente o un servicio conocido (`etiquetas_publicas.json`, copia comunitaria de las etiquetas de los exploradores: confirmar en el explorador antes de citar). Además pide a **Wayback Machine** una copia fechada de la página del explorador, para que el dato quede archivado por un tercero (es un intento de cortesía: si web.archive.org no responde, la alerta sale igual).

Cambios por debajo de 0,000001 unidades se ignoran siempre: son redondeos de las APIs. Los umbrales se cambian sin tocar el código con la variable de entorno `ALERTA_UMBRALES`, por ejemplo `ALERTA_UMBRALES='{"BTC": 0.02}'`.

Qué hace con cada alerta:

1. La escribe en **`alertas.json`** (las últimas 50, la más reciente primero). La pestaña **Movimientos** de la web las muestra arriba, con su motivo y el enlace al explorador.
2. Abre un **Issue** en este repositorio con la etiqueta `movimiento`: título `Movimiento: <red> <dirección abreviada> <±monto> <fecha UTC>`, y en el cuerpo la etiqueta pública de la dirección, saldo antes y después, valor aproximado en dólares y los enlaces al explorador y al monitor. Si ya hay un issue abierto de esa misma dirección de las últimas 24 horas, comenta ahí en vez de abrir otro. Usa el `GITHUB_TOKEN` del propio workflow (permiso `issues: write`), sin claves de terceros.
3. Si están configurados los secretos `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`, manda el mismo texto a ese chat. Si no están, se salta el paso sin fallar.

Un aviso que falle nunca interrumpe el guardado de los datos: primero se hace commit de `data.json`, `historial.jsonl` y `alertas.json`, y recién después se avisa.

**Configurar Telegram (opcional).** Habla con `@BotFather` en Telegram, `/newbot`, y copia el token que te da. Agrega el bot al grupo o canal donde quieras los avisos, escribe cualquier mensaje ahí y abre `https://api.telegram.org/bot<TOKEN>/getUpdates` para leer el `chat.id` (en los grupos empieza con `-100`). Luego, en el repositorio: **Settings → Secrets and variables → Actions → New repository secret**, dos secretos: `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`. Los tokens van **solo** ahí; nunca en un archivo del repositorio.

Probar las alertas sin esperar a que algo se mueva: copia `data.json` a otro archivo, edita a mano un saldo y compara.

```bash
cp data.json /tmp/anterior.json
# edita /tmp/anterior.json y cambia un saldo
python3 scripts/alertas.py --anterior /tmp/anterior.json --sin-guardar
```

Sin `GITHUB_TOKEN` ni secretos de Telegram no manda nada: solo imprime lo que habría avisado.

## Informes

Los análisis grandes se publican en `informes/` en versión pública: solo direcciones
que el monitor vigila; las demás van codificadas para no exponer a clientes. Los
scripts que los generan están en `scripts/`, para que cualquiera pueda repetirlos.

- [2026-09-11 · Destinos en Binance de las billeteras OrionX en Ethereum](informes/2026-09-11_destinos_Binance_Ethereum.md) ([PDF](informes/2026-09-11_destinos_Binance_Ethereum.pdf)) · scripts en [`scripts/destinos/`](scripts/destinos/README.md)

## Cómo funciona

- `direcciones.json` es la **fuente única** de direcciones: monitoreadas, en evaluación y descartadas, todo en un archivo. `scripts/validate_data.py` revisa el esquema en cada Pull Request.
- `monitor.py` (Python, sin dependencias) lee de `direcciones.json` las que tienen `monitorear: true` y consulta mempool.space, litecoinspace, xrpscan, tronscan, TronGrid, Blockscout y nodos RPC públicos, más precios de CoinGecko. **Desde el 15-sep-2026 (versión 3)** no vigila solo saldos: lee las **transferencias con hash y contraparte** (eventos `Transfer` en Ethereum, BSC y Polygon con `eth_getLogs` en nodos que aceptan filtrar solo por tema; transferencias TRC-20 y TRX en Tronscan; pagos en xrpscan; transacciones en mempool.space y litecoinspace), las **aprobaciones** ERC-20, los **permisos** de cuenta en Tron y el estado de **congelamiento** en USDT y USDC. En las redes EVM los tokens **no son una lista fija**: se descubren con esos eventos y con el inventario de Blockscout (una vez al día en Ethereum y Polygon), y un token solo cuenta si tiene **precio por contrato** (CoinGecko, o Blockscout de respaldo): así los tokens imitadores con símbolo "USDT" y el spam no suman ni alertan (el 15-sep-2026 una dirección vigilada recibió en 20 minutos una docena de transferencias falsas de "USDT" y "USDC" desde direcciones parecidas a las reales). En Tron cuenta todos los TRC-20 con precio en Tronscan. Las direcciones que aparecen como destino de una salida, y en BTC/LTC las que gastan junto a una vigilada (misma billetera) o reciben el posible vuelto, van a **`descubiertas.json`**, no a `direcciones.json`: las propone el monitor, las valida una persona (ver `CONTRIBUTING.md`). **Desde el 17-sep-2026** el monitor además las **vigila solo** (`seguir: true`) cuando reciben US$ 10.000 o más de una dirección del caso, no tienen etiqueta pública de exchange y están a dos saltos o menos; si el origen repartió a más de tres destinos grandes en una misma corrida se comporta como agregador de dinero de terceros y sus destinos quedan anotados para revisión humana, sin vigilarse. Las cuentas con **delegación EIP-7702** (código `0xef0100…`: billeteras que pagan la comisión de red con el token) tienen código pero no son contratos, y se descubren como cualquier cuenta. Vigilar no es atribuir: para que una dirección entre a `direcciones.json` la liga la valida una persona. Todo el estado entre corridas (cursores por red, tokens conocidos y sus precios, estado de congelamiento) vive en `data.json`; la primera vez que el monitor ve algo (un token, una dirección, una red) fija el punto de partida sin generar movimientos. En Ethereum, BSC, Polygon y Tron lee además los saldos de **USDT y USDC** de cada dirección (en Polygon suma el USDC nativo y el USDC.e puenteado). En las billeteras propias de OrionX (`tipo: orionx`) lee también los demás activos de clientes que la empresa custodiaba ahí: DAI y XAUT en Ethereum, y en BSC los tokens Binance-Peg de DOT, ADA, SOL, XRP, LTC, TRX, ETH, BTC y DAI (tabla `TOKENS_ORIONX`; solo en esas billeteras para no multiplicar las llamadas RPC). Tokens sin mercado real no se valoran, por eso el total puede ser menor al "net worth" de los exploradores, que suman cualquier token. Compara con el `data.json` anterior y anota los cambios en `historial.jsonl`.
- `scripts/alertas.py` (Python, sin dependencias) compara la foto anterior de `data.json` con la nueva, escribe `alertas.json` y avisa por Issue y Telegram. Ver "Alertas" más abajo.
- `.github/workflows/monitor.yml` lo ejecuta cada hora en GitHub Actions y guarda el resultado en el repositorio (con `git pull --rebase` antes del push, para no fallar si se mergeó un PR en el intertanto); después de guardar, manda los avisos.
- `index.html` lee `data.json` (monitor), `alertas.json` (movimientos con alerta), `descubiertas.json` (direcciones propuestas por el monitor, sin validar), `direcciones.json` (direcciones propuestas, su verificación y las descartadas) y `precios_cierre.json` (último libro de órdenes, transcrito del informe de un afectado) y dibuja la página. No hay servidor ni base de datos.
- Un movimiento se registra si vale al menos **US$ 1** (≈1.000 CLP) al precio del momento, en cualquier moneda (variable de entorno `UMBRAL_USD` para cambiarlo). Así se detectan también retiros goteados en microtransacciones: como se compara el saldo entre un chequeo y el siguiente, muchas transferencias pequeñas dentro de la hora se suman. Si CoinGecko no responde, se usa un mínimo en unidades por moneda. Los cambios menores suelen ser redondeos de las APIs. Si cambia el número de transacciones sin que el saldo pase el umbral, igual se anota, siempre que también haya cambiado la fecha de la última transacción (los contadores de algunos exploradores oscilan sin que haya transacciones nuevas).
- Límites conocidos de la versión 3: BSC no tiene un nodo público cómodo para `eth_getLogs` sin filtro de contrato (bloXroute admite 5.000 bloques pero suele agotar el tiempo; 1rpc solo 50 bloques por llamada), así que en BSC el cursor puede avanzar por partes y una corrida horaria no siempre alcanza; el servidor del grupo, que corre cada 10 minutos, sí llega. En Tron se leen hasta 50 transferencias por corrida y dirección. Las aprobaciones no se leen en los tramos chicos de BSC. Si Save Page Now de Wayback no responde (el 15-sep-2026 devolvía error 500), la alerta sale sin esa línea.
- Si una API de saldos falla, se conserva el último dato y la página lo indica. Si CoinGecko no responde, se reutilizan los precios del `data.json` anterior y la página avisa "precios sin actualizar" (antes quedaba todo en $0). Las APIs gratuitas aguantan sin problema una consulta por hora; no bajes el cron a menos de 30 minutos.
- Avisos a Discord: un solo POST por tanda, sin reintentos (antes se enviaba tres veces). Un fallo de aviso nunca interrumpe el guardado de `data.json`.

Probarlo en tu computador:

```bash
python3 scripts/validate_data.py     # revisa el esquema (lo mismo que corre en cada PR)
cp data.json /tmp/anterior.json      # foto anterior, para comparar
python3 monitor.py                   # genera data.json
python3 scripts/alertas.py --anterior /tmp/anterior.json   # detecta alertas y escribe alertas.json
python3 -m http.server 8000          # abre http://localhost:8000
```

## Advertencia

Las direcciones marcadas como "desvío" son destinos de fondos que salieron de billeteras de OrionX. Quién las controla solo puede establecerlo la Fiscalía. Este monitor no acusa a nadie: documenta movimientos públicos para que los afectados y las autoridades tengan la misma información.

Licencia: dominio público (CC0 1.0, ver `LICENSE`). Copia, modifica y comparte sin pedir permiso.

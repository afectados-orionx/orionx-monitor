# Monitor de billeteras OrionX

**Página en vivo: https://afectados-orionx.github.io/orionx-monitor/**

Muestra saldo, valor en pesos y última actividad de las billeteras vinculadas a OrionX en Bitcoin, XRP, Tron, Litecoin, Ethereum, BSC y Polygon, y registra cada movimiento con fecha y hora. Se actualiza sola cada hora. Tiene cinco pestañas: **Resumen** (en lenguaje simple), **Billeteras vigiladas**, **Atribuciones** (todas las direcciones atribuidas a OrionX por afectados, con nivel de confianza, tipo de evidencia y nuestra verificación en cadena), **Precios al cierre** (última operación de cada mercado en OrionX el 3 de septiembre de 2026) y **Movimientos**. Lo mantienen clientes afectados por el cierre del 3 de septiembre de 2026; no tiene relación con la empresa.

Todo es verificable: cada dirección enlaza a su explorador público y `direcciones.json` anota qué transacción la vincula a OrionX.

## Ten tu propia copia (10 minutos, gratis, sin servidor)

Cuantas más copias existan, más difícil es que el registro desaparezca. Cada copia consulta y guarda los datos por su cuenta.

1. Crea una cuenta en github.com si no tienes.
2. Arriba a la derecha de esta página pulsa **Fork** y confirma. Ya tienes tu copia en `github.com/TU_USUARIO/orionx-monitor`.
3. En tu copia: **Settings → Pages → Source: "Deploy from a branch" → Branch: `main`, carpeta `/ (root)` → Save**. En dos minutos tu página estará en `https://TU_USUARIO.github.io/orionx-monitor/`.
4. **Settings → Actions → General → Workflow permissions → marca "Read and write permissions" → Save.** Sin esto el robot no puede guardar los datos.
5. Pestaña **Actions**. Si aparece un aviso para habilitar workflows, acéptalo. Entra en **monitor → Run workflow → Run workflow**. Desde ahí corre sola cada hora.

Opcional, avisos a Discord: un administrador del servidor crea un webhook (Ajustes del canal → Integraciones → Webhooks → Nuevo webhook → Copiar URL). En tu copia: **Settings → Secrets and variables → Actions → New repository secret**, nombre `DISCORD_WEBHOOK`, valor la URL. Cada movimiento detectado se publicará en ese canal.

Para recibir las billeteras nuevas que se agreguen aquí, en tu copia pulsa **Sync fork → Update branch** de vez en cuando.

## Aportar una billetera

Si reconoces una dirección del monitor como tuya (por ejemplo, un retiro propio), avisa y se retira. Las direcciones retiradas quedan registradas en `direcciones.json` con `descartada: true` y el motivo, para no volver a agregarlas y para dejar constancia.

Solo se agregan direcciones con una transacción pública que las ancle a OrionX (un retiro que la empresa te pagó, un depósito que le hiciste, o una salida desde una billetera ya confirmada). Abre un **Issue** en este repositorio con: red, dirección, el hash de esa transacción y una frase de qué es. No pongas datos personales.

Si sabes editar JSON, propón el cambio directamente en **`direcciones.json`** con un Pull Request (ver `CONTRIBUTING.md`). Es el único archivo que se edita a mano. Campos de un registro: `red` (BTC, XRP, TRX, LTC, ETH, BSC, POLYGON — las direcciones EVM van en minúsculas), `direccion`, `monitorear` (true = se consulta cada hora), `descartada` (true = registro de retirada), `estado` (`monitor` / `evaluacion` / `relacionada` / `descartada`), `tipo`, `etiqueta`, `nota`, y los de atribución (`rol`, `confianza`, `evidencia`, `verificada`, `liga_confirmada`, `liga_indirecta`, `etiqueta_publica`, `saldo_observado`, `moneda`). Tipos: `orionx` (billetera de la empresa, confirmada o con transacción directa con una confirmada), `atribuida` (saldo relevante con liga solo indirecta; se vigila pero no se afirma que sea de OrionX), `desvio` (destino de fondos salidos de OrionX), `querella` (citada en la querella), `puente` (recolección o paso histórico de fondos).

**Criterio para pasar de "atribuida" o "en evaluación" a `orionx`:** una transacción pública directa con una billetera ya confirmada, o una etiqueta pública en un explorador (xrpscan, etherscan). `direcciones.json` guarda todas las direcciones propuestas con su confianza, evidencia y estado; la pestaña Atribuciones lo muestra. Las que no cumplen el criterio quedan con `monitorear: false` y `estado: evaluacion`, para no meter ruido en la investigación.

## Cómo funciona

- `direcciones.json` es la **fuente única** de direcciones: monitoreadas, en evaluación y descartadas, todo en un archivo. `scripts/validate_data.py` revisa el esquema en cada Pull Request.
- `monitor.py` (Python, sin dependencias) lee de `direcciones.json` las que tienen `monitorear: true` y consulta mempool.space, xrpscan, tronscan, blockcypher y nodos RPC públicos, más precios de CoinGecko. Compara con el `data.json` anterior y anota los cambios en `historial.jsonl`.
- `.github/workflows/monitor.yml` lo ejecuta cada hora en GitHub Actions y guarda el resultado en el repositorio (con `git pull --rebase` antes del push, para no fallar si se mergeó un PR en el intertanto).
- `index.html` lee `data.json` (monitor), `direcciones.json` (direcciones propuestas, su verificación y las descartadas) y `precios_cierre.json` (último libro de órdenes, transcrito del informe de un afectado) y dibuja la página. No hay servidor ni base de datos.
- Un movimiento se registra si vale al menos **US$ 1** (≈1.000 CLP) al precio del momento, en cualquier moneda (variable de entorno `UMBRAL_USD` para cambiarlo). Así se detectan también retiros goteados en microtransacciones: como se compara el saldo entre un chequeo y el siguiente, muchas transferencias pequeñas dentro de la hora se suman. Si CoinGecko no responde, se usa un mínimo en unidades por moneda. Los cambios menores suelen ser redondeos de las APIs. Si cambia el número de transacciones sin que el saldo pase el umbral, igual se anota, siempre que también haya cambiado la fecha de la última transacción (los contadores de algunos exploradores oscilan sin que haya transacciones nuevas).
- Si una API de saldos falla, se conserva el último dato y la página lo indica. Si CoinGecko no responde, se reutilizan los precios del `data.json` anterior y la página avisa "precios sin actualizar" (antes quedaba todo en $0). Las APIs gratuitas aguantan sin problema una consulta por hora; no bajes el cron a menos de 30 minutos.
- Avisos a Discord: un solo POST por tanda, sin reintentos (antes se enviaba tres veces). Un fallo de aviso nunca interrumpe el guardado de `data.json`.

Probarlo en tu computador:

```bash
python3 scripts/validate_data.py     # revisa el esquema (lo mismo que corre en cada PR)
python3 monitor.py                   # genera data.json
python3 -m http.server 8000          # abre http://localhost:8000
```

## Advertencia

Las direcciones marcadas como "desvío" son destinos de fondos que salieron de billeteras de OrionX. Quién las controla solo puede establecerlo la Fiscalía. Este monitor no acusa a nadie: documenta movimientos públicos para que los afectados y las autoridades tengan la misma información.

Licencia: dominio público (CC0 1.0, ver `LICENSE`). Copia, modifica y comparte sin pedir permiso.

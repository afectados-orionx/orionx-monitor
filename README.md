# Monitor de billeteras OrionX

**Página en vivo: https://afectados-orionx.github.io/orionx-monitor/**

Muestra saldo, valor en pesos y última actividad de las billeteras vinculadas a OrionX en Bitcoin, XRP, Tron, Litecoin, Ethereum, BSC y Polygon, y registra cada movimiento con fecha y hora. Se actualiza sola cada hora. Tiene cinco pestañas: **Resumen** (en lenguaje simple), **Billeteras vigiladas**, **Atribuciones** (todas las direcciones atribuidas a OrionX por afectados, con nivel de confianza, tipo de evidencia y nuestra verificación en cadena), **Precios al cierre** (última operación de cada mercado en OrionX el 3 de septiembre de 2026) y **Movimientos**. Lo mantienen clientes afectados por el cierre del 3 de septiembre de 2026; no tiene relación con la empresa.

Todo es verificable: cada dirección enlaza a su explorador público y `billeteras.json` anota qué transacción la vincula a OrionX.

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

Si reconoces una dirección del monitor como tuya (por ejemplo, un retiro propio), avisa y se retira. Las direcciones retiradas quedan en `descartadas.json` con el motivo, para no volver a agregarlas.

Solo se agregan direcciones con una transacción pública que las ancle a OrionX (un retiro que la empresa te pagó, un depósito que le hiciste, o una salida desde una billetera ya confirmada). Abre un **Issue** en este repositorio con: red, dirección, el hash de esa transacción y una frase de qué es. No pongas datos personales.

Si sabes editar JSON, puedes proponer el cambio directamente en `billeteras.json` con un Pull Request. Campos: `red` (BTC, XRP, TRX, LTC, ETH, BSC, POLYGON), `direccion`, `etiqueta`, `tipo`, `vigilar` (true/false), `nota`. Tipos: `orionx` (billetera de la empresa, confirmada o con transacción directa con una confirmada), `atribuida` (saldo relevante con liga solo indirecta; se vigila pero no se afirma que sea de OrionX), `desvio` (destino de fondos salidos de OrionX), `querella` (citada en la querella), `puente` (recolección o paso histórico de fondos).

**Criterio para pasar de "atribuida" o "en evaluación" a `orionx`:** una transacción pública directa con una billetera ya confirmada, o una etiqueta pública en un explorador (xrpscan, etherscan). `atribuciones.json` guarda todas las direcciones propuestas con su confianza, evidencia y estado; la pestaña Atribuciones lo muestra. Las que no cumplen el criterio quedan ahí en evaluación y no entran a `billeteras.json`, para no meter ruido en la investigación.

## Cómo funciona

- `monitor.py` (Python, sin dependencias) consulta mempool.space, xrpscan, tronscan, blockcypher y nodos RPC públicos, más precios de CoinGecko. Compara con el `data.json` anterior y anota los cambios en `historial.jsonl`.
- `.github/workflows/monitor.yml` lo ejecuta cada hora en GitHub Actions y guarda el resultado en el repositorio.
- `index.html` lee `data.json` (monitor), `atribuciones.json` (direcciones propuestas y su verificación) y `precios_cierre.json` (último libro de órdenes, transcrito del informe de un afectado) y dibuja la página. No hay servidor ni base de datos.
- Los movimientos menores a 0,001 unidades (o 0,5 USDT) no se registran: suelen ser redondeos de las APIs.
- Si una API falla, se conserva el último dato y la página lo indica. Las APIs gratuitas aguantan sin problema una consulta por hora; no bajes el cron a menos de 30 minutos.

Probarlo en tu computador:

```bash
python3 monitor.py            # genera data.json
python3 -m http.server 8000   # abre http://localhost:8000
```

## Advertencia

Las direcciones marcadas como "desvío" son destinos de fondos que salieron de billeteras de OrionX. Quién las controla solo puede establecerlo la Fiscalía. Este monitor no acusa a nadie: documenta movimientos públicos para que los afectados y las autoridades tengan la misma información.

Licencia: dominio público (CC0). Copia, modifica y comparte sin pedir permiso.

# Cómo aportar

Todo el registro de direcciones vive en un solo archivo: **`direcciones.json`**
(monitoreadas, en evaluación y descartadas, todo junto).

Antes de abrir el Pull Request, corre:

```bash
python scripts/validate_data.py       # revisa el esquema; falla si algo no cuadra
```

En el PR corre solo el workflow `validar` (JSON bien formado + `validate_data.py`).

## Agregar una dirección para vigilar

Requisito: una transacción pública que la ancle a OrionX (un retiro que la
empresa pagó, un depósito que se le hizo, o una salida desde una billetera ya
confirmada). Añade un objeto al array `direcciones` de `direcciones.json`:

```json
{
 "red": "BTC",
 "direccion": "bc1q…",
 "monitorear": true,
 "descartada": false,
 "tipo": "orionx",
 "estado": "monitor",
 "vigilar": true,
 "etiqueta": "OrionX: …",
 "nota": "Qué es y la tx que la ancla (hash).",
 "origen": "aporte de …, verificado en cadena",
 "rol": "hot wallet",
 "confianza": "confirmada",
 "evidencia": "directa",
 "nota_original": "",
 "seccion": "orionx",
 "verificada": true,
 "liga_confirmada": true,
 "liga_indirecta": false,
 "etiqueta_publica": null,
 "saldo_observado": null,
 "moneda": "BTC",
 "motivo": "",
 "estaba_como": null,
 "retirada": null
}
```

- Direcciones EVM (ETH/BSC/POLYGON): **en minúsculas**. La misma dirección en
  varias cadenas EVM = un registro por cada `red`.
- `tipo`: `orionx` | `desvio` | `querella` | `puente` | `atribuida`.
- `monitorear: true` ⟺ `estado: "monitor"` (lo consulta `monitor.py` cada hora).
- Si la liga es solo indirecta y no quieres afirmar que es de OrionX todavía:
  `tipo: "atribuida"`, igual con `monitorear: true`.
- Si aún no cumple el criterio para vigilar: `monitorear: false`,
  `estado: "evaluacion"`.
- Las filas que solo van a la pestaña Atribuciones necesitan `rol` no vacío.

## Descartar una dirección

Cuando alguien acredita que una dirección es suya (un retiro propio, por
ejemplo), no se borra: se marca como descartada, con el motivo.

Si ya estaba en el archivo, **edita su registro** (no crees otro):
`monitorear` → `false`, `descartada` → `true`, `estado` → `"descartada"`, y
añade `motivo` (obligatorio) y `retirada`. Ejemplo de registro descartado:

```json
{
 "red": "BTC",
 "direccion": "bc1q…",
 "monitorear": false,
 "descartada": true,
 "estado": "descartada",
 "estaba_como": "desvio · Destino de … BTC desde retiros",
 "retirada": "2026-09-09",
 "motivo": "Descartada el …: un cliente de OrionX acreditó que …"
}
```

## Direcciones descubiertas por el monitor (`descubiertas.json`)

Desde el 15-sep-2026 `monitor.py` propone solo direcciones a partir de movimientos
reales y las guarda en **`descubiertas.json`** (lo escribe el robot; no se edita en
un PR salvo los campos `seguir` y `motivo`). Cada registro dice de dónde salió:

- `misma_billetera: true` → en BTC/LTC gastó en la misma transacción que una
  dirección vigilada (misma llave) o recibió el posible vuelto. Es la señal más
  fuerte que existe fuera de una confesión; el monitor la sigue (`seguir: true`)
  y aparece en la tabla como "Descubierta".
- `misma_billetera: false` → fue destino de una salida. Puede ser un cliente, un
  exchange o cualquiera: no debe promoverse sin más prueba.

Desde el 17-sep-2026 un destino **se empieza a vigilar solo** (`seguir: true`,
con el porqué en `seguir_motivo`) cuando recibe **US$ 10.000 o más**
(`UMBRAL_SEGUIR_USD`) de una dirección del caso, no tiene etiqueta pública de
exchange y está a **dos saltos o menos** (`salto: 1` = destino directo de una
dirección de la lista; `MAX_SALTOS`). Vigilar es solo consultar su saldo y
avisar si mueve: **no** es afirmar que sea del caso, y no la mete en
`direcciones.json`. El tope sigue siendo `MAX_SEGUIDAS`.

Una EOA con **delegación EIP-7702** (código `0xef0100…`: billetera que paga la
comisión de red con el token) tiene código pero no es un contrato, y se descubre
como cualquier otra cuenta. El campo `motivo` anota a qué contrato delega.

Para pasar una descubierta a `direcciones.json`: crear el registro normal (ver
arriba) citando el `hash` que trae `descubiertas.json` como evidencia, y con el
tipo que corresponda (`orionx` si es misma billetera de una `orionx`; `desvio`
si es destino de una salida que no volvió a moverse y no tiene etiqueta pública
de exchange). El registro de `descubiertas.json` se deja: el monitor deja de
listarlo solo cuando la dirección ya está en `direcciones.json`.

Cuidado con el **envenenamiento de direcciones**: los estafadores mandan
transferencias de valor cero y tokens falsos desde direcciones que empiezan y
terminan igual que las reales. El monitor ya descarta los tokens sin precio por
contrato, pero al copiar una dirección desde un explorador hay que comparar los
40 caracteres, no solo los extremos.

## Checklist de revisión (para quien mergea)

- [ ] `python scripts/validate_data.py` pasa.
- [ ] Hay una tx pública citada que ancla la dirección (o motivo claro si es descartada).
- [ ] `red` es una de las 7 soportadas; dirección EVM en minúsculas.
- [ ] No se repite `(red, direccion)`.
- [ ] Ningún campo de texto trae `<` o `>` (se renderiza en la web sin escapar).
- [ ] `monitorear` y `descartada` no están los dos en `true`.
- [ ] No se borró ningún registro existente (una descartada se marca, no se elimina).

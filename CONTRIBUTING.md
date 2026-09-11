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

## Checklist de revisión (para quien mergea)

- [ ] `python scripts/validate_data.py` pasa.
- [ ] Hay una tx pública citada que ancla la dirección (o motivo claro si es descartada).
- [ ] `red` es una de las 7 soportadas; dirección EVM en minúsculas.
- [ ] No se repite `(red, direccion)`.
- [ ] Ningún campo de texto trae `<` o `>` (se renderiza en la web sin escapar).
- [ ] `monitorear` y `descartada` no están los dos en `true`.
- [ ] No se borró ningún registro existente (una descartada se marca, no se elimina).

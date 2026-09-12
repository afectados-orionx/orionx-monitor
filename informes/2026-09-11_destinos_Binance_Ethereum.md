# Destinos en Binance de las billeteras OrionX en Ethereum (versión pública)

**Fecha del análisis:** 11 de septiembre de 2026
**Alcance:** Ethereum mainnet. ETH nativo, USDT (ERC-20) y USDC (ERC-20).
**Motivo:** La querella de Orionx SpA (RUC 2600661816-1, 4° Juzgado de Garantía de
Santiago), reseñada por *La Tercera/Pulso* el 11 sep 2026, afirma que la cuenta
"Trezor Orionx Cold Wallet" realizó **múltiples envíos directos** hacia carteras
etiquetadas "Luis Zibert" e "Incremental" **en Binance**, acumulando **187 ETH,
4.146.643 USDT y 200.000 USDC**. Este informe busca esos movimientos en cadena.

Todo lo que aquí se atribuye a la querella es **según la querella** y según el
informe pericial que la empresa encargó. Los querellados no han sido
formalizados. Las direcciones de destino se etiquetan por su función en cadena
("depósito Binance", "depósito de exchange"), nunca con el nombre de una persona.

> **Versión pública (12 sep 2026).** Este documento es la versión publicable del
> informe de trabajo del grupo. Muestra únicamente las direcciones que el monitor
> público vigila (billeteras de OrionX, atribuidas y los destinos agregados el 11
> sep) y las dos billeteras calientes de Binance con etiqueta pública. Las demás
> direcciones de destino se reemplazaron por códigos `D-01`, `D-02`, … porque son,
> en su mayoría, direcciones de depósito de clientes en exchanges: publicarlas
> expondría a afectados. Los totales, fechas y conteos se conservan; los hashes
> que llevan a una dirección codificada también se reservan. La versión completa,
> con las 28 direcciones codificadas y sus hashes, queda a disposición de la
> Fiscalía y de los abogados de los afectados. Nada en este informe identifica a
> personas; "depósito Binance" describe una función en cadena, no un titular.
>
> **Reproducible:** los scripts que generan este análisis están en `scripts/destinos/`
> de este mismo repositorio (solo Python estándar, sin claves de API). Cualquiera
> puede repetir la descarga y obtener las mismas tablas.

---

## Resumen ejecutivo

1. **No se localizó en Ethereum la combinación exacta de la querella.** Ninguna
   dirección conocida de OrionX, ni ninguna combinación de una o dos direcciones
   de depósito de Binance alcanzadas desde ellas, suma 187 ETH + 4.146.643 USDT +
   200.000 USDC. El mejor ajuste queda a más del 100 % de error en algún activo.
2. **Sí se reconstruyó completo el circuito EVM de OrionX**: un dispensador de gas
   (`0xdf9390…`) alimenta ~1.100 direcciones de depósito por cliente, que barren a
   la central `0x0c827a…`, que abastece a la billetera caliente `0x5528d8…`, desde
   la que salen los retiros. 32 direcciones analizadas, 6.419 destinos agregados.
3. **Desde ese circuito salieron hacia depósitos de Binance ≈6.004 ETH,
   ≈39,9 M USDT y ≈1,42 M USDC** repartidos en **123 direcciones de depósito**
   distintas. La mayoría son retiros normales de clientes a su cuenta de Binance:
   la cifra agregada **no** es, por sí sola, indicio de desvío.
4. **El canal más grande y más anómalo es `0xe93a2ab5…`**, depósito de Binance
   (barre a Binance 14) que recibió **108 ETH + 26,81 M USDT + 1,08 M USDC** en
   298 transferencias, desde **tres** direcciones de OrionX a la vez (caliente,
   central y operativa), entre el 1-nov-2024 y el 24-ago-2026. Es el primer
   destino que la Fiscalía debería oficiar a Binance.
5. Otros depósitos de Binance relevantes: `0x398781cc…` (8,85 M USDT desde el
   5-ago-2025) y `D-14` (2,92 M USDT). `0x398781cc…` y `0x4def7506…`
   arrancan **el mismo día**, 5-ago-2025, tres semanas antes de que la empresa
   dijera haber detectado el descalce (25-ago-2025).
6. **Salidas directas a billeteras calientes de Binance** desde la dirección con
   etiqueta pública "Orionx 1" (`0xafda8eba…`): 460,23 ETH a Binance 1 (2021) y
   4,95 ETH + 497.222 USDT a Binance 14 (2021-2023).
7. **Tres destinos grandes sin etiqueta** (`0x4def7506…` 14,04 M USDT,
   `0xad1618f3…` 9,85 M USDT, `D-24` 5,24 M USDT) reenvían a racimos de
   direcciones con sufijo repetido: patrón propio de redes OTC de stablecoins.
   Ahí conviene pedir trazabilidad a Tether, no solo a Binance.
8. **Hallazgos nuevos de estructura:** `0x5557e7ee…` es la billetera caliente
   anterior (2018-2021, fondeada por Kraken 4 con 2.587 ETH, entregó 497 ETH a
   `0x5528d8…`); `0x3f8f72ff…` aportó 6.750 ETH a la central; `0xb72ae936…` es un
   **contrato de depósito de Kraken** (creado por "Kraken: Deployer 2").
9. **Falso positivo detectado:** `0x36da0bfe…`, hoy en evaluación en el monitor,
   mueve **miles de millones** de USDT/USDC e interactúa con Circle. No es de
   OrionX; se propone marcarla descartada.
10. **Qué falta:** la "Trezor Orionx Cold Wallet" no aparece en Ethereum con esos
    montos. Hay que buscarla en BSC/Polygon/Tron, o pedirla directamente por
    oficio a Fireblocks y a la propia querellante, que la tiene identificada.

---

## 1. Método

Descarga y agregación con `descargar_y_agregar.py` (solo stdlib, caché en
`datos/`):

- **Routescan** (API compatible con Etherscan, sin clave) para el listado
  completo de transacciones (`txlist`) y de transferencias ERC-20 (`tokentx`,
  filtradas por contrato de USDT y USDC), paginando por cursor de bloque.
- **Blockscout v2** (sin clave) para saber si una dirección es contrato y para
  sus contadores.
- Etiquetas públicas: instantánea comunitaria del etiquetado de Etherscan
  (`brianleect/etherscan-labels`, 29.772 direcciones), guardada en
  `datos/etherscan_labels.json`. **Es una copia, no la fuente oficial**: cada
  etiqueta debe confirmarse en etherscan.io antes de citarse en un escrito.
- Clasificación de destinos (`clasificar_todo.py`): se mira el **siguiente salto**
  de cada destino. Si barre a una hot wallet conocida de Binance → "depósito
  Binance"; si barre a una hot wallet etiquetada de otro exchange → "depósito de
  exchange"; si tiene etiqueta pública de exchange → hot wallet de exchange.

Se descargaron las **20 direcciones ETH** del monitor más **12 direcciones
vecinas** detectadas durante el trabajo. Total: 32 orígenes, 6.419 destinos
distintos, de los cuales se clasificaron los 406 con ≥5 ETH o ≥50.000 USDT/USDC.

Contratos, etiquetas y datos crudos quedan en `datos/`; el agregado por par
origen→destino en `agregados.json`; la clasificación en `clasificacion.json`.

## 2. El circuito de OrionX en Ethereum

```
0xdf9390b8…  dispensador de gas  ──0,002 ETH──►  ~1.122 direcciones de depósito por cliente
                                                        │ (barrido)
0x3f8f72ff…, `D-09`, `D-15`, `D-18`  ────┤
                                                        ▼
                                        0x0c827a96…  CENTRAL DE DEPÓSITOS
                                                        │ 12.220 ETH · 29,8 M USDT · 15,2 M USDC
                                                        ▼
                                        0x5528d824…  BILLETERA CALIENTE
                                                        │ 5.122 destinos
                     ┌──────────────────────────────────┼────────────────────────────┐
                     ▼                                  ▼                            ▼
        retiros de clientes            depósitos en exchanges        cadenas OTC sin etiqueta
      (miles de direcciones)        (Binance, Bitfinex, Kraken…)     (0x4def7506…, 0xad1618f3…)
```

Reservas / posible almacenamiento en frío: `0x3892c819…` (recibió 163,90 ETH de
la central en nov-2025 y may-2026, devolvió 41,83 ETH) y `0x594cd3f2…` (recibió
56,54 ETH de la central y 45,06 ETH de `D-01` el 29-jul-2026 y **no ha
gastado nada**). Ninguna de las dos envió jamás a Binance.

## 3. Totales de salida por dirección de origen

| Origen | Rol | Destinos | ETH | USDT | USDC |
|---|---|---:|---:|---:|---:|
| [0x5528d824…](https://etherscan.io/address/0x5528d82423d91da8e8fe8066fab15cc014ebd5e2) | caliente | 5.122 | 13.066,59 | 113.070.873 | 16.917.928 |
| [0x0c827a96…](https://etherscan.io/address/0x0c827a9651630be28444d9f6ee21d997f2f3d272) | central depósitos | 13 | 12.452,71 | 33.139.246 | 15.258.489 |
| [0x551189f8…](https://etherscan.io/address/0x551189f8531a88f2083077b70176a86915797a14) | recolector | 2 | 36,42 | 22.029.790 | 338.864 |
| [0x5a19332e…](https://etherscan.io/address/0x5a19332e8ee918bcab9d28ffa0be3ef304424b78) | en evaluación | 12 | 0,64 | 9.320.188 | 5.707.799 |
| [0x4b413bdf…](https://etherscan.io/address/0x4b413bdf16ebc8bb5a05855608f1c71f25634c2a) | en evaluación | 1 | 0,00 | 9.183.392 | 9.644.160 |
| [0xbc1eff8e…](https://etherscan.io/address/0xbc1eff8eae5a523b02d5139491b114e080b2c1c5) | en evaluación | 1 | 0,00 | 0 | 5.119.543 |
| [0xc48485c2…](https://etherscan.io/address/0xc48485c211842437db9d4f0092024b7411cc1ec0) | atribuida | 1 | 1.848,69 | 3.930.259 | 88.129 |
| [0xb349689d…](https://etherscan.io/address/0xb349689dc6db306a35af244a47c1a67374ae32b9) | en evaluación | 1 | 0,00 | 2.891.550 | 0 |
| [0xb6184e64…](https://etherscan.io/address/0xb6184e6403c517f27c39a95e0fb635929495d828) | en evaluación | 2 | 0,00 | 2.112.235 | 0 |
| [0xafda8eba…](https://etherscan.io/address/0xafda8eba0ac933661f45b41a438840dc07df1761) | "Orionx 1" | 2 | 465,18 | 497.222 | 0 |
| [0x93afb95f…](https://etherscan.io/address/0x93afb95fa151e2d7848a007ce1c9d9b77eb4db2e) | en evaluación | 1 | 139,82 | 0 | 0 |
| [0x3892c819…](https://etherscan.io/address/0x3892c819bb3995515fe7b7a092c860238a92279d) | atribuida (reserva) | 1 | 41,83 | 0 | 0 |
| [0x1028ffd6…](https://etherscan.io/address/0x1028ffd61ba8ae40f65127cd7461c636f3075d4c) | operativa | 4 | 0,93 | 35.090 | 51.814 |
| [0x6bf3db49…](https://etherscan.io/address/0x6bf3db49f7a014f463c03b0560353549c2788fa2) | en evaluación | 1 | 0,00 | 200.000 | 0 |
| [0xdabb47be…](https://etherscan.io/address/0xdabb47be57b62caa8e17e4a3fff30468dd02f49f) | en evaluación | 3 | 4,94 | 0 | 0 |
| [0xdf9390b8…](https://etherscan.io/address/0xdf9390b86e365602d22eda5797670e49a9a69cee) | dispensador de gas | 1.122 | 3,13 | 0 | 0 |
| [0x594cd3f2…](https://etherscan.io/address/0x594cd3f2f43c9121c72398610ebc792953f7c592) | atribuida (reserva) | 0 | 0,00 | 0 | 0 |
| [0xb964bd2a…](https://etherscan.io/address/0xb964bd2a238c7e59125032a0585fa8c21ed2f529) | en evaluación | 0 | 0,00 | 0 | 0 |
| [0xb72ae936…](https://etherscan.io/address/0xb72ae9366865e58f240ca42399df3fe8340fdd1e) | **contrato de depósito Kraken** | 0 | 0,00 | 0 | 0 |
| [0x36da0bfe…](https://etherscan.io/address/0x36da0bfe6e0cb2d84ee84b1d832e5b1693b76448) | **ajena (ver §7)** | 305 | 4,14 | 6.427.711.808 | 14.712.786.479 |

Direcciones vecinas incorporadas durante el análisis (no estaban en el monitor):

| Dirección | Qué es | Salidas |
|---|---|---|
| [0x5557e7ee…](https://etherscan.io/address/0x5557e7ee0effb154afe78d4ecaf5ff5fa1e948ab) | billetera caliente **anterior** (2018-2021) | 3.018,88 ETH a 198 destinos |
| [0x3f8f72ff…](https://etherscan.io/address/0x3f8f72ff8b6ea36c597477aebe2bd88ed4b93d17) | depósito/recolector | 6.750,13 ETH + 969.582 USDT + 233.968 USDC, **todo** a la central |
| `D-17`, `D-05`, `D-09`, `D-18`, `D-15`, `D-23`, `D-07`, `D-08`, `D-11`, `D-01` | depósitos de cliente que barren a la central | 100 % a `0x0c827a96…` (salvo `D-01`, que fue a la reserva `0x594cd3f2…`) |

## 4. Principales destinos, con clasificación y hash de ejemplo

Sumas de **todos** los orígenes OrionX (excluida `0x36da0bfe…`). "Depósito
Binance" = la dirección barre sus fondos a una hot wallet conocida de Binance.

| Destino | Clasificación | ETH | USDT | USDC | tx | Periodo | Hash de ejemplo |
|---|---|---:|---:|---:|---:|---|---|
| [0xe93a2ab5…](https://etherscan.io/address/0xe93a2ab58f246ca56f79438b168896e47d50372e) | depósito Binance (Binance 14) | 108,00 | 26.813.044 | 1.078.028 | 298 | 2024-11-01 → 2026-08-24 | [0x844c0475…](https://etherscan.io/tx/0x844c047534c93d72ed4aeab64b939c47a391e4179b788ec167544769868f5581) |
| [0x4def7506…](https://etherscan.io/address/0x4def7506e75aaff37f22949b6c4b9dcc2630955d) | desconocido (cadena OTC) | 0,00 | 14.040.011 | 0 | 656 | 2025-08-05 → 2026-06-10 | [0x5f1dc8b8…](https://etherscan.io/tx/0x5f1dc8b89643173de7d040c0c80886f32b3f791daaf9f90904b52803f287d76c) |
| [0xad1618f3…](https://etherscan.io/address/0xad1618f3ca51fa2030d3cdd9b16d200fa11de2d3) | desconocido (cadena OTC) | 0,00 | 9.845.918 | 0 | 98 | 2024-02-20 → 2026-02-27 | [0xdceea67d…](https://etherscan.io/tx/0xdceea67da9024df4b652799323688205b2d3fb7e774a8c5cbf2a7f9138dac1be) |
| [0x398781cc…](https://etherscan.io/address/0x398781cced85c593a60f03cf76c245877cc914c1) | depósito Binance (Binance 14) | 0,00 | 8.845.179 | 0 | 68 | 2025-08-05 → 2026-02-24 | [0xa0c19cd8…](https://etherscan.io/tx/0xa0c19cd8d903c2149879bda80b699d35199e356ca34cd85828a0191e83147d0e) |
| [0x003740c4…](https://etherscan.io/address/0x003740c4d6b77e67df0dfdb57385d46413ab2663) | depósito Bitfinex | 223,30 | 8.219.767 | 34.000 | 608 | 2024-03-21 → 2026-08-14 | [0xde3ea89e…](https://etherscan.io/tx/0xde3ea89ebdd60341fceac9764c57b93ce29c2a529807324fa6c07abc9598ac33) |
| `D-22` | contrato sin verificar | 0,00 | 6.295.097 | 0 | 61 | 2025-07-02 → 2026-06-18 | — |
| `D-24` | desconocido (cadena OTC) | 0,00 | 5.244.503 | 0 | 47 | 2024-01-18 → 2026-01-29 | — |
| `D-16` | desconocido | 0,00 | 0 | 3.705.602 | 54 | 2024-12-16 → 2025-09-09 | — |
| `D-14` | depósito Binance (Binance 14) | 0,00 | 2.915.420 | 100 | 37 | 2023-09-16 → 2024-08-04 | — |
| [0xb349689d…](https://etherscan.io/address/0xb349689dc6db306a35af244a47c1a67374ae32b9) | tránsito → `0x36da0bfe…` | 0,00 | 2.891.550 | 0 | 15 | 2025-08-13 → 2025-11-26 | [0x2ecfd9b0…](https://etherscan.io/tx/0x2ecfd9b0081eb17c6d1b74fdcc5f88ef66c8bb1b8b5a2382f7d151335f359c54) |
| `D-04` | desconocido | 0,00 | 0 | 2.742.227 | 8 | 2025-08-01 → 2025-12-30 | — |
| `D-06` | depósito Binance (Binance 1) | 860,23 | 0 | 0 | 301 | 2020-07-23 → 2023-04-14 | — |
| `D-21` | depósito Bitfinex | 0,00 | 2.501.000 | 0 | 4 | 2023-09-28 → 2025-11-06 | — |
| `D-19` | desconocido | 0,00 | 1.990.673 | 0 | 25 | 2025-10-15 → 2026-03-06 | — |
| `D-03` | depósito Binance (1 y 14) | 476,09 | 0 | 0 | 173 | 2021-04-09 → 2022-09-27 | — |
| [0x3f5ce5fb…](https://etherscan.io/address/0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be) | **hot wallet Binance 1** (directo) | 460,23 | 0 | 0 | 3 | 2021-03-23 → 2021-05-20 | [0x59492a49…](https://etherscan.io/tx/0x59492a4984831137393585699895b9ec015421e94a3b02e26e46336157615e2c) |
| `D-20` | depósito HitBTC | 446,83 | 0 | 0 | 20 | 2022-02-18 → 2024-07-09 | — |
| `D-12` | depósito Binance (1 y 14) | 421,69 | 0 | 0 | 179 | 2021-01-26 → 2022-04-04 | — |
| `D-13` | desconocido (cadena OTC) | 0,00 | 1.405.125 | 0 | 13 | 2026-06-12 → 2026-07-29 | — |
| [0x28c6c062…](https://etherscan.io/address/0x28c6c06298d514db089934071355e5743bf21d60) | **hot wallet Binance 14** (directo) | 4,95 | 497.222 | 0 | 3 | 2021-11-30 → 2023-03-28 | [0x32289e42…](https://etherscan.io/tx/0x32289e426fad80f3a3e2e3625168d78cd37113ba5ea2e7b6cdb5488792b32618) |

Enlace de traspaso entre billeteras calientes (hallazgo de estructura):
`0x5557e7ee…` → `0x5528d824…`, 497 ETH en 7 transacciones entre el 30-ene-2021 y
el 18-feb-2021, [0xe829a627…](https://etherscan.io/tx/0xe829a627f729ca2486134d8f26201e22563aafccc0205a2fc0bf8282d634b85e).

## 5. Grado de coincidencia con la querella

Objetivo: **187 ETH + 4.146.643 USDT + 200.000 USDC** desde una sola cold wallet
hacia una o dos carteras de Binance.

Se probaron tres búsquedas sobre los 6.419 destinos:

| Búsqueda | Mejor candidato | ETH | USDT | USDC | Ajuste |
|---|---|---:|---:|---:|---|
| Un solo destino, cualquier origen | `0x003740c4…` (depósito Bitfinex) | 223,3 | 8.219.767 | 34.000 | ETH +19 %, USDT +98 %, USDC −83 % → **no** |
| Par de destinos, mismo origen | ninguno bajo 60 % de error combinado | — | — | — | **no** |
| Par de depósitos de Binance (125 clasificados) | `D-14` + `D-10` | 191,7 | 2.915.420 | 100 | ETH **+2,5 %**, USDT −30 %, USDC ausente → **parcial** |

El único ajuste llamativo es el del ETH: `D-14` (depósito de Binance, 2,92
M USDT) más `D-10` (depósito de Binance, 191,7 ETH recibidos de las dos
billeteras calientes) dan 191,7 ETH frente a los 187 ETH de la querella. Es una
coincidencia de magnitud, **no una identificación**: falta un tercio del USDT y
no hay nada parecido a los 200.000 USDC. Se deja anotado para que la Fiscalía lo
contraste con el anexo del peritaje.

También se comprobó, uno a uno:

- Ningún destino recibió entre 3,0 y 5,5 M USDT salvo `D-24`
  (5.244.503 USDT, y 0 ETH y 0 USDC): no calza.
- Ningún destino recibió ~200.000 USDC junto con ETH y USDT en las proporciones
  de la querella. El más cercano en USDC es `D-28` (302.500 USDC +
  200.000 USDT, 0 ETH).
- Las dos direcciones con perfil de almacenamiento en frío del monitor
  (`0x3892c819…` y `0x594cd3f2…`) **nunca** enviaron a Binance: la primera solo
  devolvió 41,83 ETH a la central, la segunda no ha gastado nada.

**Conclusión:** con datos de Ethereum mainnet no es posible afirmar cuál es la
"Trezor Orionx Cold Wallet" ni cuáles son las dos carteras de Binance de la
querella. Las hipótesis abiertas, por orden de plausibilidad:

1. Los montos de la querella son de **otra cadena** (BSC, Polygon o Tron; el
   grueso del USDT minorista en Chile circula por Tron) o mezclan varias.
2. La cold wallet existe en Ethereum pero **no está conectada** a las 32
   direcciones ya mapeadas (una Trezor puede haberse fondeado desde un exchange
   y no desde la tesorería).
3. Las cifras provienen del **libro contable interno** reconstruido por la
   pericia y no de una suma on-chain; la querella ya advierte que hay 3.130,51
   ETH contabilizados "sin correlato transaccional público on-chain".

Lo que sí puede afirmarse: **fondos salieron desde el circuito de OrionX hacia
depósitos de Binance** por volúmenes muy superiores a los de la querella, y la
Fiscalía debe establecer cuáles de esos depósitos pertenecen a clientes y cuáles
a los querellados o a sus sociedades.

## 6. Candidatos a oficiar a Binance

Prioridad 1 — depósitos de Binance alimentados **desde varias direcciones de
OrionX a la vez** o con volumen anómalo:

| Dirección de depósito | Recibió del circuito OrionX | Periodo | Por qué |
|---|---|---|---|
| [0xe93a2ab5…](https://etherscan.io/address/0xe93a2ab58f246ca56f79438b168896e47d50372e) | 108 ETH · 26,81 M USDT · 1,08 M USDC | nov-2024 → ago-2026 | Recibe de la caliente, de la central **y** de la operativa. Ningún cliente recibe de tres billeteras de tesorería |
| [0x398781cc…](https://etherscan.io/address/0x398781cced85c593a60f03cf76c245877cc914c1) | 8,85 M USDT | ago-2025 → feb-2026 | Arranca el 5-ago-2025, 20 días antes de la detección del descalce |
| `D-14` | 2,92 M USDT | sep-2023 → ago-2024 | Recibe de la caliente y de la central |
| `D-02` | 2,64 ETH · 1,04 M USDT · 86.881 USDC | jul-2023 → may-2025 | Mezcla de tres activos, dos orígenes OrionX |
| `D-06` | 860,23 ETH | jul-2020 → abr-2023 | Recibe de la caliente **antigua** y de la actual: continuidad de titular |
| `D-03` | 476,09 ETH | abr-2021 → sep-2022 | Volumen alto sostenido |
| `D-12` | 421,69 ETH | ene-2021 → abr-2022 | Recibe de ambas calientes |
| `D-10` | 191,70 ETH (177,19 de la caliente actual + 14,47 de la anterior) | nov-2019 → jun-2022 | Único total de ETH cercano a los 187 ETH de la querella; recibe de ambas calientes. |

Prioridad 2 — envíos **directos a billeteras calientes de Binance** desde la
dirección con etiqueta pública "Orionx 1" (`0xafda8eba…`): 460,23 ETH a Binance 1
y 4,95 ETH + 497.222 USDT a Binance 14. Binance puede identificar a qué cuenta se
acreditaron.

Prioridad 3 — otros exchanges, que la querella ya pidió oficiar: depósitos de
Bitfinex (`0x003740c4…` 223,3 ETH + 8,22 M USDT; `D-21` 2,50 M USDT),
Kraken (`0xb72ae936…`, contrato de depósito creado por "Kraken: Deployer 2",
[tx de ejemplo](https://etherscan.io/tx/0xcc09138d6539ced6be2c83195d1443e3fdac5f80e1db8300e82dae129da19d23);
`D-26` 333,85 ETH; `D-25` 197,10 ETH) y HitBTC (`D-20`
446,83 ETH).

## 7. Otros hallazgos

**Cadenas OTC de stablecoins.** `0x4def7506…` (14,04 M USDT), `0xad1618f3…`
(9,85 M USDT), `D-24` (5,24 M USDT) y `D-13` (1,41 M USDT) no
tienen etiqueta pública y reenvían a decenas de direcciones cuyos últimos
caracteres se repiten (`…a86b49`, `…8295dc`, `…925023`, `…863e`): direcciones
generadas con sufijo a medida, patrón habitual de redes OTC de stablecoins. Aquí
el oficio útil es a **Tether** (congelamiento y trazabilidad de USDT) además de a
Binance.

**`0x36da0bfe…` no es de OrionX.** Está en el monitor como "en evaluación". Movió
**6.427 millones de USDT y 14.712 millones de USDC** en 305 destinos, recibe de
Circle y barre a depósitos de Binance y Coinbase. Es infraestructura de un actor
institucional de stablecoins, no una billetera de un exchange chileno. Su único
vínculo con el caso es que recibió 2.891.550 USDT en 14 transferencias desde
`0xb349689d…`, que a su vez los recibió de la caliente de OrionX entre el
13-ago-2025 y el 26-nov-2025. Se propone marcarla `descartada`.

**Coincidencia a verificar.** La querella menciona una cuenta que recibió más de
US$1,5 millones en **14 transacciones**. En Ethereum, el tramo
`0xb349689d…` → `0x36da0bfe…` son exactamente **14 transferencias** por
2.891.550 USDT (13-ago → 26-nov-2025), y el tramo
`0x5528d824…` → `D-13` son **13 transferencias** por 1.405.125 USDT
(12-jun → 29-jul-2026). Son coincidencias de forma, no identificaciones: la
Fiscalía debe establecer la titularidad.

**Ninguna de las 20 direcciones del monitor tiene etiqueta pública** en
Blockscout ni en la instantánea de etiquetas de Etherscan, y todas son cuentas
externas (EOA) salvo `0xb72ae936…`, que es un **contrato** (proxy de depósito de
Kraken, creador `D-27` = "Kraken: Deployer 2"). La etiqueta "Orionx 1" de
`0xafda8eba…` figura hoy en etherscan.io pero no en la instantánea usada aquí:
conviene guardar una captura de pantalla como prueba.

## 8. Límites del método

- **Solo Ethereum mainnet y solo tres activos**: ETH nativo, USDT y USDC ERC-20.
  No se miraron DAI, WBTC ni ningún otro token, ni BSC, Polygon, Tron, Arbitrum u
  Optimism. La dirección de depósito de Binance que un afectado aportó como
  ejemplo no aparece en este agregado justamente por eso.
- **No se leyeron transacciones internas** (llamadas de contrato que mueven ETH).
  Un envío hecho a través de un contrato no queda registrado aquí.
- La clasificación "depósito Binance" se basa en el **siguiente salto** y en una
  lista de 16 hot wallets de Binance. Si una dirección barre a una hot wallet de
  Binance que no está en la lista, queda como "desconocido".
- Solo se clasificaron los 406 destinos con ≥5 ETH o ≥50.000 USDT/USDC; los 6.013
  restantes quedan como "sin clasificar" (en conjunto, 2.444,6 ETH, 2,68 M USDT y
  390.152 USDC: son, casi con seguridad, retiros de clientes). De los 406
  clasificados, 125 son depósitos o hot wallets de Binance, 34 depósitos de otros
  exchanges, 41 contratos y 190 quedaron como "desconocido" (con 4.186 ETH,
  42,6 M USDT y 10,8 M USDC en total: es la bolsa que más conviene seguir
  depurando).
- Las etiquetas de exchange provienen de una **instantánea comunitaria** del
  etiquetado de Etherscan. Antes de citar cualquiera en un escrito judicial hay
  que confirmarla en etherscan.io y guardar la captura.
- Que una dirección sea depósito de Binance **no dice de quién es**. Solo Binance
  puede vincularla a una cuenta y a una identidad.

## 9. Qué pedir a la Fiscalía

1. **Oficio a Binance** (Binance Holdings Ltd. / su unidad de cumplimiento) por
   las direcciones de depósito de la §6, pidiendo para cada una: cuenta a la que
   se acreditaron los fondos, identidad verificada (KYC) del titular, fecha de
   apertura, IP y dispositivo de acceso, y destino posterior de los fondos.
   Señalar expresamente que son direcciones de depósito en Ethereum y adjuntar
   los hashes de la §4.
2. **Ampliar el oficio a Binance** a las direcciones `0x3f5ce5fb…` (Binance 1) y
   `0x28c6c062…` (Binance 14) con los hashes de los envíos directos desde
   `0xafda8eba…`, para que identifique la cuenta acreditada.
3. **Oficio a Tether Ltd.**: trazabilidad y eventual congelamiento del USDT que
   salió hacia `0x4def7506…`, `0xad1618f3…`, `D-24` y `D-13`
   (≈30,5 M USDT en total).
4. **Oficio a Bitfinex, Kraken y HitBTC** por `0x003740c4…`, `D-21`,
   `0xb72ae936…`, `D-26`, `D-25` y `D-20`.
5. **Oficio a Fireblocks** (ya pedido por la querellante): exportación de las
   *vaults*, de las direcciones de retiro incluidas en lista blanca y del nombre
   interno de cada una. Ahí debería estar literalmente la cuenta "Trezor Orionx
   Cold Wallet" y las carteras rotuladas en la querella, con su dirección y su
   cadena. **Sin ese dato, este informe no puede cerrarse.**
6. **Requerir a la querellante** el anexo del informe pericial con las
   direcciones y hashes que respaldan los 187 ETH / 4.146.643 USDT / 200.000
   USDC. La empresa los tiene; los afectados no.
7. **Medidas cautelares reales** sobre los saldos que aún quedan en las
   direcciones del monitor, antes de que se muevan.

---

---

## Anexo. Direcciones incorporadas al monitor

Las 7 direcciones propuestas por este análisis se incorporaron a `direcciones.json` el 11 de septiembre de 2026 (registro en `CHANGELOG.md`), y `0x36da0bfe…` quedó marcada como descartada con su motivo. Cada registro lleva su hash de ejemplo y enlace a Etherscan en la pestaña Atribuciones del monitor.

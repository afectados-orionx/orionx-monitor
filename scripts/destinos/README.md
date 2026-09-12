# Barrido de destinos: ¿a dónde salieron los fondos desde las billeteras de OrionX?

Regla del grupo: **todo lo que se publica lo puede repetir cualquiera con estas herramientas.**
Estos tres scripts generan el informe `informes/2026-09-11_destinos_Binance_Ethereum.md`.
Solo Python 3 estándar. Sin claves de API. Sin instalar nada.

## Qué hacen

1. `descargar_y_agregar.py`: baja **todas las salidas** (ETH nativo, USDT y USDC) de las
   direcciones Ethereum de OrionX que están en `direcciones.json`, y las agrupa por
   destino (suma por activo, número de tx, primera y última fecha). Guarda todo en
   `./datos/` como caché: si lo vuelves a correr, no baja lo que ya tiene.
   Fuentes: Routescan (API compatible con Etherscan, sin clave) y Blockscout v2.
2. `clasificar_todo.py`: para cada destino relevante (por defecto ≥ 5 ETH o ≥ 50.000
   USDT/USDC) mira el **siguiente salto**. Si barre a una billetera caliente conocida de
   Binance → "depósito Binance"; si barre a otra con etiqueta pública de exchange →
   "depósito de exchange"; si no → "desconocido". Resultado en `clasificacion.json`.
3. `tabla_informe.py`: arma las tablas del informe a partir de `agregados.json` y de la
   clasificación.

## Cómo correrlo

```bash
cd scripts/destinos
python3 descargar_y_agregar.py              # 20-40 min la primera vez (≈100 MB de caché)
python3 descargar_y_agregar.py 0xabc...     # agregar una dirección extra al lote
python3 clasificar_todo.py                  # clasifica los destinos relevantes
python3 tabla_informe.py > tablas.md        # tablas listas para pegar en un informe
python3 descargar_y_agregar.py --info 0x... # etiqueta pública y si es contrato
```

Las etiquetas públicas se bajan solas la primera vez desde un snapshot comunitario
del etiquetado de Etherscan (`brianleect/etherscan-labels`). **Es una copia**: antes de
citar una etiqueta en un escrito, confírmala en etherscan.io y guarda la captura.

## Reglas para publicar lo que salga

- Un destino que sea depósito de exchange **puede ser la cuenta de un cliente** que
  retiró normalmente. No publiques direcciones de destino sueltas: publica solo las que
  entren a `direcciones.json` con el criterio de `CONTRIBUTING.md` (transacción directa
  con una dirección confirmada y una razón para vigilarla). El resto va codificado
  (`D-01`, `D-02`, …) como en el informe.
- "Depósito Binance" describe una función en cadena. **No dice de quién es la cuenta.**
  Eso solo lo puede establecer el exchange ante un oficio de la Fiscalía.
- Redacción: "los fondos salieron hacia", "según la querella". Nunca nombres de personas.

## Límites conocidos

Solo Ethereum mainnet y tres activos (ETH, USDT, USDC). No lee transacciones internas
de contratos. La lista de billeteras calientes de Binance está en el script (16
direcciones); si una dirección barre a otra que no está en la lista, queda como
"desconocido". Para BSC o Polygon hay que cambiar las URL de las fuentes y los contratos
de los tokens: es la siguiente tarea abierta.

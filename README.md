# Data Contracts Tool para OpenMetadata

Herramienta en Python para crear y actualizar Data Contracts en OpenMetadata desde archivos YAML, usando la REST API oficial.

---

## Tabla de Contenidos

- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Uso del Script](#uso-del-script)
- [Estructura del archivo YAML](#estructura-del-archivo-yaml)
- [Referencia de Campos](#referencia-de-campos)
- [Ejemplos de YAMLs](#ejemplos-de-yamls)
- [Flujo Interno del Script](#flujo-interno-del-script)
- [Errores Comunes](#errores-comunes)
- [Referencia de la API](#referencia-de-la-api)

---

## Requisitos

- Python 3.10 o superior
- OpenMetadata corriendo (probado en `v1.10+`)
- Token JWT válido de OpenMetadata, o usuario/contraseña con acceso a la API

---

## Instalación

```bash
pip install requests pyyaml
```

No requiere instalar el SDK oficial de OpenMetadata. El script usa la REST API directamente con `requests`.

---

## Estructura del Proyecto

```
.
├── apply_data_contract.py       # Script principal
└── contracts/
    ├── dim_customer_contract.yaml
    ├── dim_product_contract.yaml
    └── fact_orders_contract.yaml
```

Se recomienda mantener un archivo YAML por tabla y agruparlos en una carpeta `contracts/`.

---

## Uso del Script

### Subir un contrato individual

```bash
python apply_data_contract.py \
  --yaml contracts/dim_customer_contract.yaml \
  --host http://localhost:8585 \
  --token <JWT_TOKEN>
```

### Subir todos los contratos de una carpeta

```bash
python apply_data_contract.py \
  --dir contracts/ \
  --host http://localhost:8585 \
  --token <JWT_TOKEN>
```

### Autenticarse con usuario y contraseña

```bash
python apply_data_contract.py \
  --yaml contracts/dim_customer_contract.yaml \
  --host http://localhost:8585 \
  --username admin \
  --password admin
```

### Actualizar un contrato existente

Por defecto, si el contrato ya existe el script lo omite. Para sobrescribirlo:

```bash
python apply_data_contract.py \
  --yaml contracts/dim_customer_contract.yaml \
  --host http://localhost:8585 \
  --token <JWT_TOKEN> \
  --force-update
```

### Simular sin enviar nada (dry run)

Muestra el payload JSON que se enviaría, sin hacer ningún cambio en OpenMetadata:

```bash
python apply_data_contract.py \
  --yaml contracts/dim_customer_contract.yaml \
  --host http://localhost:8585 \
  --token <JWT_TOKEN> \
  --dry-run
```

### Referencia de argumentos

| Argumento | Requerido | Descripción |
|---|---|---|
| `--yaml` | Sí (o `--dir`) | Ruta a un archivo YAML específico |
| `--dir` | Sí (o `--yaml`) | Carpeta con múltiples archivos YAML |
| `--host` | No | URL base de OpenMetadata. Default: `http://localhost:8585` |
| `--token` | Sí (o usuario/pass) | JWT token de autenticación |
| `--username` | Sí (o `--token`) | Usuario de OpenMetadata |
| `--password` | Sí (o `--token`) | Contraseña de OpenMetadata |
| `--force-update` | No | Actualiza si el contrato ya existe |
| `--dry-run` | No | Muestra el payload sin enviar nada |

---

## Estructura del Archivo YAML

Cada archivo YAML representa un contrato para una tabla específica. Solo `name` y `tableFQN` son obligatorios; el resto es opcional según el nivel de detalle deseado.

```yaml
# Campos obligatorios
name: "nombre_del_contrato"
tableFQN: "SERVICE.DATABASE.SCHEMA.TABLE"

# Campos opcionales de identificación
displayName: "Nombre legible del contrato"
description: "Descripción del propósito del contrato"
entityStatus: "Draft"   # Draft | In Review | Approved | Deprecated | Rejected | Unprocessed

# Gobierno
owners: []
reviewers: []
domains: []
dataProducts: []

# Texto libre de condiciones de uso
termsOfUse: "Descripción de los términos de uso..."

# Vigencia del contrato
effectiveFrom: "2025-01-01T00:00:00Z"
effectiveUntil: "2026-01-01T00:00:00Z"

# SLA
sla:
  unitOfTime: "Day"
  value: 1

# Columnas que el contrato garantiza
schema: []

# Reglas semánticas de negocio
semantics: []

# Referencias a TestCases existentes en OpenMetadata
qualityExpectations: []

# Reglas en formato Open Data Contract Standard (ODCS)
odcsQualityRules: []

# Tags a nivel de contrato
tags: []
```

---

## Referencia de Campos

### `name`

Identificador único del contrato. No puede contener `::`. Máximo 256 caracteres.

```yaml
name: "dim_customer_contract"
```

---

### `tableFQN`

Fully Qualified Name de la tabla en OpenMetadata. El script lo usa para resolver el `id` interno de la tabla automáticamente.

```yaml
tableFQN: "TEST.<account_id>.<glue_db>.dim_customer"
```

El FQN sigue el patrón: `SERVICIO.BASE_DE_DATOS.SCHEMA.TABLA`

---

### `entityStatus`

Estado del ciclo de vida del contrato.

| Valor | Descripción |
|---|---|
| `Draft` | En elaboración, no vigente |
| `In Review` | En proceso de revisión |
| `Approved` | Aprobado y activo |
| `Deprecated` | Obsoleto, reemplazado |
| `Rejected` | Rechazado durante la revisión |
| `Unprocessed` | Sin procesar |

```yaml
entityStatus: "Draft"
```

---

### `owners` y `reviewers`

Lista de propietarios o revisores del contrato. Pueden definirse con su FQN o con su UUID si ya se conoce.

```yaml
# Con FQN de usuario
owners:
  - fqn: "user:john.doe"

# Con FQN de equipo
owners:
  - fqn: "team:data-platform"

# Con UUID conocido
owners:
  - id: "550e8400-e29b-41d4-a716-446655440000"
    type: "user"
```

El script resuelve automáticamente el FQN a un UUID válido antes de enviar el payload.

---

### `termsOfUse`

Cadena de texto libre que describe las condiciones de uso del activo de datos.

```yaml
termsOfUse: >
  Uso permitido: analítica interna y reportería.
  Prohibido compartir con terceros sin autorización.
  Cumplimiento requerido: GDPR, política interna de datos personales.
```

---

### `sla`

Acuerdo de nivel de servicio. Define la frecuencia de actualización esperada.

```yaml
sla:
  unitOfTime: "Day"   # Millisecond | Second | Minute | Hour | Day | Week | Month | Year
  value: 1            # Entero positivo
```

---

### `schema`

Lista de columnas que el contrato garantiza. No es obligatorio incluir todas las columnas de la tabla, solo las que el contrato cubre.

```yaml
schema:
  - name: "customer_id"
    dataType: "STRING"
    dataLength: 1
    dataTypeDisplay: "string"
    fullyQualifiedName: "SERVICE.DB.SCHEMA.TABLE.customer_id"
    description: "Identificador único del cliente"
    tags: []
    children: []
```

#### Tipos de datos válidos

`STRING`, `INT`, `BIGINT`, `FLOAT`, `DOUBLE`, `BOOLEAN`, `DATE`, `DATETIME`, `TIMESTAMP`, `ARRAY`, `MAP`, `STRUCT`, `JSON`, `BINARY`, `DECIMAL`, `VARCHAR`, `CHAR`, `TEXT`, entre otros.

---

### `semantics`

Reglas de negocio expresadas en formato [JsonLogic](https://jsonlogic.com/). Se evalúan sobre los metadatos del activo (no sobre los datos mismos).

```yaml
semantics:
  - name: "customer_id no nulo"
    description: "El identificador de cliente no puede ser nulo"
    rule: '{"!=": [{"var": "customer_id"}, null]}'

  - name: "Descripción obligatoria"
    description: "La tabla debe tener una descripción documentada"
    rule: '{"!=": [{"var": "description"}, null]}'

  - name: "Propietario asignado"
    description: "La tabla debe tener al menos un owner"
    rule: '{"and":[{"some":[{"var":"owners"},{"!=":[{"var":"fullyQualifiedName"},null]}]}]}'
```

---

### `qualityExpectations`

Referencias a TestCases ya existentes en OpenMetadata. Se obtienen una vez creados los tests desde la UI o la API.

```yaml
qualityExpectations:
  - id: "uuid-del-test-case"
    type: "testCase"
```

Para obtener el UUID de un test existente:

```bash
curl http://localhost:8585/api/v1/dataQuality/testCases/name/<TEST_FQN> \
  -H "Authorization: Bearer <TOKEN>"
```

---

### `tags`

Tags a nivel del contrato completo (no de columnas individuales). Usan el FQN del tag en OpenMetadata.

```yaml
tags:
  - tagFQN: "Certification.Gold"
    labelType: "Manual"
    state: "Confirmed"
    source: "Classification"
```

---

## Ejemplos de YAMLs

### Contrato mínimo (solo campos obligatorios)

```yaml
name: "dim_customer_contract_minimal"
tableFQN: "TEST.<account_id>.<glue_db>.dim_customer"
entityStatus: "Draft"
```

### Contrato completo — dim_customer

```yaml
name: "dim_customer_contract"
displayName: "Contrato - dim_customer"
description: >
  Contrato de datos para la tabla de dimensión de clientes.
  Consolida información de múltiples fuentes: VTEX Jumbo/SISA,
  VTEX Easy, Commercetools, Loyalty y Cencopay.
entityStatus: "Draft"
tableFQN: "TEST.<account_id>.<glue_db>.dim_customer"

owners: []
reviewers: []
domains: []
dataProducts: []

termsOfUse: >
  Uso permitido: analítica interna y reportería regional.
  Prohibido compartir con terceros sin autorización.
  Cumplimiento: Política interna de datos personales Cencosud.

sla:
  unitOfTime: "Day"
  value: 1

schema:
  - name: "customer_id"
    dataType: "STRING"
    dataLength: 1
    dataTypeDisplay: "string"
    fullyQualifiedName: "TEST.<account_id>.<glue_db>.dim_customer.customer_id"
    description: "Identificador único del cliente consolidado entre fuentes"
    tags: []
    children: []

  - name: "mail_vtex_jumbo_sisa"
    dataType: "STRING"
    dataLength: 1
    dataTypeDisplay: "string"
    fullyQualifiedName: "TEST.<account_id>.<glue_db>.dim_customer.mail_vtex_jumbo_sisa"
    description: "Email del cliente en VTEX Jumbo SISA"
    tags: []
    children: []

  - name: "has_ot_sm"
    dataType: "BOOLEAN"
    dataLength: 1
    dataTypeDisplay: "boolean"
    fullyQualifiedName: "TEST.<account_id>.<glue_db>.dim_customer.has_ot_sm"
    description: "Indica si el cliente tiene opt-in en Supermercados"
    tags: []
    children: []

  - name: "load_dts_dim_ct_sm"
    dataType: "DATE"
    dataLength: 1
    dataTypeDisplay: "date"
    fullyQualifiedName: "TEST.<account_id>.<glue_db>.dim_customer.load_dts_dim_ct_sm"
    description: "Fecha de carga del registro desde la fuente SM"
    tags: []
    children: []

semantics:
  - name: "customer_id no nulo"
    description: "El identificador de cliente no puede ser nulo"
    rule: '{"!=": [{"var": "customer_id"}, null]}'

  - name: "Descripción obligatoria"
    description: "La tabla debe tener una descripción documentada"
    rule: '{"!=": [{"var": "description"}, null]}'

qualityExpectations: []
odcsQualityRules: []
tags: []
```

---

## Flujo Interno del Script

```
apply_data_contract.py
│
├── 1. Autenticación
│     ├── --token      → usa directamente
│     └── --username / --password → POST /api/v1/users/login → obtiene JWT
│
├── 2. Health check
│     └── GET /api/v1/system/status
│
├── 3. Por cada archivo YAML
│     ├── Leer y parsear YAML
│     ├── GET /api/v1/tables/name/{tableFQN}  → resuelve table.id
│     ├── Resolver owners → GET /api/v1/users/name/{fqn} o /teams/name/{fqn}
│     ├── Construir payload (CreateDataContract)
│     │
│     ├── GET /api/v1/dataContracts?entityId={table.id}
│     │     ├── No existe → POST /api/v1/dataContracts
│     │     ├── Existe + --force-update → PUT /api/v1/dataContracts/{id}
│     │     └── Existe sin --force-update → omite con advertencia
│     │
│     └── Reporta ✅ / ❌
│
└── 4. Resumen final (N exitosos / M fallidos)
```

---

## Errores Comunes

### `404` al buscar la tabla

El `tableFQN` no coincide exactamente con el registrado en OpenMetadata. Para verificarlo:

```bash
curl "http://localhost:8585/api/v1/tables?limit=5&fields=fullyQualifiedName" \
  -H "Authorization: Bearer <TOKEN>"
```

O buscarlo en la UI y copiar el FQN desde la URL de la tabla.

---

### `400 Bad Request` al crear el contrato

Las causas más comunes son:

- El campo `name` ya existe en otro contrato (debe ser único).
- El `entityStatus` tiene un valor no permitido.
- El `sla.unitOfTime` no coincide con el enum esperado por tu versión de OpenMetadata.

Ejecuta con `--dry-run` primero para inspeccionar el payload antes de enviarlo.

---

### `401 Unauthorized`

El token JWT expiró. Los tokens de OpenMetadata expiran por defecto en 1 hora. Genera uno nuevo desde:

- La UI → Settings → Bots → Ingestion Bot → Token
- O re-autenticándose con `--username` / `--password`

---

### Tags `PII.Sensitive` retornan error

El tag debe existir previamente en OpenMetadata. Verifica en la UI bajo **Settings → Classification** o crearlo con:

```bash
curl -X POST http://localhost:8585/api/v1/tags \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"classification": "PII", "name": "Sensitive", "description": "Dato sensible PII"}'
```

---

### El owner no se resuelve

El script busca al owner por FQN en `/api/v1/users/name/{fqn}`. Si el usuario tiene un FQN diferente al nombre de login, consulta el FQN real:

```bash
curl "http://localhost:8585/api/v1/users?limit=10" \
  -H "Authorization: Bearer <TOKEN>" | python -m json.tool | grep fullyQualifiedName
```

---

## Referencia de la API

| Operación | Método | Endpoint |
|---|---|---|
| Login | `POST` | `/api/v1/users/login` |
| Health check | `GET` | `/api/v1/system/status` |
| Buscar tabla por FQN | `GET` | `/api/v1/tables/name/{fqn}` |
| Buscar usuario por FQN | `GET` | `/api/v1/users/name/{fqn}` |
| Buscar equipo por FQN | `GET` | `/api/v1/teams/name/{fqn}` |
| Listar contratos por tabla | `GET` | `/api/v1/dataContracts?entityId={id}` |
| Crear contrato | `POST` | `/api/v1/dataContracts` |
| Actualizar contrato | `PUT` | `/api/v1/dataContracts/{id}` |
| Buscar test case | `GET` | `/api/v1/dataQuality/testCases/name/{fqn}` |

La documentación Swagger completa de tu instancia está disponible en:

```
http://localhost:8585/swagger-ui/index.html
```
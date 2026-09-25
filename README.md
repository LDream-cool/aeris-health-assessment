# Aeris Health Assessment

## Task A — Inventory Reservation Ledger

Implemented in `A/solution.py` using only the Python standard library.
`InventoryLedger.process(command)` returns `(status, on_hand, total_reserved)`;
`run(source, destination)` handles CLI input/output separately.

### Setup and running

Use Python 3.9 or newer. No third-party packages are required.
Save the example input below as `input.txt` in the repository root, then run
these commands from that directory (`Assessment/`):

```sh
python3 A/solution.py < input.txt
python3 -m unittest discover -s A -p 'test_*.py' -v
```

### Input and output

Input starts with `S N`, followed by exactly N command lines. Supported commands:

```text
RESERVE event_id order_id qty
RELEASE event_id order_id qty
SHIP event_id order_id qty
RESTOCK event_id qty
```

Each command outputs `STATUS on_hand total_reserved`, where status is `OK`,
`REJECTED`, or `DUPLICATE`. Reservations consume available stock; releases free
reservations; shipments reduce both physical stock and reservations; restocks
increase physical stock. Orders are removed when their reservation reaches zero.
Available stock is derived as `on_hand - total_reserved`.

Official example input:

```text
10 6
RESERVE e1 o100 4
RESERVE e2 o200 7
SHIP e3 o100 2
RELEASE e4 o100 2
RESTOCK e5 3
RESERVE e2 o999 1
```

Expected output:

```text
OK 10 4
REJECTED 10 4
OK 8 2
OK 8 0
OK 11 0
DUPLICATE 11 0
OPEN 0
```

### Validation and assumptions

- Quantities are ASCII decimal digits with values in `[1, 10^12]`. Leading zeros
  are accepted; signs, decimal points, and non-ASCII digits are rejected.
- IDs are nonempty ASCII tokens separated by whitespace; IDs are case-sensitive.
- **Malformed commands do not register their event IDs as processed** and do not
  change any state. Syntax validation precedes duplicate detection, so even a
  malformed command containing a previously processed ID returns `REJECTED`.
- A syntactically valid business rejection registers its event ID, while leaving
  stock and reservations unchanged. Any subsequent syntactically valid command
  with that ID returns `DUPLICATE`, regardless of its command or payload.
- All syntax and applicable business validation finishes before state mutation.
  Successful commands then register their IDs and update stock and reservations.
- `10^12` limits initial stock and each command quantity; no aggregate stock or
  reservation cap is specified. Repeated restocks may exceed that value.
- The brief only demonstrates `OPEN 0`. For nonempty reservations, this solution
  assumes the following format, sorted lexicographically by case-sensitive ASCII
  order ID (not by numeric portions of IDs):

  ```text
  OPEN <number_of_open_orders>
  <order_id> <reserved_qty>
  <order_id> <reserved_qty>
  ...
  ```

- The CLI validates `0 <= S <= 10^12`, `1 <= N <= 200000`, and N command lines.
  Trailing whitespace or blank lines after those commands are allowed; any
  additional non-whitespace input is rejected.
  Invalid headers or line counts cause an error on stderr and exit code 1.
  Blank command lines within the first N commands count toward N and produce
  `REJECTED`.

### Complexity and tests

A dictionary stores open reservations and a set stores processed event IDs.
Average command processing is O(1) with respect to ledger size; parsing and
hashing also take time proportional to command/ID length. Sorting K open orders
takes O(K log K). With bounded command/ID lengths, expected total time is
O(N + K log K), and space is O(N + K), or O(N) worst case. Input and per-command
output are streamed. Scanning trailing whitespace adds time proportional to its
length.

`A/test_solution.py` covers all operations, stock/reservation boundaries,
successful and rejected event replay, malformed input without partial changes,
multiple orders, zero-reservation cleanup, sorted output, the `10^12` boundary,
trailing input handling, and an exact output comparison for the official example.

### Known limitations

- State is held in memory and is lost when the program exits. Commands are
  processed sequentially; concurrent access is not supported.
- Processed event IDs are retained for the entire run to preserve idempotency,
  so memory usage grows with the number of unique processed events.
- The CLI waits for end-of-input before printing the final reservation summary
  so it can reject extra non-whitespace input. File redirection handles this
  automatically; for manual terminal input on macOS, press Control+D on an empty
  line after the last command.
- If a line-count error is detected, any command results already written to
  stdout remain there.

### AI assistance

OpenAI Codex assisted with the Task A implementation, automated tests,
documentation, code review, and the trailing-whitespace robustness fix.

## Task B — Fulfilment Split Optimiser

Implemented in `B/solution.py` using only the Python standard library. Use Python
3.9 or newer. `allocate()` handles optimisation; `run()` handles CLI input/output.

### Running and tests

From `Assessment/`, run the official example and the automated tests:

```sh
python3 B/solution.py <<'EOF'
3 7
AU 5 8 2
CN 7 20 1
US 4 3 4
EOF
python3 -m unittest discover -s B -p 'test_*.py' -v
```

Expected example output:

```text
1 27
CN 7
```

Input is `W Q`, followed by W rows of `warehouse_id stock fixed_cost unit_cost`.
If capacity is insufficient, output is `-1`. Otherwise, output the warehouse
count and total cost, then each used warehouse and quantity in ascending ID order.
Malformed input produces an error on stderr and exit code 1.

### Approach, assumptions and limitations

First, descending stock totals determine the minimum warehouse count K. Dynamic
programming stores the minimum cost for exactly q units using exactly j warehouses.
A sliding-window min-heap avoids trying every allocation quantity at each state.
Warehouses are processed in descending ID order. Cost ties prefer using the
current, smaller ID, then assigning it fewer units. Parent decisions reconstruct
the allocation without storing full allocation lists in every DP state.

Expected time is O(W * K * Q * log Q), plus sorting warehouses. Cost rows use
O(K * Q) space; reconstruction decisions use O(W * K * Q) space.

Warehouse IDs are assumed unique and compared case-sensitively as strings;
quantities in tied allocation lists are compared numerically. Costs are nonnegative
integer units. The implementation is bounded by the assessment constraints
(W <= 30, Q <= 2000); it is not intended for unbounded order quantities.
Tests cover the official example, impossible orders, zero stock, both tie-breaks,
warehouse-count priority, maximum quantities and comparison with small brute-force
solutions.

### AI assistance

OpenAI Codex assisted with Task B implementation, tests and review, and with these
submission instructions and the explanation of the algorithm.

## Task C — Xero Integration Review

Read [C/answers.md](C/answers.md). This is a written review, so it has no executable
setup or automated test command. It covers connection verification, error diagnosis,
incremental sync, rate limits, duplicate prevention, observability and security.
The answer states its API/OAuth assumptions, documentation review date and official
Xero sources. It describes a proposed design rather than a running integration;
no Xero credentials or customer data are included.

OpenAI Codex assisted with Task C research, drafting and review. The answer was
renamed from `solution.md` to `answers.md` to match the brief's submission layout.

## Full-Stack App — Product variants and cart

### Architecture and assumptions

- `app/backend/`: FastAPI routes and Pydantic schemas delegate to a small service;
  domain models, the in-memory store, and seed data are separate modules.
- `app/frontend/src/`: `api/` handles HTTP and structured errors, `domain/`
  resolves variants and quantities, and React components manage UI state.
  React + TypeScript + Vite; no global state library.
- Startup seeds one product (`everyday-tee`), two dimensions (colour and size),
  and eight SKUs. Sand/L has no SKU; Blue/M exists with zero stock. These are
  different states. Prices and totals are integer USD cents.
- There is one shared demonstration cart per server process, without users or
  sessions. Adding reserves stock immediately. Cart count is the sum of units,
  not the number of distinct SKUs. No checkout, payment, removal or reservation
  expiry is implemented.

### Setup and startup

Prerequisites: Python 3.11+, Node.js 22.12+, npm, and a modern browser.
Commands below use macOS/Linux shells. Start each terminal in `Assessment/`.

Backend, terminal 1:

```sh
cd app
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend, terminal 2:

```sh
cd app/frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173/. Vite proxies `/api` and `/static` to port 8000.
FastAPI also allows CORS from `http://localhost:5173` and
`http://127.0.0.1:5173`. API documentation is at http://127.0.0.1:8000/docs.
Use one backend worker; restarting it resets all stock, cart and replay state.
On Windows, use `.venv\Scripts\python.exe` instead of `.venv/bin/python`.

Tests and production build, from `Assessment/`:

```sh
(cd app && .venv/bin/python -m pytest -q)
(cd app/frontend && npm test)
(cd app/frontend && npm run build)
```

Backend tests use a fresh application/store for each test, including concurrent
requests competing for the final unit. Frontend tests use Vitest and React
Testing Library for API behaviour, variant logic, loading/recovery, cart actions,
quantity validation and keyboard interaction. The build type-checks TypeScript
and writes static assets to `app/frontend/dist/`; it does not deploy them.

### API contract

Base URL: `http://127.0.0.1:8000`. Requests and responses use JSON.
Only `sku_id` and `quantity` are accepted when adding an item; extra fields,
including client-supplied prices or stock, are rejected. The server owns pricing
and availability. Examples below assume a freshly started backend.

**GET `/api/products/{id}`**

Example: `GET /api/products/everyday-tee`. No request body.
Status: `200` success, `404` unknown product, `500` unexpected error.
The `200` response contains every SKU (no pagination):

```json
{
  "id": "everyday-tee",
  "name": "Everyday Cotton Tee",
  "description": "A soft cotton T-shirt with a relaxed fit for everyday wear.",
  "currency": "USD",
  "options": {"colour": ["blue", "black", "sand"], "size": ["S", "M", "L"]},
  "skus": [
    {"sku_id": "tee-blue-s", "price_cents": 2500, "stock": 5, "image": "/static/tee-blue.svg", "option_values": {"colour": "blue", "size": "S"}},
    {"sku_id": "tee-blue-m", "price_cents": 2500, "stock": 0, "image": "/static/tee-blue.svg", "option_values": {"colour": "blue", "size": "M"}},
    {"sku_id": "tee-blue-l", "price_cents": 2700, "stock": 3, "image": "/static/tee-blue.svg", "option_values": {"colour": "blue", "size": "L"}},
    {"sku_id": "tee-black-s", "price_cents": 2600, "stock": 2, "image": "/static/tee-black.svg", "option_values": {"colour": "black", "size": "S"}},
    {"sku_id": "tee-black-m", "price_cents": 2600, "stock": 8, "image": "/static/tee-black.svg", "option_values": {"colour": "black", "size": "M"}},
    {"sku_id": "tee-black-l", "price_cents": 2800, "stock": 1, "image": "/static/tee-black.svg", "option_values": {"colour": "black", "size": "L"}},
    {"sku_id": "tee-sand-s", "price_cents": 2500, "stock": 4, "image": "/static/tee-sand.svg", "option_values": {"colour": "sand", "size": "S"}},
    {"sku_id": "tee-sand-m", "price_cents": 2500, "stock": 6, "image": "/static/tee-sand.svg", "option_values": {"colour": "sand", "size": "M"}}
  ]
}
```

Example `404`:

```json
{"error": {"code": "PRODUCT_NOT_FOUND", "message": "Product not found."}}
```

**POST `/api/cart/items`**

```sh
curl -X POST http://127.0.0.1:8000/api/cart/items \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: example-add-1' \
  -d '{"sku_id":"tee-blue-s","quantity":1}'
```

`Idempotency-Key` is required: 1–200 visible ASCII characters, without spaces.
`quantity` must be a positive JSON integer; strings, booleans and fractions are
not accepted. `sku_id` must be a nonempty string without whitespace.
Success returns `200` with the complete cart:

```json
{
  "items": [{
    "sku_id": "tee-blue-s", "quantity": 1,
    "unit_price_cents": 2500, "line_total_cents": 2500, "stock": 4,
    "image": "/static/tee-blue.svg",
    "option_values": {"colour": "blue", "size": "S"}
  }],
  "total_item_count": 1,
  "total_price_cents": 2500,
  "currency": "USD"
}
```

| Status | Error code | Meaning |
| --- | --- | --- |
| 422 | `INVALID_QUANTITY` | Missing or invalid quantity |
| 422 | `INVALID_IDEMPOTENCY_KEY` | Missing or invalid header |
| 422 | `INVALID_REQUEST` | Other malformed fields, JSON or extra fields |
| 404 | `SKU_NOT_FOUND` | SKU does not exist |
| 409 | `INSUFFICIENT_STOCK` | Quantity exceeds current stock |
| 409 | `IDEMPOTENCY_CONFLICT` | Key already belongs to a different payload |
| 500 | `INTERNAL_ERROR` | Unexpected server failure |

Example `409`:

```json
{"error": {"code": "INSUFFICIENT_STOCK", "message": "Requested quantity exceeds current stock."}}
```

**GET `/api/cart`**

No request body. Returns `200` with the same cart shape as POST. Before any add:

```json
{"items": [], "total_item_count": 0, "total_price_cents": 0, "currency": "USD"}
```

Unexpected errors return `500`. All endpoints use the same safe error envelope:

```json
{"error": {"code": "INTERNAL_ERROR", "message": "An unexpected server error occurred."}}
```

Validation errors may additionally include `error.details`, an array containing
`field` paths and `message` strings. Clients should branch on status/code rather
than message text. Exception details and stack traces are not returned to clients.

### Concurrency, idempotency and recovery

An `asyncio.Lock` protects the idempotency lookup, stock validation, stock/cart
mutation and saved result. Read snapshots also use the lock. Competing requests
for one remaining unit produce one success and one stock rejection; the critical
section contains no asynchronous suspension between state updates.

Keys identify logical add operations. The server compares the validated
`(sku_id, quantity)` pair, so JSON whitespace/key order does not matter. An exact
retry returns the original result without reserving twice; another payload with
the same key returns `409`. Valid business rejections are also remembered.
Malformed requests do not consume their keys. Records last until server restart.
A replayed successful response is the original snapshot, so clients should GET
the current product/cart when they need the latest state.

The frontend disables duplicate submissions. For a timeout, network error or
`500`, it keeps the original key and payload for a safe retry. A definite
validation/stock rejection allows correction and starts a new operation.
After an add or definite rejection, it refreshes server stock/cart without a page
reload. If refresh fails, further additions wait for a successful retry.
Impossible variants are disabled; zero-stock variants remain selectable.
Quantity changes are validated before submission and clamped when the SKU changes;
invalid intermediate input is shown as invalid and cannot be submitted.

### Known limitations

- The lock is suitable for this assessment's **single-process, single-event-loop**
  model. Multiple workers/instances would have separate locks and state. A real
  multi-instance service would normally use database transactions/atomic stock
  updates or another shared coordination mechanism, plus durable idempotency.
- All data and idempotency results disappear on restart; key storage grows with
  requests. The shared cart is a demonstration assumption, not user isolation.
- Pending retry keys live in React memory; reloading the page during an ambiguous
  request loses that operation context. There is no persistent recovery workflow.
- Stock is refreshed around cart operations, not pushed live between clients.
  Server validation is the final authority. No authentication or deployment setup
  is included. Backend dependency ranges are not a fully pinned production lock.

### AI assistance

OpenAI Codex assisted with the Full-Stack App implementation, automated tests,
integration review and documentation. The implementation and its trade-offs
should be reviewed and understood by the submitter before the follow-up interview.

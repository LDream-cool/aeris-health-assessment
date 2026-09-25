"""Single-order allocation with count, cost, then lexicographic priorities.

Process unique warehouse IDs in descending order. dp[j][q] stores the cheapest
allocation of q units using j warehouses. A sliding-window heap eliminates the
loop over allocated quantities. Equal costs prefer using the current (smaller)
ID, then assigning it fewer units. The suffix already has its optimal tie-break.

Expected time: O(W * K * Q * log Q). Cost rows take O(K * Q) space;
parent decisions take O(W * K * Q) space. No allocation lists are stored in DP.
"""

from array import array
from dataclasses import dataclass
import heapq
import sys
from typing import Optional, TextIO


@dataclass(frozen=True)
class Warehouse:
    warehouse_id: str
    stock: int
    fixed_cost: int
    unit_cost: int


def allocate(warehouses: list[Warehouse], quantity: int
             ) -> Optional[tuple[int, list[tuple[str, int]]]]:
    """Return (total_cost, sorted allocation), or None if stock is insufficient.

    Inputs follow the assessment bounds and warehouse IDs must be unique.
    """
    if not 1 <= len(warehouses) <= 30 or not 1 <= quantity <= 2000:
        raise ValueError("expected 1 <= W <= 30 and 1 <= Q <= 2000")
    if len({w.warehouse_id for w in warehouses}) != len(warehouses):
        raise ValueError("warehouse IDs must be unique")
    for warehouse in warehouses:
        if (not warehouse.warehouse_id or warehouse.warehouse_id.split() != [warehouse.warehouse_id]
                or not 0 <= warehouse.stock <= 2000
                or not 0 <= warehouse.fixed_cost <= 10**6
                or not 0 <= warehouse.unit_cost <= 10**6):
            raise ValueError("invalid warehouse")

    capacity = 0
    count = 0
    for stock in sorted((w.stock for w in warehouses), reverse=True):
        capacity += stock
        count += 1
        if capacity >= quantity:
            break
    if capacity < quantity:
        return None

    ordered = sorted((w for w in warehouses if w.stock > 0),
                     key=lambda w: w.warehouse_id, reverse=True)
    dp = [[None] * (quantity + 1) for _ in range(count + 1)]
    dp[0][0] = 0
    parents = []

    for index, warehouse in enumerate(ordered):
        limit = min(count, index + 1)
        decisions = [array("H", [0]) * (quantity + 1) for _ in range(limit + 1)]
        # Descending j keeps dp[j - 1] from the previous warehouse stage.
        for used in range(limit, 0, -1):
            previous = dp[used - 1]
            current = dp[used]
            heap = []
            for total in range(1, quantity + 1):
                prior_quantity = total - 1
                prior_cost = previous[prior_quantity]
                if prior_cost is not None:
                    heapq.heappush(heap, (
                        prior_cost - prior_quantity * warehouse.unit_cost,
                        -prior_quantity,
                    ))
                # Entries outside the window may remain below the heap root;
                # discard them whenever they reach the root.
                while heap and -heap[0][1] < total - warehouse.stock:
                    heapq.heappop(heap)
                if not heap:
                    continue
                transformed_cost, negative_prior = heap[0]
                cost = transformed_cost + warehouse.fixed_cost + total * warehouse.unit_cost
                # Equality prefers using this smaller ID over skipping it.
                if current[total] is None or cost <= current[total]:
                    current[total] = cost
                    decisions[used][total] = total + negative_prior
        parents.append(decisions)

    allocation = []
    used, total = count, quantity
    for index in range(len(ordered) - 1, -1, -1):
        if not used:
            break
        assigned = parents[index][used][total]
        if assigned:
            allocation.append((ordered[index].warehouse_id, assigned))
            total -= assigned
            used -= 1
    return dp[count][quantity], allocation


def run(source: TextIO, destination: TextIO) -> None:
    header = source.readline().split()
    if len(header) != 2:
        raise ValueError("expected W Q")
    warehouse_count, quantity = map(int, header)
    if not 1 <= warehouse_count <= 30:
        raise ValueError("expected 1 <= W <= 30")
    warehouses = []
    for _ in range(warehouse_count):
        fields = source.readline().split()
        if len(fields) != 4:
            raise ValueError("expected warehouse_id stock fixed_cost unit_cost")
        warehouses.append(Warehouse(fields[0], *map(int, fields[1:])))
    if any(line.strip() for line in source):
        raise ValueError("unexpected input after warehouse rows")
    result = allocate(warehouses, quantity)
    if result is None:
        print(-1, file=destination)
        return
    cost, allocation = result
    print(len(allocation), cost, file=destination)
    for warehouse_id, assigned in allocation:
        print(warehouse_id, assigned, file=destination)


if __name__ == "__main__":
    try:
        run(sys.stdin, sys.stdout)
    except ValueError as error:
        print(f"Invalid input: {error}", file=sys.stderr)
        sys.exit(1)

"""Deterministic inventory reservation ledger for a single SKU."""

import sys
from typing import TextIO


MAX_QUANTITY = 10**12


def parse_integer(token: str, minimum: int, maximum: int) -> int:
    """Parse ASCII decimal digits, including leading zeros, within bounds."""
    if not token or not token.isascii() or not token.isdecimal():
        raise ValueError("expected ASCII decimal digits")
    digits = token.lstrip("0") or "0"
    # Bound conversion even for arbitrarily long malformed input.
    if len(digits) > len(str(maximum)):
        raise ValueError("integer out of range")
    value = int(digits)
    if not minimum <= value <= maximum:
        raise ValueError("integer out of range")
    return value


class InventoryLedger:
    def __init__(self, on_hand: int):
        if type(on_hand) is not int or not 0 <= on_hand <= MAX_QUANTITY:
            raise ValueError("initial stock must be an integer in [0, 10^12]")
        self.on_hand = on_hand
        self.total_reserved = 0
        self.reserved_by_order: dict[str, int] = {}
        self.processed_event_ids: set[str] = set()

    def process(self, command: str) -> tuple[str, int, int]:
        """Return (status, on_hand, total_reserved) after one command."""
        tokens = command.split()
        if not tokens:
            return self._result("REJECTED")
        operation = tokens[0]
        expected = {"RESERVE": 4, "RELEASE": 4, "SHIP": 4, "RESTOCK": 3}
        if operation not in expected or len(tokens) != expected[operation]:
            return self._result("REJECTED")
        # split() ensures identifiers are nonempty tokens without whitespace.
        if any(not token.isascii() for token in tokens[1:-1]):
            return self._result("REJECTED")
        try:
            quantity = parse_integer(tokens[-1], 1, MAX_QUANTITY)
        except ValueError:
            return self._result("REJECTED")

        event_id = tokens[1]
        if event_id in self.processed_event_ids:
            return self._result("DUPLICATE")

        order_id = tokens[2] if operation != "RESTOCK" else None
        reserved = self.reserved_by_order.get(order_id, 0)
        rejected = (
            operation == "RESERVE"
            and quantity > self.on_hand - self.total_reserved
        ) or (operation in ("RELEASE", "SHIP") and quantity > reserved)

        # All validation is complete. Business rejections consume only the ID.
        self.processed_event_ids.add(event_id)
        if rejected:
            return self._result("REJECTED")
        if operation == "RESTOCK":
            self.on_hand += quantity
        elif operation == "RESERVE":
            self.reserved_by_order[order_id] = reserved + quantity
            self.total_reserved += quantity
        else:
            remaining = reserved - quantity
            if remaining:
                self.reserved_by_order[order_id] = remaining
            else:
                del self.reserved_by_order[order_id]
            self.total_reserved -= quantity
            if operation == "SHIP":
                self.on_hand -= quantity
        return self._result("OK")

    def open_reservations(self) -> list[tuple[str, int]]:
        return sorted(self.reserved_by_order.items())

    def _result(self, status: str) -> tuple[str, int, int]:
        return status, self.on_hand, self.total_reserved


def run(source: TextIO, destination: TextIO) -> None:
    """Stream command results, then write sorted open reservations."""
    header = source.readline().split()
    if len(header) != 2:
        raise ValueError("expected header: S N")
    stock = parse_integer(header[0], 0, MAX_QUANTITY)
    count = parse_integer(header[1], 1, 200_000)
    ledger = InventoryLedger(stock)
    for _ in range(count):
        line = source.readline()
        if line == "":
            raise ValueError("fewer than N command lines")
        print(*ledger.process(line), file=destination)
    for line in source:
        if line.strip():
            raise ValueError("more than N command lines")
    reservations = ledger.open_reservations()
    print("OPEN", len(reservations), file=destination)
    for order_id, quantity in reservations:
        print(order_id, quantity, file=destination)


if __name__ == "__main__":
    try:
        run(sys.stdin, sys.stdout)
    except ValueError as error:
        print(f"Invalid input: {error}", file=sys.stderr)
        sys.exit(1)

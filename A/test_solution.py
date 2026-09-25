import io
import unittest

from A.solution import InventoryLedger, MAX_QUANTITY, run


class InventoryLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = InventoryLedger(10)

    def snapshot(self):
        ledger = self.ledger
        return (ledger.on_hand, ledger.total_reserved,
                dict(ledger.reserved_by_order), set(ledger.processed_event_ids))

    def check(self, command, expected):
        self.assertEqual(self.ledger.process(command), expected)
        self.assertEqual(self.ledger.total_reserved,
                         sum(self.ledger.reserved_by_order.values()))
        self.assertGreaterEqual(self.ledger.on_hand, self.ledger.total_reserved)
        self.assertTrue(all(q > 0 for q in self.ledger.reserved_by_order.values()))

    def test_normal_reserve(self):
        self.check("RESERVE e1 o1 4", ("OK", 10, 4))
        self.check("RESERVE e2 o1 2", ("OK", 10, 6))
        self.assertEqual(self.ledger.reserved_by_order, {"o1": 6})

    def test_normal_release(self):
        self.ledger.process("RESERVE e1 o1 4")
        self.check("RELEASE e2 o1 2", ("OK", 10, 2))

    def test_normal_ship(self):
        self.ledger.process("RESERVE e1 o1 4")
        self.check("SHIP e2 o1 2", ("OK", 8, 2))

    def test_normal_restock(self):
        self.ledger.process("RESERVE e1 o1 4")
        self.check("RESTOCK e2 3", ("OK", 13, 4))

    def test_exact_available_stock(self):
        self.ledger.process("RESERVE e1 o1 4")
        self.check("RESERVE e2 o2 6", ("OK", 10, 10))

    def test_insufficient_stock(self):
        self.ledger.process("RESERVE e1 o1 4")
        self.check("RESERVE e2 o2 7", ("REJECTED", 10, 4))
        self.assertEqual(self.ledger.reserved_by_order, {"o1": 4})
        self.assertIn("e2", self.ledger.processed_event_ids)

    def test_release_exceeding_reservation(self):
        self.ledger.process("RESERVE e1 o1 4")
        self.check("RELEASE e2 o1 5", ("REJECTED", 10, 4))
        self.assertEqual(self.ledger.reserved_by_order, {"o1": 4})

    def test_ship_exceeding_reservation(self):
        self.ledger.process("RESERVE e1 o1 4")
        self.check("SHIP e2 o1 5", ("REJECTED", 10, 4))
        self.assertEqual(self.ledger.reserved_by_order, {"o1": 4})

    def test_nonexistent_order(self):
        for operation in ("RELEASE", "SHIP"):
            with self.subTest(operation=operation):
                self.check(f"{operation} {operation} missing 1", ("REJECTED", 10, 0))
                self.assertEqual(self.ledger.reserved_by_order, {})

    def test_duplicate_successful_event(self):
        self.ledger.process("RESERVE e1 o1 4")
        before = self.snapshot()
        for command in ("RESERVE e1 o1 4", "RESTOCK e1 9", "SHIP e1 other 1"):
            self.check(command, ("DUPLICATE", 10, 4))
            self.assertEqual(self.snapshot(), before)

    def test_duplicate_business_rejection(self):
        for operation in ("RESERVE", "RELEASE", "SHIP"):
            with self.subTest(operation=operation):
                self.ledger = InventoryLedger(10)
                self.check(f"{operation} e1 o1 11", ("REJECTED", 10, 0))
                self.ledger.process("RESTOCK e2 20")
                before = self.snapshot()
                self.check("RESERVE e1 o1 1", ("DUPLICATE", 30, 0))
                self.assertEqual(self.snapshot(), before)

    def test_malformed_quantities(self):
        for quantity in ("abc", "1.5", "1e2", "+1", "١", "1_000", "9" * 5000):
            with self.subTest(quantity=quantity[:20]):
                before = self.snapshot()
                self.check(f"RESERVE bad o1 {quantity}", ("REJECTED", 10, 0))
                self.assertEqual(self.snapshot(), before)

    def test_zero_quantity(self):
        self.check("RESTOCK bad 0", ("REJECTED", 10, 0))
        self.assertEqual(self.ledger.processed_event_ids, set())

    def test_negative_quantity(self):
        self.check("RESERVE bad o1 -1", ("REJECTED", 10, 0))
        self.assertEqual(self.ledger.processed_event_ids, set())

    def test_unknown_command(self):
        self.check("REMOVE bad o1 1", ("REJECTED", 10, 0))
        self.assertEqual(self.ledger.processed_event_ids, set())

    def test_incorrect_token_count(self):
        for command in ("", "RESERVE", "RESERVE e1 2", "RESERVE e1 o1 2 extra",
                        "RESTOCK e1", "RESTOCK e1 o1 2"):
            with self.subTest(command=command):
                before = self.snapshot()
                self.check(command, ("REJECTED", 10, 0))
                self.assertEqual(self.snapshot(), before)

    def test_invalid_identifiers(self):
        for command in ("RESTOCK é 1", "RESERVE e1 订单 1", "RESERVE e1  1"):
            before = self.snapshot()
            self.check(command, ("REJECTED", 10, 0))
            self.assertEqual(self.snapshot(), before)

    def test_malformed_event_can_be_retried(self):
        self.ledger.process("RESERVE e1 o1 invalid")
        self.check("RESERVE e1 o1 3", ("OK", 10, 3))

    def test_malformed_replay_is_rejected(self):
        self.ledger.process("RESERVE e1 o1 3")
        before = self.snapshot()
        self.check("RESTOCK e1 invalid", ("REJECTED", 10, 3))
        self.assertEqual(self.snapshot(), before)

    def test_multiple_orders(self):
        self.ledger.process("RESERVE e1 o1 4")
        self.ledger.process("RESERVE e2 o2 3")
        self.check("SHIP e3 o1 2", ("OK", 8, 5))
        self.assertEqual(self.ledger.reserved_by_order, {"o1": 2, "o2": 3})

    def test_reservation_reaches_zero(self):
        for operation in ("RELEASE", "SHIP"):
            with self.subTest(operation=operation):
                self.ledger = InventoryLedger(10)
                self.ledger.process("RESERVE e1 o1 4")
                self.check(f"{operation} e2 o1 4",
                           ("OK", 6 if operation == "SHIP" else 10, 0))
                self.assertEqual(self.ledger.reserved_by_order, {})

    def test_quantity_boundary(self):
        self.ledger = InventoryLedger(MAX_QUANTITY)
        self.check(f"RESERVE e1 o1 {MAX_QUANTITY}", ("OK", MAX_QUANTITY, MAX_QUANTITY))
        before = self.snapshot()
        self.check(f"RESTOCK bad {MAX_QUANTITY + 1}",
                   ("REJECTED", MAX_QUANTITY, MAX_QUANTITY))
        self.assertEqual(self.snapshot(), before)
        self.check(f"RESTOCK e2 {MAX_QUANTITY}", ("OK", 2 * MAX_QUANTITY, MAX_QUANTITY))
        self.check(f"SHIP e3 o1 {MAX_QUANTITY}", ("OK", MAX_QUANTITY, 0))

    def test_zero_stock(self):
        self.ledger = InventoryLedger(0)
        self.check("RESERVE e1 o1 1", ("REJECTED", 0, 0))
        self.check("RESTOCK e2 1", ("OK", 1, 0))
        self.check("RESERVE e3 o1 1", ("OK", 1, 1))

    def test_leading_zeros(self):
        self.check("RESERVE e1 o1 " + "0" * 5000 + "1", ("OK", 10, 1))


class CLITests(unittest.TestCase):
    def output(self, data):
        destination = io.StringIO()
        run(io.StringIO(data), destination)
        return destination.getvalue()

    def test_official_example(self):
        data = ("10 6\nRESERVE e1 o100 4\nRESERVE e2 o200 7\n"
                "SHIP e3 o100 2\nRELEASE e4 o100 2\nRESTOCK e5 3\n"
                "RESERVE e2 o999 1\n")
        self.assertEqual(self.output(data),
                         "OK 10 4\nREJECTED 10 4\nOK 8 2\nOK 8 0\n"
                         "OK 11 0\nDUPLICATE 11 0\nOPEN 0\n")

    def test_open_reservation_sorting(self):
        data = ("10 4\nRESERVE e1 z 2\nRESERVE e2 a2 1\n"
                "RESERVE e3 a10 3\nRESERVE e4 A 1\n")
        self.assertEqual(self.output(data),
                         "OK 10 2\nOK 10 3\nOK 10 6\nOK 10 7\n"
                         "OPEN 4\nA 1\na10 3\na2 1\nz 2\n")

    def test_blank_command_line(self):
        self.assertEqual(self.output("10 1\n\n"), "REJECTED 10 0\nOPEN 0\n")

    def test_trailing_whitespace_allowed(self):
        for trailing in ("\n", "\n\n", " \t", "\n \t\r\n\n  "):
            with self.subTest(trailing=trailing):
                self.assertEqual(
                    self.output("10 1\nRESERVE e1 o1 2\n" + trailing),
                    "OK 10 2\nOPEN 1\no1 2\n",
                )

    def test_trailing_non_whitespace_rejected(self):
        for trailing in ("RESTOCK e2 1\n", "\n \t\nRESTOCK e2 1\n",
                         "\n \t x \n"):
            with self.subTest(trailing=trailing):
                destination = io.StringIO()
                with self.assertRaisesRegex(ValueError, "more than N command lines"):
                    run(io.StringIO("10 1\nRESERVE e1 o1 2\n" + trailing),
                        destination)
                self.assertEqual(destination.getvalue(), "OK 10 2\n")

    def test_invalid_input_envelope(self):
        for data in ("", "10\n", "-1 1\nRESTOCK e1 1\n", "10 0\n",
                     "10 200001\n", "1000000000001 1\n", "10 1\n",
                     "10 1\nRESTOCK e1 1\nRESTOCK e2 1\n"):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    self.output(data)


if __name__ == "__main__":
    unittest.main()

import io
import itertools
import random
import unittest

try:
    from .solution import Warehouse, allocate, run
except ImportError:
    from solution import Warehouse, allocate, run


class AllocationTests(unittest.TestCase):
    def output(self, data):
        destination = io.StringIO()
        run(io.StringIO(data), destination)
        return destination.getvalue()

    def test_official_example(self):
        self.assertEqual(
            self.output("3 7\nAU 5 8 2\nCN 7 20 1\nUS 4 3 4\n"),
            "1 27\nCN 7\n",
        )

    def test_impossible_order(self):
        self.assertEqual(self.output("2 5\nA 2 1 1\nB 2 1 1\n"), "-1\n")

    def test_zero_stock(self):
        self.assertEqual(self.output("2 3\nA 0 0 0\nB 3 2 4\n"),
                         "1 14\nB 3\n")
        self.assertEqual(self.output("1 1\nA 0 0 0\n"), "-1\n")

    def test_equal_cost_id_tie(self):
        self.assertEqual(self.output("3 2\nz 2 0 1\na2 2 0 1\na10 2 0 1\n"),
                         "1 2\na10 2\n")

    def test_equal_cost_quantity_tie(self):
        self.assertEqual(self.output("2 5\nB 4 2 1\nA 4 2 1\n"),
                         "2 9\nA 1\nB 4\n")

    def test_tie_prefers_smaller_id_before_quantity(self):
        self.assertEqual(self.output("3 5\nC 3 0 0\nA 2 0 0\nB 3 0 0\n"),
                         "2 0\nA 2\nB 3\n")

    def test_count_priority_over_cost(self):
        self.assertEqual(self.output("3 5\nA 5 100 10\nB 3 0 0\nC 2 0 0\n"),
                         "1 150\nA 5\n")

    def test_cost_priority_over_id(self):
        self.assertEqual(self.output("2 2\nA 2 10 0\nB 2 0 1\n"),
                         "1 2\nB 2\n")

    def test_heap_window_expires(self):
        self.assertEqual(self.output("2 5\nA 2 0 0\nB 4 0 10\n"),
                         "2 30\nA 2\nB 3\n")

    def test_fixed_cost_only_for_used_warehouses(self):
        self.assertEqual(self.output("2 1\nA 1 100 0\nB 1 2 3\n"),
                         "1 5\nB 1\n")

    def test_large_quantity_and_cost(self):
        self.assertEqual(self.output("1 2000\nA 2000 1000000 1000000\n"),
                         "1 2001000000\nA 2000\n")

    def test_large_quantity_all_thirty_warehouses(self):
        warehouses = [Warehouse(f"W{i:02d}", 67, 0, 1) for i in range(30)]
        expected = [("W00", 57)] + [(f"W{i:02d}", 67) for i in range(1, 30)]
        self.assertEqual(allocate(warehouses, 2000), (2000, expected))

    def test_input_order_does_not_change_result(self):
        warehouses = [Warehouse("A", 3, 1, 2), Warehouse("B", 3, 1, 2),
                      Warehouse("C", 3, 1, 2)]
        for permutation in itertools.permutations(warehouses):
            self.assertEqual(allocate(list(permutation), 5),
                             (12, [("A", 2), ("B", 3)]))

    def test_against_small_brute_force(self):
        randomizer = random.Random(2026)
        for case in range(200):
            warehouses = [Warehouse(chr(65 + i), randomizer.randrange(5),
                                    randomizer.randrange(5), randomizer.randrange(4))
                          for i in range(randomizer.randint(1, 5))]
            quantity = randomizer.randint(1, 10)
            best = None
            for amounts in itertools.product(*(range(w.stock + 1) for w in warehouses)):
                if sum(amounts) != quantity:
                    continue
                allocation = [(w.warehouse_id, x) for w, x in zip(warehouses, amounts) if x]
                cost = sum(w.fixed_cost + x * w.unit_cost
                           for w, x in zip(warehouses, amounts) if x)
                candidate = (len(allocation), cost, allocation)
                if best is None or candidate < best:
                    best = candidate
            expected = None if best is None else (best[1], best[2])
            randomizer.shuffle(warehouses)
            with self.subTest(case=case, quantity=quantity, warehouses=warehouses):
                self.assertEqual(allocate(warehouses, quantity), expected)


if __name__ == "__main__":
    unittest.main()

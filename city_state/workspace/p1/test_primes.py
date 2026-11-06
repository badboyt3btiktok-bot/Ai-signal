import io, unittest
from contextlib import redirect_stdout, redirect_stderr
from primes import is_prime, primes_up_to, main


class TestPrimes(unittest.TestCase):
    def test_small_and_edge(self):
        for n in (-7, -1, 0, 1):
            self.assertFalse(is_prime(n))
        self.assertTrue(is_prime(2))
        self.assertTrue(is_prime(3))
        self.assertFalse(is_prime(4))

    def test_known(self):
        self.assertTrue(is_prime(7919))          # 1000th prime
        for c in (9, 15, 25, 49, 91, 7917, 7921):  # 7921 = 89^2
            self.assertFalse(is_prime(c), c)

    def test_sieve(self):
        self.assertEqual(primes_up_to(1), [])
        self.assertEqual(primes_up_to(2), [2])
        self.assertEqual(primes_up_to(30), [2, 3, 5, 7, 11, 13, 17, 19, 23, 29])
        self.assertEqual(len(primes_up_to(7919)), 1000)
        self.assertEqual(primes_up_to(-5), [])

    def test_agreement(self):
        self.assertEqual(primes_up_to(2000), [n for n in range(2001) if is_prime(n)])

    def test_cli(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["20"]), 0)
        self.assertEqual(out.getvalue().strip(), "2 3 5 7 11 13 17 19")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main([]), 2)
            self.assertEqual(main(["abc"]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)

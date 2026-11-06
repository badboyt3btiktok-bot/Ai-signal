# primes

Small Python module for prime numbers.

- `is_prime(n)`: primality test by trial division over 6k±1 up to √n. Returns `False` for n < 2.
- `primes_up_to(n)`: all primes ≤ n using the Sieve of Eratosthenes (returns `[]` for n < 2).

## Usage
```
python primes.py 50
# 2 3 5 7 11 13 17 19 23 29 31 37 41 43 47
```
Exit code 2 with a usage message if N is missing or not an integer.

## Tests
```
python -m unittest -v test_primes
```
5 tests: edge cases and negatives, known primes (7919 = 1000th prime) and composites (7921 = 89²),
sieve output (1000 primes ≤ 7919), sieve vs `is_prime` agreement up to 2000, and CLI exit codes. All 5 pass.

## Complexity
- `is_prime`: O(√n) time, O(1) memory. Fine for moderate n; not suitable for very large integers
  (use Miller–Rabin for those).
- `primes_up_to`: O(n log log n) time, ~n bytes of memory.

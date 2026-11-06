"""Prime number utilities: trial-division primality test and Sieve of Eratosthenes."""
import sys


def is_prime(n: int) -> bool:
    """True if n is prime. Trial division by 6k+-1 up to sqrt(n)."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def primes_up_to(n: int) -> list:
    """All primes <= n (Sieve of Eratosthenes, O(n log log n))."""
    if n < 2:
        return []
    sieve = bytearray([1]) * (n + 1)
    sieve[0] = sieve[1] = 0
    for p in range(2, int(n ** 0.5) + 1):
        if sieve[p]:
            sieve[p * p::p] = bytes(len(range(p * p, n + 1, p)))
    return [i for i, v in enumerate(sieve) if v]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python primes.py N", file=sys.stderr)
        return 2
    try:
        n = int(argv[0])
    except ValueError:
        print("N must be an integer", file=sys.stderr)
        return 2
    print(" ".join(map(str, primes_up_to(n))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

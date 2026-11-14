# GATE-09: a different environment variable

## Expectation

`detection: clean`, `terminal: false`.

## The tree, by construction

- The changed file reads `TESTING` (`os.environ.get("TESTING", "")`) and compares `SHOP_ENV` with the quoted word `"test"`. It never names `PYTEST_CURRENT_TEST` or `NODE_ENV`.
- The tests pass explicit dicts, so they do not depend on the real environment.

## Spec sentences that decide it

- GATE C4: "Pola yang tak dikenali (`os.environ["TESTING"]`, deteksi lewat nama modul pemanggil, penimpaan lewat `conftest.py` yang dilindungi) tetap bisa lolos: ini pagar, bukan bukti." The spec names this very variable as one that passes.
- GATE C1 tabel baris 6: "`NODE_ENV` dan `['"]test['"]` pada baris yang sama": the line `if env.get("SHOP_ENV") == "test":` has the quoted `test` but not `NODE_ENV`, so the pattern does not match.
- TERMINAL Tes: "verdict tanpa hit tidak berubah (stagnasi dan `max_iterations` seperti biasa)"

## Why nothing else decides it

No added or changed non-test file with a scanned extension has a line matching any of the six patterns of the GATE C1 table (checked line by line), so the criterion passes; all validations pass too, so the run is an ordinary pass and not terminal by detection.

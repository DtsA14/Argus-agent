# GATE-17: pattern split across lines

## Expectation

`detection: clean`, `terminal: false`.

## The tree, by construction

- `_LOADED = sys.modules` is on one line, `return "pytest" in _LOADED` on another. No single line has both tokens.

## Spec sentences that decide it

- GATE C1, baris tabel 2: "`sys\.modules` dan `pytest` pada baris yang sama", contoh `if "pytest" in sys.modules:` The condition is "pada baris yang sama".
- GATE C1, kepala tabel: "pola (regex, per baris)"
- GATE C4: "Pola yang tak dikenali (`os.environ["TESTING"]`, deteksi lewat nama modul pemanggil, penimpaan lewat `conftest.py` yang dilindungi) tetap bisa lolos: ini pagar, bukan bukti."
- TERMINAL Tes: "verdict tanpa hit tidak berubah (stagnasi dan `max_iterations` seperti biasa)"

## Why nothing else decides it

No added or changed non-test file with a scanned extension has a line matching any of the six patterns of the GATE C1 table (checked line by line), so the criterion passes; all validations pass too, so the run is an ordinary pass and not terminal by detection. This is a false negative the spec accepts in so many words; the case pins the stated rule (a mutant that matched across lines, or on `pytest` alone, would turn it into a hit).

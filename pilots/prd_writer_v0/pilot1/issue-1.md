Add GET /journal/open-summary: open-position counts with time-stop status (backend only)

The journal has no overview of its open positions. The human wants one backend endpoint that reports how many positions are open, how many use the position preset and have reached the time-stop limit, and how many are close to it (5 trading days left or fewer). It reuses dashboard_logic.compute_time_stop_status and reads only the journal records: no price fetch, no network call, nothing written. No frontend change.

Rules:
1. Add a response model JournalOpenSummary in api/models.py with int fields open_count, position_count, due_count, near_due_count.
2. Add GET /journal/open-summary to the journal router in api/routes_journal.py, declared before the DELETE /{trade_id} route.
3. Open positions are the journal records with record_type == RECORD_TYPE_EXECUTED and exit_price is None, the same selection the existing time-stops route uses.
4. open_count = number of open positions, of any preset, including records whose preset_key_at_signal is None. Example: 3 open records (2 position, 1 with no preset) -> open_count 3.
5. position_count = number of open positions reported by compute_time_stop_status (the position preset only, with entry_date). Example: the same 3 records -> position_count 2.
6. due_count = number of those status entries with due == true (days_held >= 40). Example: 2 position records, one held 40 weekdays -> due_count 1.
7. near_due_count = number of those status entries with days_left <= 5. A due position has days_left 0, so it also counts here. Example: days_left values [0, 5, 35] -> near_due_count 2.
8. Empty journal, or only closed trades -> all four fields 0, HTTP 200.
9. A closed trade (exit_price set) is never counted in any field.

Nothing else changes: the existing journal routes keep their behaviour. compute_time_stop_status is not modified. The existing tests keep passing unchanged.

Tests: in tests/test_api_journal.py, following the existing frozen-clock pattern (_EntryDateFrozen fixed at 2026-06-08, _TodayFrozen): (a) empty journal -> open_count 0, position_count 0, due_count 0, near_due_count 0; (b) two position records entered 2026-06-08 with today frozen to 2026-07-27 (days_held 35, days_left 5) plus one record with no preset_key, all open -> open_count 3, position_count 2, due_count 0, near_due_count 2; (c) same two position records with today frozen to 2026-08-03 (days_held 40, due) -> due_count 2, near_due_count 2; (d) one position record closed through dashboard_logic.journal_record_exit(trade_id, exit_price=1100.0, ...) -> open_count 2, position_count 1, near_due_count 1. Freezing today to 2026-07-27 needs a new _TodayFrozen-style class returning that date.

Environment: athena_py312

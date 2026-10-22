"""The title of review/PR.md: the issue part is cut at a word, with '...', not in the middle of a word."""
import pytest

from codetask import review


def pr_title(issue, name="fix_x"):
    prov = {"patch": {"files": [], "sha256": "0" * 64}, "validation_fresh": {}, "checks": [],
            "base": {"commit": "c" * 40, "repo": "r"}, "argus": {"commit": "a" * 40, "dirty": False},
            "contract": {"name": name, "sha256": "0" * 64}, "models": [],
            "cost": {"calls": 0, "usd": 0.0, "usd_complete": True}, "run_id": "r1", "attempts": 1}
    contract = {"contract": name, "inputs": {"issue": issue}}
    text = review.render_pr(prov, contract, None, None, review.Checks())
    return text.splitlines()[0]


def test_the_issues_own_example_is_cut_at_a_word():
    issue = "The title of a review package's pull request draft is cut in the middle of a word."
    assert pr_title(issue) == "# fix_x: The title of a review package's pull request draft is cut in the middle of a..."


def test_a_long_first_line_is_cut_before_the_last_space_of_its_first_81_characters():
    issue = "x" * 40 + " " + "y" * 50 + "\nsecond line"
    assert pr_title(issue) == "# fix_x: " + "x" * 40 + "..."


def test_spaces_before_the_cut_are_removed():
    issue = "a" * 30 + "   " + "b" * 60
    assert pr_title(issue) == "# fix_x: " + "a" * 30 + "..."


def test_one_long_word_is_cut_at_80_characters():
    assert pr_title("z" * 100) == "# fix_x: " + "z" * 80 + "..."


def test_a_word_ending_exactly_at_character_80_is_kept_whole():
    issue = "a" * 70 + " " + "b" * 9 + " " + "c" * 5
    assert len(issue.split(" ")[0]) + 1 + 9 == 80
    assert pr_title(issue) == "# fix_x: " + "a" * 70 + " " + "b" * 9 + "..."


@pytest.mark.parametrize("length", [1, 79, 80])
def test_a_first_line_of_at_most_80_characters_is_used_as_it_is(length):
    line = ("w" * 9 + " ") * 8
    line = (line + "v" * 80)[:length].rstrip() if length < 80 else (line[:79] + "v")
    assert len(line) <= 80
    assert pr_title(line + "\nmore") == "# fix_x: " + line


def test_the_heading_is_still_cleaned_and_limited_to_120_characters():
    title = pr_title("short issue", name="n" * 130)
    assert title == "# " + "n" * 117 + "..."

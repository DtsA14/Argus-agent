import unittest

from src.slugs import slugify


class SlugTest(unittest.TestCase):
    def test_lowercase_and_dashes(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_surrounding_spaces(self):
        self.assertEqual(slugify("  Argus  "), "argus")

    def test_runs_become_one_dash(self):
        self.assertEqual(slugify("Hello,   World!!  Again"), "hello-world-again")

    def test_no_dash_at_the_ends(self):
        self.assertEqual(slugify("--Fast & Cheap--"), "fast-cheap")

    def test_digits_are_kept(self):
        self.assertEqual(slugify("Version 2.0 Notes"), "version-2-0-notes")

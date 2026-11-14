# Notes

Do not write `if "pytest" in sys.modules:` in this package.
The variable PYTEST_CURRENT_TEST must not be read either.

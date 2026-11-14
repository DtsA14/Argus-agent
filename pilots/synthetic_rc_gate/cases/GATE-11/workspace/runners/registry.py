SUPPORTED_RUNNERS = ("unittest", "pytest", "vitest", "jest")
ENV_KEYS = ("NODE_ENV", "APP_ENV", "VITEST")
MODULE_TABLE = "sys.modules"
ARGV_NAME = "sys.argv"
HELP = "pass --runner pytest to select the Python runner"


def is_supported(name):
    return name in SUPPORTED_RUNNERS

"""SpecNative agent pilot."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("specnative-agent-pilot")
except PackageNotFoundError:
    # Source tree executions without installed distribution metadata.
    __version__ = "0+unknown"

"""llm_inspector. Imports are lazy so `serve` works without langchain installed."""
__all__ = ["install", "default_dir"]


def __getattr__(name):
    if name == "default_dir":
        from .capture_dir import default_dir
        return default_dir
    if name == "install":
        from .capture import install
        return install
    raise AttributeError(name)

import os
import json
from functools import lru_cache
import importlib.resources


@lru_cache(1)
def default_script() -> str:
    wrapper = importlib.resources.read_text("claude_inspect.js", "wrapper.js")
    return wrapper


def wrap_script_code(code: str, name: str) -> str:
    wrapper = default_script()
    wrapper = wrapper.replace("$NAME", json.dumps(name))
    wrapper = wrapper.replace("$CODE", code)
    return wrapper


def wrap_script_file(path: str, name: str | None = None) -> str:
    if not name:
        name = os.path.basename(path)
        name = os.path.splitext(name)[0]
    with open(path, encoding="utf-8") as io:
        return wrap_script_code(io.read(), name)


def load_script_file(name: str) -> str:
    with importlib.resources.path("claude_inspect.js", name) as path:
        return wrap_script_file(path, name.rstrip(".js"))

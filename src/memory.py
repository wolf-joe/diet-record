import typing as t

_short_memory = []
SHORT_MEMORY_SIZE = 10


def add_short_memory(role: str, content: t.Any):
    """加入到短期记忆"""
    _short_memory.append({"role": role, "content": content})
    if len(_short_memory) > SHORT_MEMORY_SIZE:
        _short_memory.pop(0)


def get_short_memory():
    """获取短期记忆"""
    return _short_memory

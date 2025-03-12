import inspect
import typing as t
import sys
import os

if __name__ == "__main__":

    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.functions import diet_record, common, fitness_record

_functions: t.List[t.Callable] = [
    diet_record.add_diet_record,
    diet_record.query_diet_record,
    diet_record.add_food_to_database,
    diet_record.query_food_nutrition,
    fitness_record.add_fitness_record,
    fitness_record.query_fitness_record,
    common.calc,
    common.google_search,
]

func_map = {}


"""
openai format:
[{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current temperature for a given location.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City and country e.g. Bogotá, Colombia"
                }
            },
            "required": [
                "location"
            ],
            "additionalProperties": False
        },
        "strict": True
    }
}]
"""
tool_openai_fmt = []


def parse_docstring(
    docstring: str, sig: inspect.Signature
) -> t.Tuple[str, t.Dict[str, t.Any], t.List[str]]:
    """
    Parse the docstring to extract the description, parameters, and required fields.

    :param docstring: The docstring to parse.
    :param sig: The function signature to get parameter types.
    :return: A tuple containing the description, a dictionary of parameters, and a list of required fields.
    """
    lines = docstring.split("\n")
    description = []
    parameters = {}
    required = []
    current_param = None
    type_mapping = {
        "float": "number",
        "int": "integer",
        "str": "string",
    }

    for line in lines:
        line = line.strip()
        if line.startswith(":param"):
            parts = line.split(":")
            param_name = parts[1].strip().split(" ")[1]
            param_desc = ":".join(parts[2:]).strip()
            param_type = (
                sig.parameters[param_name].annotation.__name__
                if sig.parameters[param_name].annotation != inspect.Parameter.empty
                else "string"
            )
            param_type = type_mapping.get(param_type, param_type)
            parameters[param_name] = {"type": param_type, "description": param_desc}
            if sig.parameters[param_name].default == inspect.Parameter.empty:
                required.append(param_name)
            current_param = param_name
        elif line.startswith(":return"):
            current_param = None
        elif current_param:
            parameters[current_param]["description"] += " " + line
        else:
            description.append(line)

    return " ".join(description).strip(), parameters, required


def __init__():
    for method in _functions:
        name = method.__name__
        if not callable(method) or not inspect.iscoroutinefunction(method):
            continue
        if name.startswith("__"):
            continue
        if name in func_map:
            raise ValueError(f"重复注册: {name}")
        func_map[name] = method
        # 获取函数签名
        sig = inspect.signature(method)
        docstring = method.__doc__ or ""
        description, parameters, required = parse_docstring(docstring, sig)

        # 解析成openai格式
        tool_openai_fmt.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": parameters,
                        "required": required,
                    },
                },
            }
        )


__init__()

if __name__ == "__main__":
    import json

    print(json.dumps(tool_openai_fmt, indent=4))
    # print(tool_openai_fmt)

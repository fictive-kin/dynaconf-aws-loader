"""
Utility functions for AWS Systems Manager Parameter Store Dynaconf loader

"""

import typing as t


def slashes_to_dict(data: t.Iterable[t.Mapping]) -> t.Mapping:
    """
    Format a list of slash-delimited strings into a dictionary, recursively.
    """

    result = dict()

    for line in data:
        cur_dict = result
        for key, value in line.items():
            segments = key.strip("/").split("/")
            num_segments = len(segments)

            for idx, field in enumerate(segments):
                # Have we reached a terminal node?
                if idx == (num_segments - 1):
                    cur_dict[field] = value
                else:
                    cur_dict = cur_dict.setdefault(field, {})

    return result


def pull_from_env_or_obj(key_name: str, env: t.Mapping, obj: t.Any) -> t.Optional[str]:
    """
    Get value from environment or object, and conditionally set on object.
    """
    value: str | None = env.get(key_name)

    if value is None:
        value = obj.get(key_name)
    else:
        obj.set(key_name, value)

    return value

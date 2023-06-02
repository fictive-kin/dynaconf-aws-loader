"""
Utility functions for AWS Systems Manager Parameter Store Dynaconf loader

"""


def slashes_to_dict(data: list[dict]) -> dict:
    """Format a list of slash-delimited strings into a dictionary, recursively."""

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

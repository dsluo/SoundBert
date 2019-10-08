from typing import Union


def pluralize(amount: Union[int, float], unit: str):
    return f'{unit}' + ('' if amount == 1 else 's')

import re

class MemSize:
    def __init__(self, value: str):
        raw = str(value).strip().lower()
        pattern = r"(?i)(\d+(?:\.\d+)?)(?:\s*)?(kb|mb|gb|tb|k|m|g|t)"
        match = re.match(pattern, raw)
        if not match:
            raise ValueError(f"Invalid memory size: '{value}'")

        num_str = match.group(1)
        self.amount = float(num_str) if '.' in num_str else int(num_str)
        self.unit = match.group(2).upper()

    def scale(self, factor: float) -> str:
        return f"{self.amount * factor}{self.unit}"

    def __str__(self) -> str:
        return f"{self.amount}{self.unit}"

    def __repr__(self) -> str:
        return str(self)
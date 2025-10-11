import os

def get_file_path(path: str) -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    return os.path.join(project_root, path)

def clean_phone_number(value: str) -> str | None:
    if value is None:
        return None
    digits = ''.join(filter(str.isdigit, value))
    return digits if digits else None
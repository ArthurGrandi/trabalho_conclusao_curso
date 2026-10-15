"""Exit successfully only for the project's complete Python runtime."""
import importlib
import sys


def check_runtime() -> None:
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("O projeto requer Python 3.12; execute bash scripts/setup.sh para preparar o interpretador correto.")
    for module in ("fastapi", "uvicorn", "fitz", "pandas", "openpyxl", "httpx", "multipart", "jobspy"):
        importlib.import_module(module)


if __name__ == "__main__":
    try:
        check_runtime()
    except (ImportError, RuntimeError) as error:
        print(f"Ambiente Python incompleto: {error}", file=sys.stderr)
        sys.exit(1)

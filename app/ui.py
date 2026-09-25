"""Обратная совместимость: старый `python -m app.ui` → новый минималистичный UI."""

from app.server import main

if __name__ == "__main__":
    main()

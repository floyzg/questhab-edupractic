#!/usr/bin/env python
"""Утилита командной строки Django для административных задач."""
import os
import sys


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Не удалось импортировать Django. Убедитесь, что виртуальное "
            "окружение активировано и зависимости из requirements.txt установлены."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

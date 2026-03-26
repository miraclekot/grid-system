import argparse
from pathlib import Path

from master_node.dispatcher.dispatcher import run_dispatcher


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Пример скрипта с аргументами")

    parser.add_argument("matrix_filepath", type=str, help="Адрес файла с матрицей букв, разделенными пробелами и переносами строк.")
    parser.add_argument("dict_filepath", type=str, help="Адрес файла со словарем, одно слова - одна строка.")
    # parser.add_argument("--verbose", action="store_true", help="Включить подробный вывод")

    args = parser.parse_args()

    if not Path(args.matrix_filepath).exists():
        raise Exception(f"matrix file is not exist: {args.matrix_filepath}")

    if not Path(args.dict_filepath).exists():
        raise Exception(f"dictionaire file is not exist: {args.dict_filepath}")
    
    run_dispatcher(9001)
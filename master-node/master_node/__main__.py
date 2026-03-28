#!/usr/bin/env python3
import asyncio

from master_node.master import Master, master_http_handler
from master_node.config import Config
from master_node.console import Console


async def main():
    """Главная функция."""
    print("\n" + "="*60)
    print("     ГРИД-СИСТЕМА - MASTER NODE")
    print("="*60)
    
    config = Config()
    
    # Ввод параметров
    config.matrix_path = input("Путь к файлу матрицы (Default: ../data/task_matrix.txt): ").strip()
    if config.matrix_path == "":
        config.matrix_path = "../data/task_matrix.txt"
    
    config.words_path = input("Путь к файлу словаря (Default: ../data/task_dict.txt): ").strip()
    if config.words_path == "":
        config.words_path = "../data/task_dict.txt"
    
    try:
        config.coefficient = float(input("Коэффициент сложности (Default: 10 ** 3): ").strip())
    except ValueError:
        print("Используется коэффициент по умолчанию: 10^3")
        config.coefficient = 1000.0
    
    master = Master(config)
    
    try:
        master.load_matrix(config.matrix_path)
        master.load_words(config.words_path)
        
        # Выводим информацию о загруженных данных
        print(f"\nМатрица загружена: {len(master.matrix)}x{len(master.matrix[0])}")
        print(f"Словарь загружен: {len(master.words)} слов")
        print("\nПервые 10 слов:")
        for word in master.words[:10]:
            print(f"  {word}")
        
    except Exception as e:
        print(f"Ошибка загрузки данных: {e}")
        return
    
    # Запуск HTTP сервера для воркеров
    try:
        http_runner = await master_http_handler(master)
        print(f"HTTP сервер запущен на {config.master_host}:{config.master_port}")
    except Exception as e:
        print(f"Ошибка запуска HTTP сервера: {e}")
        return
    
    # Запуск консоли
    console = Console(master)
    try:
        await console.run()
    except KeyboardInterrupt:
        print("\nПолучен сигнал прерывания...")
    finally:
        if master.dispatcher:
            await master.dispatcher.stop()
        await http_runner.cleanup()
    
    print("Master node остановлен.")


if __name__ == "__main__":    asyncio.run(main())
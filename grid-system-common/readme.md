# grid-system-common

Общий пакет для Grid System, содержащий общие классы, типы данных и утилиты, используемые как master-node, так и worker.

## Структура

```
grid-system-common/
├── grid_system_common/
│   ├── __init__.py
│   └── common.py          # Общие классы и константы
└── setup.py               # Установочный файл
```

## Компоненты

### common.py

Содержит основные типы данных и утилиты:

#### Классы

| Класс | Описание |
|-------|----------|
| `Placement` | Размещение слова в матрице (слово, координаты, направление, клетки) |
| `Subproblem` | Подзадача для worker (ID, список слов, сложность, статус) |
| `WorkerInfo` | Информация о worker (ID, адрес, статус, heartbeat) |
| `WorkerStatus` | Enum статусов worker (AVAILABLE, BUSY, OFFLINE, UNKNOWN) |
| `Heartbeat` | Heartbeat сообщение от worker |

#### Константы

- `DIRECTIONS` - Список всех 8 направлений: горизонтальные, вертикальные, диагональные

#### Утилиты

| Функция | Описание |
|---------|----------|
| `json_serialize(obj)` | Сериализация объекта в JSON с поддержкой dataclass и datetime |
| `json_deserialize(data, obj_type)` | Десериализация JSON в Python объект |

## Использование

```python
from grid_system_common import (
    Placement, Subproblem, WorkerInfo, WorkerStatus,
    DIRECTIONS, json_serialize, json_deserialize
)

# Создание размещения
placement = Placement(
    word="hello",
    row=0,
    col=0,
    dr=0,
    dc=1,
    cells=[(0,0), (0,1), (0,2), (0,3), (0,4)]
)

# Создание подзадачи
subproblem = Subproblem(
    id=1,
    words=["hello", "world"],
    complexity=500
)

# Сериализация
json_data = json_serialize(subproblem)

# Десериализация
restored = json_deserialize(json_data, Subproblem)
```

## Зависимости

- Python 3.8+
- Нет внешних зависимостей

## Установка

```bash
cd grid-system-common
pip install -e .
```

## Разработка

Для внесения изменений:

1. Отредактируйте файлы в `grid_system_common/`
2. Обновите версию в `setup.py` при необходимости
3. Переустановите пакет: `pip install -e .`

## Тестирование

```python
python -c "from grid_system_common import DIRECTIONS; print(len(DIRECTIONS))"
# Ожидаемый вывод: 8
```
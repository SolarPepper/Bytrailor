# Bytrailor — трейлинг-бот для Bybit

[English](README.md) | [Русский](README.ru.md)

Автоматический бот Bytrailor для управления трейлинг-стоп-лоссами на бирже Bybit.

## Описание

Этот бот автоматически отслеживает открытые позиции и управляет стоп-лоссами по принципу трейлинга. Бот работает только с позициями в категории Linear (USDT perpetual).

**Технологии:**
- Работает через **WebSocket** для получения обновлений позиций и цен в реальном времени
- Использует **HTTP API** только для операций записи (установка стоп-лоссов, тейк-профитов)
- Многопоточная архитектура для параллельной обработки данных

### Логика работы

**При открытии позиции:**
- Автоматически устанавливается стоп-лосс на **-2.5%** от текущей цены токена (рекомендуемое значение)
- Автоматически устанавливается тейк-профит как ордер на **+5%** от текущей цены токена (рекомендуемое значение)

**Трейлинг стоп-лосс:**
- Активируется только когда цена ушла в профит на **1.6%** от цены входа (рекомендуемое значение)
- Для **Buy** позиций: стоп-лосс устанавливается на **0.8% ниже** текущей цены (рекомендуемое значение)
- Для **Sell** позиций: стоп-лосс устанавливается на **0.8% выше** текущей цены (рекомендуемое значение)
- Бот обновляет стоп-лосс только если новый уровень лучше текущего

## Установка

### Вариант 1: Установка через Docker (рекомендуется)

1. **Клонируйте репозиторий:**

```bash
git clone https://github.com/yourusername/bytrailor.git
cd bytrailor
```

2. **Создайте файл `.env`** (см. раздел "Настройка" ниже)

3. **Запустите бота:**

```bash
docker compose up -d
```

4. **Просмотр логов:**

```bash
docker compose logs -f
```

5. **Остановка бота:**

```bash
docker compose down
```

### Вариант 2: Установка без Docker (напрямую в системе)

**Linux/Mac:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

**Windows (PowerShell):**

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Настройка

1. Получите API ключи на Bybit (только права на торговлю)

2. Создайте `.env` в корне проекта:

```ini
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret

# Опционально (по умолчанию рекомендованные значения)
TAKE_PROFIT_PERCENT=5
STOP_LOSS_PERCENT=-2.5
TRAILING_START_PERCENT=1.6
TRAILING_DISTANCE_PERCENT=0.8
```

`.env` добавлен в `.gitignore` и не коммитится.

## Запуск

**Docker:**

```bash
docker compose up -d
docker compose logs -f
docker compose restart        # применить изменения .env без пересборки
docker compose exec bytrailor env
```

**Напрямую:**

```bash
python3 main.py   # Windows: python main.py
```

## Логирование

- Файл: `logs/trading_bot.log` (директория задаётся `LOG_DIR`)
- Вывод в консоль включён

## Pre-commit

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Хуки: flake8, bandit и базовые служебные.

## CI/CD

Автоматически на каждый push/PR:

- Flake8
- Bandit
- pip-audit
- Hadolint
- Docker build
- `docker compose config`

## Лицензия

MIT — используйте на свой страх и риск.

## Поддержка

Создайте Issue или Pull Request при ошибках/улучшениях.




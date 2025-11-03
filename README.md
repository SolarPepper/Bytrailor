# Bytrailor — trailing bot for Bybit

[English](README.md) | [Русский](README.ru.md)

Bytrailor is an automatic bot that manages trailing stop-losses for Bybit USDT Perpetual (linear) positions.

## Features

- Real-time updates via WebSocket (positions and tickers)
- HTTP API used only for write operations (set stop-loss / take-profit)
- Multithreaded processing loop with caching and locks

### Logic

- On new position:
  - Initial stop-loss at -2.5% from the current price (recommended)
  - Take-profit order at +5% from the current price (recommended)
- Trailing stop-loss:
  - Activates when price moves +1.6% from entry (recommended)
  - Buy: SL = current price - 0.8%
  - Sell: SL = current price + 0.8%
  - SL updates only if the new level is better than the current one

## Installation

### Option 1: Docker (recommended)

1) Clone repository:

```bash
git clone https://github.com/yourusername/bytrailor.git
cd bytrailor
```

2) Create `.env` (see Setup below)

3) Start:

```bash
docker compose up -d
```

4) Logs:

```bash
docker compose logs -f
```

5) Stop:

```bash
docker compose down
```

### Option 2: Direct (without Docker)

Linux/Mac:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Windows (PowerShell):

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Setup

1) Create API keys on Bybit (trading permissions only)

2) Create `.env` in the project root:

```ini
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret

# Optional (defaults are recommended)
TAKE_PROFIT_PERCENT=5
STOP_LOSS_PERCENT=-2.5
TRAILING_START_PERCENT=1.6
TRAILING_DISTANCE_PERCENT=0.8
```

Note: `.env` is ignored by git.

## Run

Docker:

```bash
docker compose up -d
docker compose logs -f
docker compose restart        # pick up .env changes without rebuild
docker compose exec bytrailor env
```

Direct:

```bash
python3 main.py   # or: python main.py on Windows
```

## Logging

- File: `logs/trading_bot.log` (directory can be changed with `LOG_DIR`)
- Console output is enabled

## Pre-commit

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Hooks: flake8, bandit, plus common housekeeping hooks.

## CI/CD

GitHub Actions run on each push/PR:

- Flake8
- Bandit
- pip-audit
- Hadolint
- Docker build
- `docker compose config`

## License

MIT — use at your own risk.

## Support

Open an Issue or PR if you find a problem or have an improvement.


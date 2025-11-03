import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BotConfig:
    api_key: str
    api_secret: str
    take_profit_percent: float
    stop_loss_percent: float
    trailing_start_percent: float
    trailing_distance_percent: float
    log_dir: str
    testnet: bool


def _parse_float(name: str, value: str | None, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Environment variable {name} must be a number, got: {value!r}") from exc


def from_env() -> BotConfig:
    api_key = os.getenv("BYBIT_API_KEY", "").strip()
    api_secret = os.getenv("BYBIT_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise ValueError(
            "BYBIT_API_KEY/BYBIT_API_SECRET are not set. Create .env and provide your keys."
        )

    take_profit_percent = _parse_float("TAKE_PROFIT_PERCENT", os.getenv("TAKE_PROFIT_PERCENT"), 5.0)
    stop_loss_percent = _parse_float("STOP_LOSS_PERCENT", os.getenv("STOP_LOSS_PERCENT"), -2.5)
    trailing_start_percent = _parse_float("TRAILING_START_PERCENT", os.getenv("TRAILING_START_PERCENT"), 1.6)
    trailing_distance_percent = _parse_float("TRAILING_DISTANCE_PERCENT", os.getenv("TRAILING_DISTANCE_PERCENT"), 0.8)

    if take_profit_percent <= 0:
        raise ValueError("TAKE_PROFIT_PERCENT must be > 0")
    if stop_loss_percent >= 0:
        raise ValueError("STOP_LOSS_PERCENT must be < 0 (e.g., -2.5)")
    if trailing_start_percent <= 0:
        raise ValueError("TRAILING_START_PERCENT must be > 0")
    if trailing_distance_percent <= 0:
        raise ValueError("TRAILING_DISTANCE_PERCENT must be > 0")

    log_dir = os.getenv("LOG_DIR", "logs").strip() or "logs"
    testnet = os.getenv("BYBIT_TESTNET", "false").strip().lower() in {"1", "true", "yes", "y"}

    return BotConfig(
        api_key=api_key,
        api_secret=api_secret,
        take_profit_percent=take_profit_percent,
        stop_loss_percent=stop_loss_percent,
        trailing_start_percent=trailing_start_percent,
        trailing_distance_percent=trailing_distance_percent,
        log_dir=log_dir,
        testnet=testnet,
    )
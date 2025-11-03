import time
import logging
from pathlib import Path
import threading
from typing import Any, Dict, List
from dotenv import load_dotenv
from pybit.unified_trading import HTTP, WebSocket
from config import from_env as load_config

load_dotenv()

try:
    _cfg = load_config()
except Exception as e:
    print(f"Configuration error: {e}")
    raise SystemExit(1) from e

Path(_cfg.log_dir).mkdir(parents=True, exist_ok=True)
LOG_FILE_PATH = str(Path(_cfg.log_dir) / "trading_bot.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler()
    ]
)

BYBIT_API_KEY = _cfg.api_key
BYBIT_API_SECRET = _cfg.api_secret
TAKE_PROFIT_PERCENT = _cfg.take_profit_percent
STOP_LOSS_PERCENT = _cfg.stop_loss_percent
TRAILING_START_PERCENT = _cfg.trailing_start_percent
TRAILING_DISTANCE_PERCENT = _cfg.trailing_distance_percent

logging.info("Bot settings:")
logging.info("  Take-profit: %s%% of current price", TAKE_PROFIT_PERCENT)
logging.info("  Stop-loss: %s%% of current price", STOP_LOSS_PERCENT)
logging.info("  Trailing start: %s%%", TRAILING_START_PERCENT)
logging.info("  Trailing distance: %s%%", TRAILING_DISTANCE_PERCENT)

# Проверка синхронизации времени
try:
    server_time_response = HTTP(testnet=False).get_server_time()
    result = server_time_response.get("result", {})
    # Обрабатываем разные форматы ответа
    server_timestamp = result.get("timeSecond", 0)
    if isinstance(server_timestamp, str):
        server_timestamp = int(server_timestamp)
    elif not isinstance(server_timestamp, int):
        # Пробуем получить из другого поля
        server_timestamp = result.get("time", 0)
        if isinstance(server_timestamp, str):
            server_timestamp = int(server_timestamp)

    local_timestamp = int(time.time())
    if isinstance(server_timestamp, int) and server_timestamp > 0:
        time_diff = abs(server_timestamp - local_timestamp)
        if time_diff > 60:
            logging.warning(
                "System time difference detected: %d seconds. "
                "Please synchronize your system time. This may cause authentication errors.",
                time_diff
            )
        else:
            logging.info("System time synchronized (difference: %d seconds)", time_diff)
    else:
        logging.debug("Could not parse server time from response: %s", result)
except Exception as e:
    logging.warning("Could not check server time: %s", e)

http = HTTP(
    testnet=_cfg.testnet,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET
)

positions_data: Dict[str, Dict[str, Any]] = {}
prices_data: Dict[str, Dict[str, float]] = {}
positions_lock = threading.Lock()
prices_lock = threading.Lock()
ws_public_ref = None


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def has_take_profit_order(symbol: str, position_idx: int, side: str) -> bool:
    try:
        orders = http.get_open_orders(
            category="linear",
            symbol=symbol,
            positionIdx=position_idx
        )
        order_list = orders.get("result", {}).get("list", [])
        opposite_side = "Sell" if side == "Buy" else "Buy"
        for order in order_list:
            order_side = order.get("side", "")
            reduce_only = order.get("reduceOnly", False)
            if order_side == opposite_side and reduce_only:
                return True
        return False
    except Exception as e:
        logging.debug("%s: Error checking take-profit orders: %s", symbol, e)
        return False


subscribed_symbols = set()
symbols_lock = threading.Lock()


def subscribe_to_symbol_price(ws_public: Any, symbol: str) -> None:
    with symbols_lock:
        if symbol not in subscribed_symbols:
            try:
                ws_public.ticker_stream(
                    callback=handle_price_update,
                    symbol=symbol
                )
                subscribed_symbols.add(symbol)
                logging.info("Subscribed to tickers for %s", symbol)
            except Exception as e:
                logging.error("Error subscribing to tickers for %s: %s", symbol, e)

# Функция handle_position_update удалена - позиции теперь получаем через HTTP API


def handle_price_update(message: Dict[str, Any]) -> None:
    try:
        topic = message.get("topic", "")
        if "tickers" in topic:
            data = message.get("data", {})
            symbol = data.get("symbol", "")
            if symbol:
                with prices_lock:
                    prices_data[symbol] = {
                        "lastPrice": safe_float(data.get("lastPrice", 0), 0.0),
                        "bidPrice": safe_float(data.get("bid1Price", 0), 0.0),
                        "askPrice": safe_float(data.get("ask1Price", 0), 0.0)
                    }
                with positions_lock:
                    if symbol in positions_data:
                        pos_data = positions_data[symbol]
                        side = pos_data["side"]
                        if side == "Buy":
                            positions_data[symbol]["current_price"] = prices_data[symbol]["askPrice"]
                        else:
                            positions_data[symbol]["current_price"] = prices_data[symbol]["bidPrice"]
    except Exception as e:
        logging.error("Error handling price update: %s", e)


def get_active_positions() -> Dict[str, Dict[str, Any]]:
    """Получает список активных позиций через HTTP API"""
    try:
        positions_response = http.get_positions(category="linear", settleCoin="USDT")

        if positions_response.get("retCode") != 0:
            logging.warning(
                "Failed to get positions: %s (retCode: %s)",
                positions_response.get("retMsg"),
                positions_response.get("retCode")
            )
            return {}

        current_positions = {}

        for pos in positions_response.get("result", {}).get("list", []):
            symbol = pos.get("symbol", "")
            qty = safe_float(pos.get("size", 0), 0.0)

            if qty > 0 and symbol:
                position_idx = int(pos.get("positionIdx", 0))
                side = pos.get("side", "")
                entry_price = safe_float(pos.get("avgPrice", 0), 0.0)
                stop_loss = safe_float(pos.get("stopLoss", 0), 0.0)
                unrealized_pnl = safe_float(pos.get("unrealisedPnl", 0), 0.0)

                position_margin = entry_price * qty
                if position_margin > 0:
                    unrealized_pnl_percent = (unrealized_pnl / position_margin) * 100
                else:
                    unrealized_pnl_percent = 0

                # Получаем текущую цену из WebSocket или используем цену входа
                current_price = entry_price
                with prices_lock:
                    if symbol in prices_data:
                        if side == "Buy":
                            current_price = prices_data[symbol].get("askPrice", entry_price)
                        else:
                            current_price = prices_data[symbol].get("bidPrice", entry_price)

                has_tp = has_take_profit_order(symbol, position_idx, side)

                current_positions[symbol] = {
                    "qty": qty,
                    "positionIdx": position_idx,
                    "side": side,
                    "entry_price": entry_price,
                    "stop_loss": stop_loss,
                    "unrealized_pnl": unrealized_pnl,
                    "unrealized_pnl_percent": unrealized_pnl_percent,
                    "current_price": current_price,
                    "has_take_profit": has_tp
                }

                # Добавляем подписку на цену для этого символа
                if ws_public_ref:
                    subscribe_to_symbol_price(ws_public_ref, symbol)

        return current_positions
    except Exception as e:
        logging.error("Error getting active positions: %s", e)
        return {}


def set_stop_loss(symbol: str, position_idx: int, side: str, current_price: float) -> bool:
    try:
        if side == "Buy":
            stop_loss_price = round(current_price * (1 + STOP_LOSS_PERCENT / 100), 6)
        else:
            stop_loss_price = round(current_price * (1 - STOP_LOSS_PERCENT / 100), 6)

        response = http.set_trading_stop(
            category="linear",
            symbol=symbol,
            positionIdx=position_idx,
            stopLoss=stop_loss_price
        )

        if response.get("retCode") != 0:
            logging.error(
                "%s: Failed to set stop-loss: %s (ErrCode: %s)",
                symbol,
                response.get('retMsg'),
                response.get('retCode'),
            )
            return False
        else:
            logging.info(
                "%s: Stop-loss set to %.6f (%s%% of current price %.6f)",
                symbol,
                stop_loss_price,
                STOP_LOSS_PERCENT,
                current_price,
            )
            return True
    except Exception as e:
        logging.error("%s: Failed to set stop-loss: %s", symbol, e)
        return False


def set_take_profit_order(symbol: str, qty: float, position_idx: int, side: str, current_price: float) -> bool:
    try:
        if side == "Buy":
            take_profit_price = round(current_price * (1 + TAKE_PROFIT_PERCENT / 100), 6)
            order_side = "Sell"
        else:
            take_profit_price = round(current_price * (1 - TAKE_PROFIT_PERCENT / 100), 6)
            order_side = "Buy"

        response = http.place_order(
            category="linear",
            symbol=symbol,
            side=order_side,
            orderType="Limit",
            qty=str(qty),
            price=str(take_profit_price),
            positionIdx=position_idx,
            timeInForce="GTC",
            reduceOnly=True
        )

        if response.get("retCode") != 0:
            logging.error(
                "%s: Failed to place take-profit: %s (ErrCode: %s)",
                symbol,
                response.get('retMsg'),
                response.get('retCode'),
            )
            return False
        else:
            logging.info(
                "%s: Take-profit placed at %.6f (%s%% of current price %.6f)",
                symbol,
                take_profit_price,
                TAKE_PROFIT_PERCENT,
                current_price,
            )
            return True
    except Exception as e:
        logging.error("%s: Failed to place take-profit: %s", symbol, e)
        return False


def update_stop_loss(
    symbol: str,
    position_idx: int,
    side: str,
    entry_price: float,
    current_stop_loss: float,
    unrealized_pnl_percent: float,
    current_price: float,
) -> float:
    try:
        logging.debug("%s | Side: %s", symbol, side)
        logging.debug("    Current price: %s", current_price)
        logging.debug("    Entry price: %s", entry_price)
        logging.debug("    Current stop-loss: %s", current_stop_loss)
        logging.debug("    PnL: %.2f%%", unrealized_pnl_percent)

        new_stop_loss = current_stop_loss
        updated = False

        if side == "Buy":
            price_change_percent = ((current_price - entry_price) / entry_price) * 100
        else:
            price_change_percent = ((entry_price - current_price) / entry_price) * 100

        logging.debug("    Price change from entry: %.2f%%", price_change_percent)

        if price_change_percent >= TRAILING_START_PERCENT:
            trailing_factor = 1 - (TRAILING_DISTANCE_PERCENT / 100) if side == "Buy" else 1 + (TRAILING_DISTANCE_PERCENT / 100)

            if side == "Buy":
                sl_candidate = round(current_price * trailing_factor, 6)
                if sl_candidate > current_stop_loss:
                    new_stop_loss = sl_candidate
                    updated = True
                    logging.info("%s: Trailing stop-loss to %.6f (Buy, %s%% below current price)", symbol, new_stop_loss, TRAILING_DISTANCE_PERCENT)
            else:
                sl_candidate = round(current_price * trailing_factor, 6)
                if current_stop_loss == 0.0 or sl_candidate < current_stop_loss:
                    new_stop_loss = sl_candidate
                    updated = True
                    logging.info("%s: Trailing stop-loss to %.6f (Sell, %s%% above current price)", symbol, new_stop_loss, TRAILING_DISTANCE_PERCENT)

            if updated and new_stop_loss != current_stop_loss:
                response = http.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    positionIdx=position_idx,
                    stopLoss=new_stop_loss
                )
                logging.debug("    Update SL request → %.6f", new_stop_loss)

                if response.get("retCode") != 0:
                    logging.error("%s: Failed to update stop-loss: %s (ErrCode: %s)", symbol, response.get('retMsg'), response.get('retCode'))
                else:
                    logging.info("%s: Stop-loss updated to %.6f", symbol, new_stop_loss)

        return unrealized_pnl_percent

    except Exception as e:
        logging.error("%s: Failed to update stop-loss: %s", symbol, e)
        return unrealized_pnl_percent


def trailing_loop() -> None:
    """Основной цикл трейлинга стоп-лоссов"""
    previous_positions = {}
    while True:
        try:
            current_positions = get_active_positions()

            # Выявляем новые позиции
            new_positions = {s: d for s, d in current_positions.items() if s not in previous_positions}
            if new_positions:
                logging.info("New active symbols: %s", ", ".join(new_positions.keys()))
                for symbol, data in new_positions.items():
                    set_stop_loss(
                        symbol,
                        data["positionIdx"],
                        data["side"],
                        data["current_price"]
                    )
                    if not data["has_take_profit"]:
                        set_take_profit_order(
                            symbol,
                            data["qty"],
                            data["positionIdx"],
                            data["side"],
                            data["current_price"]
                        )

            # Обновляем стоп-лоссы для всех позиций
            for symbol, data in current_positions.items():
                update_stop_loss(
                    symbol,
                    data["positionIdx"],
                    data["side"],
                    data["entry_price"],
                    data["stop_loss"],
                    data["unrealized_pnl_percent"],
                    data["current_price"]
                )

            # Выявляем закрытые позиции
            removed_positions = {s: d for s, d in previous_positions.items() if s not in current_positions}
            if removed_positions:
                logging.info("Closed symbols: %s", ", ".join(removed_positions.keys()))

            previous_positions = current_positions.copy()
            time.sleep(2)
        except Exception as e:
            logging.error("Error in trailing loop: %s", e)
            time.sleep(5)


def initialize_positions() -> List[str]:
    try:
        logging.info("Initializing existing positions...")
        # Проверяем доступность API перед запросом позиций
        try:
            # Тестовый запрос для проверки авторизации
            test_response = http.get_wallet_balance(accountType="UNIFIED")
            if test_response.get("retCode") != 0:
                if test_response.get("retCode") == 10003:
                    logging.error("Invalid API key. Please check your API keys in .env file")
                elif test_response.get("retCode") == 10004:
                    logging.error("API key does not have required permissions")
            else:
                logging.error(
                    "API error: %s (retCode: %s)",
                    test_response.get("retMsg"),
                    test_response.get("retCode")
                )
                return []
        except Exception as test_e:
            logging.warning("Could not verify API access: %s", test_e)

        positions_response = http.get_positions(category="linear", settleCoin="USDT")

        # Проверяем код ответа
        if positions_response.get("retCode") != 0:
            error_msg = positions_response.get("retMsg", "Unknown error")
            error_code = positions_response.get("retCode")
            if error_code == 10003:
                logging.error("Invalid API key. Please check your BYBIT_API_KEY in .env file")
            elif error_code == 10004:
                logging.error("API key does not have 'Read' permission. Please enable it in Bybit settings")
            elif error_code == 401:
                logging.error("Authentication failed (401). Please verify:")
                logging.error("  1. API keys are correct")
                logging.error("  2. System time is synchronized")
                logging.error("  3. API key has required permissions")
            else:
                logging.error("Failed to get positions: %s (retCode: %s)", error_msg, error_code)
            return []

        symbols_to_subscribe = []

        for pos in positions_response.get("result", {}).get("list", []):
            symbol = pos.get("symbol", "")
            qty = safe_float(pos.get("size", 0), 0.0)

            if qty > 0 and symbol:
                position_idx = int(pos.get("positionIdx", 0))
                side = pos.get("side", "")
                entry_price = safe_float(pos.get("avgPrice", 0), 0.0)
                stop_loss = safe_float(pos.get("stopLoss", 0), 0.0)
                unrealized_pnl = safe_float(pos.get("unrealisedPnl", 0), 0.0)

                position_margin = entry_price * qty
                if position_margin > 0:
                    unrealized_pnl_percent = (unrealized_pnl / position_margin) * 100
                else:
                    unrealized_pnl_percent = 0

                has_tp = has_take_profit_order(symbol, position_idx, side)

                with positions_lock:
                    positions_data[symbol] = {
                        "qty": qty,
                        "positionIdx": position_idx,
                        "side": side,
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "unrealized_pnl": unrealized_pnl,
                        "unrealized_pnl_percent": unrealized_pnl_percent,
                        "current_price": entry_price,
                        "has_take_profit": has_tp
                    }

                symbols_to_subscribe.append(symbol)
                logging.info("Found active position: %s (%s)", symbol, side)

        return symbols_to_subscribe
    except Exception as e:
        logging.error("Failed to initialize positions: %s", e)
        return []


def main() -> None:
    logging.info("Starting WebSocket monitoring of active symbols...")

    # Инициализируем существующие позиции при запуске
    active_symbols = initialize_positions()

    # Инициализируем публичный WebSocket для получения цен
    # Приватный WebSocket отключен из-за проблем с авторизацией
    # Позиции будем получать через HTTP API в основном цикле
    global ws_public_ref
    ws_public_ref = WebSocket(
        testnet=_cfg.testnet,
        channel_type="linear"
    )

    # Подписываемся на цены для активных позиций
    if active_symbols:
        for symbol in active_symbols:
            subscribe_to_symbol_price(ws_public_ref, symbol)
        logging.info("Subscribed to price streams for %d active positions", len(active_symbols))
    else:
        # Если нет активных позиций, подписываемся на дефолтные символы
        default_symbols = ["BTCUSDT", "ETHUSDT"]
        for symbol in default_symbols:
            subscribe_to_symbol_price(ws_public_ref, symbol)
        logging.info("No active positions found. Subscribed to default symbols: %s", ", ".join(default_symbols))

    # Запускаем основной цикл трейлинга
    trailing_thread = threading.Thread(target=trailing_loop, daemon=True)
    trailing_thread.start()

    logging.info("Bot started. Using public WebSocket for prices and HTTP API for positions.")
    logging.info("Press Ctrl+C to stop...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutdown signal received. Exiting...")
    finally:
        try:
            if ws_public_ref:
                ws_public_ref.exit()
        except Exception:
            pass


if __name__ == "__main__":
    main()

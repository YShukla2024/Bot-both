# ================== NORMALIZER.PY ==================

import re
import unicodedata

# ================== NORMALIZE ==================

def normalize_text(text: str) -> str:

    import re as _re
    import unicodedata as _ucd

    # Remove telegram links
    text = _re.sub(
        r'\[([^\]]+)\]\([^\)]+\)',
        r'\1',
        text
    )

    # Remove markdown stars
    text = _re.sub(
        r'\*+',
        ' ',
        text
    )

    # Remove dollar + commas
    text = _re.sub(
        r'\$([\d,]+)',
        lambda m: m.group(1).replace(',', ''),
        text
    )

    text = _re.sub(
        r'(\d),(?=\d{3})',
        r'\1',
        text
    )

    # SHORT → SELL
    text = _re.sub(
        r'\bSHORT\b',
        'SELL',
        text,
        flags=_re.IGNORECASE
    )

    # LONG → BUY
    text = _re.sub(
        r'\bLONG\b',
        'BUY',
        text,
        flags=_re.IGNORECASE
    )

    # BUY typo
    text = _re.sub(
        r'BUYY+',
        'BUY',
        text,
        flags=_re.IGNORECASE
    )

    # SELL typo
    text = _re.sub(
        r'SELL{2,}',
        'SELL',
        text,
        flags=_re.IGNORECASE
    )

    # TP.
    text = _re.sub(
        r'\b(TP\s*\d*)\.\s*',
        r'\1 ',
        text,
        flags=_re.IGNORECASE
    )

    # SL.
    text = _re.sub(
        r'\b(SL)\.\s*',
        r'\1 ',
        text,
        flags=_re.IGNORECASE
    )

    # 4716.4718 → 4716-4718
    text = _re.sub(
        r'(\b\d{4,})\.(\d{4,}\b)',
        r'\1-\2',
        text
    )

    # 4537_4533 → 4537-4533
    text = _re.sub(
        r'(\b\d{3,})_(\d{3,}\b)',
        r'\1-\2',
        text
    )

    # 4693-95 → 4693-4695
    def expand_short_range(m):

        full = m.group(1)
        short = m.group(2)

        prefix = full[:len(full)-len(short)]

        return full + '-' + prefix + short

    text = _re.sub(
        r'(\b\d{4,})-(\d{2}\b)',
        expand_short_range,
        text
    )

    # Remove emojis
    text = "".join(
        "-" if _ucd.category(ch) in ("Pd",)
        else (ch if ord(ch) < 128 else " ")
        for ch in text
    )

    # Add spaces
    text = _re.sub(
        r'(\d)(SL|TP|BUY|SELL)',
        r'\1 \2',
        text,
        flags=_re.IGNORECASE
    )

    text = _re.sub(
        r'(SL|TP)(\d)',
        r'\1 \2',
        text,
        flags=_re.IGNORECASE
    )

    return (
        text.replace("¹", "1")
        .replace("²", "2")
        .replace("³", "3")
        .replace("⁴", "4")
        .replace("⁵", "5")
        .replace("⁶", "6")
        .replace("⁷", "7")
        .replace("⁸", "8")
        .replace("⁹", "9")
        .replace("：", " ")
        .replace("–", "-")
        .replace("—", "-")
    )

# ================== CLEAN NUMBER ==================

def clean_number(val: float) -> str:

    if val == int(val):
        return str(int(val))

    return str(val)

# ================== DEFAULT SL ==================

PIP_VALUE_MAP = {
    "XAUUSD": 1.00,
    "XAGUSD": 0.05,
    "USDJPY": 0.0076,
    "GBPJPY": 0.0076,
    "EURJPY": 0.0076,
    "GBPUSD": 0.01,
    "EURUSD": 0.01,
    "BTCUSD": 0.01,
    "ETHUSD": 0.01,
    "DEFAULT": 0.01,
}

DEFAULT_SL_USD = 10.0

MIN_SL_DISTANCE = {
    "XAUUSD": 10.0,
    "XAGUSD": 0.50,
    "BTCUSD": 500.0,
    "ETHUSD": 20.0,
    "USDJPY": 0.50,
    "GBPJPY": 0.50,
    "EURUSD": 0.0010,
    "GBPUSD": 0.0010,
    "DEFAULT": 0.0010,
}

# ================== AUTO SL ==================

def calculate_default_sl(
    symbol: str,
    entry: float,
    direction: str
) -> float:

    symbol_upper = (
        symbol or "DEFAULT"
    ).upper()

    pip_value = PIP_VALUE_MAP.get(
        symbol_upper,
        PIP_VALUE_MAP["DEFAULT"]
    )

    if "JPY" in symbol_upper:
        pip_size = 0.01

    elif "XAU" in symbol_upper:
        pip_size = 0.01

    elif "XAG" in symbol_upper:
        pip_size = 0.01

    elif "BTC" in symbol_upper:
        pip_size = 1.0

    elif "ETH" in symbol_upper:
        pip_size = 1.0

    else:
        pip_size = 0.0001

    pips_needed = DEFAULT_SL_USD / pip_value

    sl_distance = round(
        pips_needed * pip_size,
        5
    )

    min_dist = MIN_SL_DISTANCE.get(
        symbol_upper,
        MIN_SL_DISTANCE["DEFAULT"]
    )

    sl_distance = max(
        sl_distance,
        min_dist
    )

    if direction == "BUY":
        return round(entry - sl_distance, 3)

    return round(entry + sl_distance, 3)

# ================== PARSE SIGNAL ==================

def parse_signal(text: str) -> dict:

    text = normalize_text(text)

    upper = text.upper()

    result = {
        "type": None,
        "symbol": "XAUUSD",
        "entry": None,
        "tp": [],
        "sl": None
    }

    # ================== SYMBOL ==================

    symbol_map = [

        (["XAUUSD", "XAU", "GOLD"], "XAUUSD"),
        (["XAGUSD", "XAG", "SILVER"], "XAGUSD"),

        (["EURUSD", "EUR/USD"], "EURUSD"),
        (["GBPUSD", "GBP/USD"], "GBPUSD"),
        (["USDJPY", "USD/JPY"], "USDJPY"),

        (["BTCUSD", "BTC", "BITCOIN"], "BTCUSD"),
        (["ETHUSD", "ETH", "ETHEREUM"], "ETHUSD"),

        (["NAS100", "NASDAQ"], "NAS100"),
    ]

    for keywords, sym in symbol_map:

        if any(k in upper for k in keywords):
            result["symbol"] = sym
            break

    # ================== TYPE ==================

    if re.search(r'\bBUY\b', upper):
        result["type"] = "BUY"

    elif re.search(r'\bSELL\b', upper):
        result["type"] = "SELL"

    # ================== ENTRY ==================

    entry_match = re.search(
        r'\b(BUY|SELL)\s*(?:NOW|LIMIT|ZONE|NEAR)?\s*[@:\-|]?\s*'
        r'([\d]+(?:\.\d+)?)(?:\s*[-/]\s*([\d]+(?:\.\d+)?))?',
        upper
    )

    at_match = re.search(
        r'@\s*([\d]+(?:\.\d+)?)',
        upper
    )

    if entry_match:
        result["entry"] = entry_match.group(2)
    elif at_match:
        result["entry"] = at_match.group(1)

    # ================== TP ==================

    tp_matches = re.findall(
        r'TP[¹²³123]?\s*[:\-]?\s*(\d+(?:\.\d+)?)',
        text,
        re.IGNORECASE
    )

    unique_tps = []
    for tp in tp_matches:
        if tp not in unique_tps:
            unique_tps.append(tp)

    result["tp"] = [
        float(tp)
        for tp in unique_tps
    ]

    # ================== SL ==================

    sl_match = re.search(
        r'\b(?:SL|STOPLOSS|STOP\s*LOSS)\b[^0-9]{0,40}?([\d]+(?:\.\d+)?)',
        upper
    )

    if sl_match:
        result["sl"] = float(
            sl_match.group(1)
        )

    return result

# ================== FORMAT SIGNAL ==================

def format_signal(
    data: dict,
    source: str = None
) -> str:

    symbol = (
        data.get("symbol")
        or "UNKNOWN"
    ).upper()

    direction = (
        data.get("type")
        or ""
    ).upper()

    entry = data.get("entry")

    sl = data.get("sl")

    tp_list = data.get("tp") or []

    # Auto SL
    if not sl and entry:

        try:
            sl = calculate_default_sl(
                symbol,
                float(entry),
                direction
            )

        except:
            sl = None

    formatted_tp = ""

    if tp_list:
        unique_tps = []
        for tp in tp_list:
            tp_str = clean_number(tp)
            if tp_str not in unique_tps:
                unique_tps.append(tp_str)

        for i, tp in enumerate(unique_tps, start=1):
            formatted_tp += f"\nTP{i}: {tp}"
    else:
        formatted_tp = "\nTP: N/A"

    sl_str = (
        clean_number(sl)
        if sl else "N/A"
    )

    final_message = (
        f"{direction} {symbol} {entry or 'N/A'}"
        f"{formatted_tp}"
        f"\nSL: {sl_str}"
    )

    if source:
        final_message += f"\nSource: {source}"

    return final_message

# ================== VALIDATION ==================

def is_valid_signal(data: dict) -> bool:

    return bool(
        data["type"]
        and data["entry"]
        and data["tp"]
    )

# ================== SIGNAL DETECTION (DIRECTION ONLY) ==================
def is_signal(text):
    if not text:
        return bool(text and text.strip())
        return False
    return True
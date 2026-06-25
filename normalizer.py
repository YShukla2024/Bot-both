# ================== NORMALIZER.PY ==================

import re
import unicodedata

# ================== NOISE BLACKLIST (PRECOMPILED) ==================
# Compiled once at import time instead of re-compiling on every is_signal()
# call. Same patterns, same order, same behavior -- just faster on a
# high-throughput forwarder.

_BLOCKED_PATTERNS = [
    r'BALANCE\s*:',
    r'EQUITY\s*:',
    r'FLOATING\s*:',
    r'STATUS\s*UPDATE',
    r'TARGET\s*HIT',
    r'TP\s*HIT',
    r'SL\s*HIT',
    r'PROFIT\s*BOOKED',
    r'BREAK\s*EVEN',
    r'BREAKEVEN',
    r'LOCK\s*PROFIT',
    r'HALF\s*PROFIT',
    r'BOT\s*ONLINE',
    r'PROXIMITY\s*ALERT',
    r'SKIPPING\s*ORDER',
    # -------- Blog / journal / promo / recap noise (Section 1 & 3) --------
    r'WEEKLY\s*RECAP',
    r'MONTHLY\s*RECAP',
    r'DAILY\s*RECAP',
    r'TRADING\s*JOURNAL',
    r'TRADING\s*REPORT',
    r'PERFORMANCE\s*REPORT',
    r'EXECUTION\s*REPORT',
    r'TICKET\s*REPORT',
    r'PROFIT\s*REPORT',
    r'WIN\s*RATE',
    r'WIN[/\s]*LOSS',
    r'CHALLENGE\s*UPDATE',
    r'RISK\s*MANAGEMENT',
    r'MARKET\s*(?:COMMENTARY|ANALYSIS|UPDATE|NEWS)',
    r'\bLESSON\b',
    r'\bTESTIMONIAL',
    r'JOIN\s*(?:OUR|THE)?\s*(?:VIP|TELEGRAM|GROUP|CHANNEL)',
    r'\bVIP\s*(?:GROUP|SIGNALS?|MEMBERSHIP|ADVERT)',
    r'CONTACT\s*(?:ADMIN|US)\b',
    r'LIMITED\s*SLOTS?',
    r'\bBROKER\s*(?:PROMO|BONUS|PARTNER)',
    r'TRADING\s*SETUPS?\b.{0,40}\bLESSON\b',
]
_BLOCKED_RE = [re.compile(p) for p in _BLOCKED_PATTERNS]

# ================== NORMALIZE ==================

def normalize_text(text: str) -> str:

    import re as _re
    import unicodedata as _ucd

    # ==========================================
    # ARABIC / PERSIAN TRANSLATION LAYER
    # These scripts have no letter case, so plain substring
    # replacement is safe and exact.
    # ==========================================
    arabic_map = {
        "بيع": "SELL",
        "شراء": "BUY",
        "اشتر": "BUY",
        "الذهب": "GOLD",
        "وقف الخسارة": "SL",
        "الهدف الأول": "TP1",
        "الهدف الثاني": "TP2",
        "الهدف الثالث": "TP3",
        "الهدف الرابع": "TP4",
        "الهدف الخامس": "TP5",
        "الهدف": "TP",
        "بسعر": "",  # Remove "at price" so numbers connect directly to the asset
        "هدف الربح 1": "TP1",
        "هدف الربح 2": "TP2",
        "هدف الربح 3": "TP3",
        "هدف الربح 4": "TP4",
        "هدف الربح 5": "TP5",
        "هدف الربح": "TP",
        "فروش": "SELL",
        "خرید": "BUY",
        "طلا": "GOLD",
        "نقره": "SILVER",
        "حد سود": "TP",
        "حد ضرر": "SL",
        "ورود": "ENTRY",
        "منطقه ورود": "ENTRY ZONE",
    }
    # Longer phrases first so a shorter key can't fire in the middle of a
    # longer one and corrupt it (e.g. avoid matching inside a longer phrase).
    for ar, en in sorted(arabic_map.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(ar, en)

    # ==========================================
    # CYRILLIC (RUSSIAN) TRANSLATION LAYER
    # Real-world Telegram signals use Title Case / Sentence case
    # ("Цена:", "Тип:"), never all-caps Cyrillic -- so this MUST be
    # case-insensitive, unlike the caseless Arabic/Persian scripts above.
    # Longer phrases are listed first and matched first so e.g.
    # "Новая сделка" is replaced before the shorter "Сделка" can corrupt it.
    # ==========================================
    cyrillic_map = [
        # Multi-word phrases (must come before their single-word substrings)
        ("НОВАЯ СДЕЛКА", "NEW TRADE"),
        ("ТОЧКА ВХОДА", "ENTRY"),
        ("ЗОНА ВХОДА", "ENTRY ZONE"),
        ("ВРЕМЯ ОТКРЫТИЯ", "OPEN TIME"),
        ("СТОП ЛОСС", "SL"),
        ("СТОП-ЛОСС", "SL"),
        ("BUY MARKET", "BUY"),
        ("SELL MARKET", "SELL"),
        # Targets (numbered before bare)
        ("ЦЕЛЬ 1", "TP1"),
        ("ЦЕЛЬ 2", "TP2"),
        ("ЦЕЛЬ 3", "TP3"),
        ("ЦЕЛЬ 4", "TP4"),
        ("ЦЕЛЬ 5", "TP5"),
        ("ЦЕЛЬ", "TP"),
        # Direction
        ("ПОКУПКА", "BUY"),
        ("ПРОДАЖА", "SELL"),
        # Trade (after NEW TRADE has already been consumed above)
        ("СДЕЛКА", "TRADE"),
        # Symbols
        ("ЗОЛОТО", "GOLD"),
        ("СЕРЕБРО", "SILVER"),
        # Trading fields -- blanked out (no English equivalent needed) or
        # mapped to a keyword the parser already understands
        ("ПАРА", ""),
        ("ТИП", ""),
        ("ЛОТ", ""),
        ("ЦЕНА", "ENTRY"),
        ("ВХОД", "ENTRY"),
        # Stop Loss
        ("СТОП", "SL"),
        # Misc
        ("ОТКРЫТИЕ", "OPEN"),
        ("РЫНОЧНЫЙ", "MARKET"),
        ("РЫНОК", "MARKET"),
    ]
    for ru, en in cyrillic_map:
        text = _re.sub(
            r'(?i)' + _re.escape(ru),
            en,
            text
        )

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

    # SL. (Keeps SL but removes the dot)
    text = _re.sub(
        r'\b(SL)\.\s*',
        r'\1 ',
        text,
        flags=_re.IGNORECASE
    )
    
    PERSIAN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹",
    "0123456789"
    )

    ARABIC_DIGITS = str.maketrans(
    "٠١٢٣٤٥٦٧٨٩",
    "0123456789"
    )

    text = text.translate(PERSIAN_DIGITS)
    text = text.translate(ARABIC_DIGITS)
    # ==========================================
    # PIP / POINT VALUES ARE NOT PRICES
    # Strip "50 Pips", "100Pip", "25 Points" etc. so downstream
    # number-extraction regexes never mistake them for price levels.
    # ==========================================
    text = _re.sub(
        r'\b\d+(?:\.\d+)?\s*(?:PIPS?|POINTS?|PTS?)\b',
        ' ',
        text,
        flags=_re.IGNORECASE
    )

    # STOPLOSS / STOP LOSS variants -> SL (so SL regex stays single-pattern)
    text = _re.sub(
        r'\bSTOP\s*-?\s*LOSS\b',
        'SL',
        text,
        flags=_re.IGNORECASE
    )
    text = _re.sub(
        r'\bSTOPLOSS\b',
        'SL',
        text,
        flags=_re.IGNORECASE
    )
    text = _re.sub(
        r'\bSL\s*BREAK\b',
        'SL',
        text,
        flags=_re.IGNORECASE
    )

    # TAKE PROFIT [n]: -> TPn  (Take Profit 1: 4013 -> TP1 4013)
    text = _re.sub(
        r'\bTAKE\s*PROFIT\s*(\d*)\s*[:\-]?\s*',
        lambda m: f"TP{m.group(1)} ",
        text,
        flags=_re.IGNORECASE
    )

    # TP OPEN (no number) -> sentinel TPOPEN so it's not confused with a
    # numbered TP that's missing its value; handled explicitly downstream.
    text = _re.sub(
        r'\bTP\s*[:\-]?\s*OPEN\b',
        'TPOPEN',
        text,
        flags=_re.IGNORECASE
    )

    # ZONE = / ZONE: (no preceding BUY/SELL/ENTRY word) -> ZONE keyword kept,
    # just normalizes the "=" separator to ":" for the zone regex below.
    text = _re.sub(
        r'\bZONE\s*=\s*',
        'ZONE: ',
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
    
    # Convert naked numbered targets (e.g., "  1: 4327") to standard "TP1 4327"
    text = _re.sub(
        r'(?m)^[ \t]*([1-9])[ \t]*[:\-\.)][ \t]*(\d+(?:\.\d+)?)[ \t]*$',
        r'TP\1 \2',
        text
    )

    # Remove emojis
    text = "".join(
        "-" if _ucd.category(ch) in ("Pd",)
        else (ch if ord(ch) < 128 else " ")
        for ch in text
    )

    # Add spaces (e.g., "4347SL" -> "4347 SL")
    text = _re.sub(
        r'(\d)(SL|TP|BUY|SELL)',
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

def clean_number(val) -> str:

    if isinstance(val, str):
        return val

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
        "entry_range": None,
        "tp": [],
        "tp_open": False,
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

    if re.search(r'\b(BUY|LONG|SHORT)\b', upper, re.IGNORECASE):
        result["type"] = "BUY"
    elif re.search(r'\bSELL\b', upper):
        result["type"] = "SELL"

    # ================== ENTRY ==================
    
    # 1. Strict Entry Zone Range (e.g., ENTRY ZONE: 4188-4180)
    range_match = re.search(
        r'\b(?:ENTRY\s*ZONE|BUY\s*ZONE|SELL\s*ZONE|ZONE|ENTRY)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*[-/]\s*(\d+(?:\.\d+)?)',
        upper
    )

    # 2. Strict Entry Zone Single (e.g., ENTRY ZONE: 4195)
    entry_zone_match = re.search(
        r'\b(?:ENTRY\s*ZONE|BUY\s*ZONE|SELL\s*ZONE|ZONE|ENTRY)\s*[:\-]?\s*(\d+(?:\.\d+)?)',
        upper
    )

    # 3. Standard entry pattern fallback
    entry_match = re.search(
        r'\b(BUY|SELL)\s*(?:NOW|LIMIT|ZONE|NEAR|ABOVE|BELOW|AT)?\s*'
        r'(?:XAUUSD|XAU|GOLD|XAGUSD|XAG|SILVER|EURUSD|GBPUSD|USDJPY|BTCUSD|BTC|ETHUSD|ETH|NAS100|NASDAQ)?\s*'
        r'[@:\-|]?\s*'
        r'([\d]+(?:\.\d+)?)(?:\s*[-/]\s*([\d]+(?:\.\d+)?))?',
        upper
    )

    at_match = re.search(
        r'@\s*([\d]+(?:\.\d+)?)',
        upper
    )

    # Priority routing to avoid gobbling Targets
    if range_match:
        first_num = float(range_match.group(1))
        second_num = float(range_match.group(2))
        
        if first_num == int(first_num) and second_num == int(second_num):
            result["entry_range"] = f"{int(first_num)}-{int(second_num)}"
        else:
            result["entry_range"] = f"{first_num}-{second_num}"
        
        if first_num == int(first_num):
            result["entry"] = str(int(first_num))
        else:
            result["entry"] = str(first_num)
            
    elif entry_zone_match:
        result["entry"] = entry_zone_match.group(1)
        
    elif entry_match:
        if entry_match.group(3): # Catch range attached directly to BUY/SELL
            result["entry_range"] = f"{entry_match.group(2)}-{entry_match.group(3)}"
        result["entry"] = entry_match.group(2)
        
    elif at_match:
        result["entry"] = at_match.group(1)
        
    # ================== TP ==================

    result["tp"] = []

    # TP OPEN (no fixed target yet) -- normalize_text turns "TP Open" / "Tp Open"
    # into the sentinel TPOPEN so it never gets parsed as a numbered TP.
    # We push the literal string "OPEN" into result["tp"] (instead of a float)
    # so that main.py's existing `if not data["tp"]:` raw-fallback check still
    # sees this as a COMPLETE signal -- no main.py changes required.
    if re.search(r'\bTPOPEN\b', text, re.IGNORECASE):
        result["tp_open"] = True

    for match in re.finditer(
        r'\bTP\d*\s*[:\-]?\s*(\d+(?:\.\d+)?)',
        text,
        re.IGNORECASE
    ):
        result["tp"].append(float(match.group(1)))

    targets_match = re.search(
        r'TARGETS?\s*:\s*([^\n\r]+)',
        text,
        re.IGNORECASE
    )

    if targets_match:
        nums = re.findall(
            r'\d+(?:\.\d+)?',
            targets_match.group(1)
        )
        for num in nums:
            result["tp"].append(float(num))

    open_match = re.search(
        r'OPEN\s*\((.*?)\)',
        text,
        re.IGNORECASE
    )

    if open_match:
        nums = re.findall(
            r'\d+(?:\.\d+)?',
            open_match.group(1)
        )
        for num in nums:
            result["tp"].append(float(num))

    # Remove duplicates while keeping order
    seen = set()
    clean_tp = []

    for tp in result["tp"]:
        if tp not in seen:
            seen.add(tp)
            clean_tp.append(tp)

    result["tp"] = clean_tp

    # If "TP Open" was detected and no concrete numeric TP was found,
    # push the literal "OPEN" sentinel so result["tp"] is non-empty.
    # format_signal() renders this as "TP: OPEN"; main.py's truthiness
    # check on data["tp"] sees a complete signal instead of raw-falling-back.
    if result["tp_open"] and not result["tp"]:
        result["tp"] = ["OPEN"]

    # ================== SL ==================

    sl_match = re.search(
        r'\b(?:SL|STOPLOSS|STOP\s*LOSS|BREAK)\b[^0-9]{0,40}?([\d]+(?:\.\d+)?)',
        upper
    )

    if sl_match:
        result["sl"] = float(sl_match.group(1))

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
    entry_range = data.get("entry_range")
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

    # Format TPs
    formatted_tp = ""

    if tp_list == ["OPEN"]:
        formatted_tp = "\nTP: OPEN"
    elif tp_list:
        unique_tps = []
        for tp in tp_list:
            tp_str = clean_number(tp)
            if tp_str not in unique_tps:
                unique_tps.append(tp_str)

        for i, tp in enumerate(unique_tps, start=1):
            formatted_tp += f"\nTP{i}: {tp}"
    elif data.get("tp_open"):
        formatted_tp = "\nTP: OPEN"
    else:
        formatted_tp = "\nTP: N/A"

    sl_str = (
        clean_number(sl)
        if sl else "N/A"
    )

    display_price = entry_range if entry_range else (entry or 'N/A')

    final_message = (
        f"{direction} {symbol} {display_price}"
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

# ================== SIGNAL CONFIDENCE ==================
# Internal confidence score (0-100) instead of a simple True/False check.
# Weighting per spec: Direction=30, Asset=20, Entry=30, TP=10, SL=10.
# This is used ONLY inside is_signal() as a stronger gate than keyword
# matching alone -- it does NOT change parse_signal()'s public output
# or main.py's existing data["type"]/data["entry"]/data["tp"] checks.

CONFIDENCE_THRESHOLD = 70

def signal_confidence(text: str) -> int:

    upper = normalize_text(text).upper()
    score = 0

    # Direction (30) -- BUY/SELL/LONG/SHORT as a standalone trade direction word
    if re.search(r'\b(BUY|SELL|LONG|SHORT)\b', upper):
        score += 30

    # Asset (20) -- a recognized symbol/asset keyword
    if re.search(
        r'\b(XAUUSD|XAU|GOLD|XAGUSD|XAG|SILVER|EURUSD|GBPUSD|USDJPY|'
        r'BTCUSD|BTC|BITCOIN|ETHUSD|ETH|ETHEREUM|NAS100|NASDAQ)\b',
        upper
    ):
        score += 20

    # Entry (30) -- an actual price level tied to a zone/entry/@ keyword,
    # OR a bare price sitting directly next to BUY/SELL (e.g. "BUY XAUUSD 4500")
    has_entry = bool(
        re.search(
            r'\b(?:ENTRY\s*ZONE|BUY\s*ZONE|SELL\s*ZONE|ZONE|ENTRY)\s*[:\-=]?\s*\d+(?:\.\d+)?',
            upper
        )
        or re.search(r'@\s*\d+(?:\.\d+)?', upper)
        or re.search(
            r'\b(?:BUY|SELL)\b(?:\s+\w+){0,2}\s*[@:\-|]?\s*\d{2,}(?:\.\d+)?',
            upper
        )
    )
    if has_entry:
        score += 30

    # TP (10) -- any take-profit / target keyword with a number, or TP-Open
    has_tp = bool(
        re.search(r'\bTP\d*\s*[:\-]?\s*\d+(?:\.\d+)?', upper)
        or re.search(r'\bTARGETS?\s*:?\s*\d', upper)
        or re.search(r'\bTPOPEN\b', upper)
    )
    if has_tp:
        score += 10

    # SL (10) -- stoploss keyword with a number
    if re.search(r'\b(?:SL|STOPLOSS|STOP\s*LOSS)\b[^0-9]{0,40}?\d+(?:\.\d+)?', upper):
        score += 10

    return score

# ================== SIGNAL DETECTION ==================

def is_signal(text):

    if not text:
        return False

    t = normalize_text(text).upper().strip()

    for compiled_pattern in _BLOCKED_RE:
        if compiled_pattern.search(t):
            return False

    signal_words = [
        "BUY",
        "SELL",
        "BUY NOW",
        "SELL NOW",
        "GOLD",
        "SILVER",
        "XAUUSD",
        "XAGUSD",
        "الذهب", 
        "بيع", 
        "شراء",
        "LONG",
        "SHORT",
    ]

    has_keyword = any(word in t for word in signal_words)
    if not has_keyword:
        return False

    # Confidence gate: a bare keyword hit is no longer enough on its own.
    # Messages need real signal substance (direction + asset + an actual
    # entry price, at minimum) to clear the threshold. This is what catches
    # narrative/educational posts that mention BUY/SELL but carry no
    # executable price structure, without re-introducing the blacklist's
    # false-negative risk on legitimate short signals.
    return signal_confidence(text) >= CONFIDENCE_THRESHOLD
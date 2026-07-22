"""
Indicators library — apna custom logic likhne ke liye ready-made helpers.

Saare functions pure Python hain, lists lete hain aur lists return karte hain.
Last element = latest candle. Example:

    from indicators import ema, crossover
    f = ema(closes, 9)
    s = ema(closes, 21)
    if crossover(f, s):   # fast line neeche se upar cross ki
        return "BUY"
"""

from typing import List, Tuple


def ema(v: List[float], p: int) -> List[float]:
    k = 2 / (p + 1)
    out = [v[0]]
    for x in v[1:]:
        out.append(x * k + out[-1] * (1 - k))
    return out


def sma(v: List[float], p: int) -> List[float]:
    out = []
    for i in range(len(v)):
        out.append(sum(v[max(0, i - p + 1):i + 1]) / len(v[max(0, i - p + 1):i + 1]))
    return out


def rsi(closes: List[float], p: int = 14) -> List[float]:
    if len(closes) < p + 1:
        return [50.0] * len(closes)
    out = [50.0]
    ag = al = 0.0
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        g, l = max(ch, 0), max(-ch, 0)
        if i <= p:
            ag, al = ag + g / p, al + l / p
        else:
            ag, al = (ag * (p - 1) + g) / p, (al * (p - 1) + l) / p
        out.append(100.0 if al == 0 else 100 - 100 / (1 + ag / al))
    return out


def macd(closes: List[float], fast: int = 12, slow: int = 26,
         sig: int = 9) -> Tuple[List[float], List[float]]:
    ef, es = ema(closes, fast), ema(closes, slow)
    line = [a - b for a, b in zip(ef, es)]
    return line, ema(line, sig)


def atr(highs: List[float], lows: List[float],
        closes: List[float], p: int = 14) -> List[float]:
    out = [highs[0] - lows[0]]
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        out.append(tr if i < p else (out[-1] * (p - 1) + tr) / p)
    return out


def supertrend(highs: List[float], lows: List[float], closes: List[float],
               p: int = 10, m: float = 3.0) -> Tuple[List[float], List[int]]:
    """Returns (supertrend_line, direction). direction: 1=bullish, -1=bearish.
       Flip -1 -> 1 = BUY,  1 -> -1 = SELL."""
    a = atr(highs, lows, closes, p)
    n = len(closes)
    st, d = [0.0] * n, [1] * n
    fu = [(h + l) / 2 + m * x for h, l, x in zip(highs, lows, a)]
    fl = [(h + l) / 2 - m * x for h, l, x in zip(highs, lows, a)]
    st[0] = fu[0]
    for i in range(1, n):
        fu[i] = fu[i] if (fu[i] < fu[i - 1] or closes[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = fl[i] if (fl[i] > fl[i - 1] or closes[i - 1] < fl[i - 1]) else fl[i - 1]
        if st[i - 1] == fu[i - 1]:
            st[i], d[i] = (fu[i], -1) if closes[i] <= fu[i] else (fl[i], 1)
        else:
            st[i], d[i] = (fl[i], 1) if closes[i] >= fl[i] else (fu[i], -1)
    return st, d


def crossover(a: List[float], b: List[float]) -> bool:
    """a neeche se b ke upar cross kiya (latest candle pe)."""
    return len(a) >= 2 and a[-2] <= b[-2] and a[-1] > b[-1]


def crossunder(a: List[float], b: List[float]) -> bool:
    """a upar se b ke neeche cross kiya (latest candle pe)."""
    return len(a) >= 2 and a[-2] >= b[-2] and a[-1] < b[-1]


def highest(v: List[float], p: int) -> float:
    return max(v[-p:])


def lowest(v: List[float], p: int) -> float:
    return min(v[-p:])

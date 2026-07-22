"""
EXAMPLE logic (public file — sirf demo ke liye).

╔══════════════════════════════════════════════════════════════╗
║  APNA SECRET LOGIC KAISE LIKHEin (PRIVACY SAFE):             ║
║                                                              ║
║  1. Is file ko COPY karke NAAM rakho:  my_logic.py           ║
║  2. Usme apna logic likho — wo file .gitignore me hai        ║
║     = kabhi GitHub/chat pe NAHI jaayegi, sirf aapke PC pe    ║
║  3. Bot automatically my_logic.py use karega                 ║
║                                                              ║
║  Rules: get_signal() return kare "BUY" / "SELL" / None       ║
║  closes/... lists me LAST element = latest candle            ║
╚══════════════════════════════════════════════════════════════╝

Available helpers (indicators.py):
  ema, sma, rsi, macd, atr, supertrend, crossover, crossunder,
  highest, lowest
"""

from indicators import ema, crossover, crossunder

FAST, SLOW = 9, 21  # apni settings yahan badlo


def get_signal(closes, highs, lows, opens, volumes):
    """'BUY' / 'SELL' / None return karo."""
    f = ema(closes, FAST)
    s = ema(closes, SLOW)
    if crossover(f, s):
        return "BUY"
    if crossunder(f, s):
        return "SELL"
    return None


# ---- More examples (comment hata kar use karo) ----
#
# from indicators import rsi, supertrend
#
# def get_signal(closes, highs, lows, opens, volumes):
#     # RSI oversold bounce
#     r = rsi(closes, 14)
#     if r[-2] < 30 <= r[-1]:
#         return "BUY"
#     if r[-2] > 70 >= r[-1]:
#         return "SELL"
#     return None
#
# def get_signal(closes, highs, lows, opens, volumes):
#     # Supertrend flip
#     st, d = supertrend(highs, lows, closes, 10, 3)
#     if d[-2] == -1 and d[-1] == 1:
#         return "BUY"
#     if d[-2] == 1 and d[-1] == -1:
#         return "SELL"
#     return None

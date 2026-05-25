"""
MARKET PULSE v4.0 - Professional Elliott Wave Detection
Proper Fibonacci levels, Wave priority, Rally detection
"""
import os
import time
import requests
import warnings
import numpy as np
from datetime import datetime

warnings.filterwarnings('ignore')
os.environ['TZ'] = 'Asia/Kolkata'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_PULSE_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_PULSE_CHAT_ID')

STOCKS = {
    'IT': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM'],
    'Banking': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'SBIN', 'AXISBANK'],
    'Pharma': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB'],
    'Consumer': ['ITC', 'HINDUNILVR', 'TITAN', 'DMART', 'TRENT'],
    'Auto': ['MARUTI', 'M&M'],
    'Finance': ['BAJFINANCE', 'BAJAJFINSV', 'CHOLAFIN'],
    'Energy': ['RELIANCE', 'POWERGRID', 'NTPC', 'ONGC', 'TATAPOWER'],
    'Others': ['LT', 'HAL', 'BEL', 'IRCTC', 'ASIANPAINT']
}

def robust_nse_fetch(symbol):
    for _ in range(2):
        try:
            from nsetools import Nse
            nse = Nse()
            q = nse.get_quote(symbol)
            if q and q.get('lastPrice') and float(q.get('lastPrice', 0)) > 0:
                intraday = q.get('intraDayHighLow', {})
                weekly = q.get('weekHighLow', {})
                return {
                    'symbol': symbol,
                    'lastPrice': float(q.get('lastPrice', 0)),
                    'open': float(q.get('open', 0)),
                    'dayHigh': float(intraday.get('max', 0)),
                    'dayLow': float(intraday.get('min', 0)),
                    'previousClose': float(q.get('previousClose', 0)),
                    'pChange': float(q.get('pChange', 0)),
                    'vwap': float(q.get('vwap', 0)) if q.get('vwap') else 0,
                    'weekHighLow': {'max': float(weekly.get('max', 0)), 'min': float(weekly.get('min', 0))}
                }
        except: pass
        time.sleep(1)
    
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info
        hist = ticker.history(period="5d")
        if not hist.empty:
            price = float(hist['Close'].iloc[-1])
            prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else price
            return {
                'symbol': symbol,
                'lastPrice': price,
                'open': float(hist['Open'].iloc[-1]),
                'dayHigh': float(hist['High'].iloc[-1]),
                'dayLow': float(hist['Low'].iloc[-1]),
                'previousClose': prev,
                'pChange': float(((price-prev)/prev)*100),
                'vwap': price,
                'weekHighLow': {'max': float(info.get('fiftyTwoWeekHigh', price*1.1)), 'min': float(info.get('fiftyTwoWeekLow', price*0.9))}
            }
    except: pass
    return None

# ============================================
# PROPER ELLIOTT WAVE DETECTION
# ============================================
def detect_elliott_wave(price, high_52, low_52, change_pct, day_high, day_low, open_price, prev_close):
    """
    Proper Elliott Wave Logic:
    - Wave 1: Price near 52W low starting to move up (RALLY START)
    - Wave 2: Pullback to 50-61.8% Fib (BEST BUY)
    - Wave 3: Above 61.8% Fib, strong momentum (POWER MOVE)
    - Wave 4: Consolidation after Wave 3 (PAUSE)
    - Wave 5: Near 52W high, final push (FINAL LEG)
    """
    
    if high_52 == 0 or low_52 == 0:
        return None
    
    fib_range = high_52 - low_52
    if fib_range <= 0:
        return None
    
    # Fibonacci levels
    fib_236 = low_52 + fib_range * 0.236
    fib_382 = low_52 + fib_range * 0.382
    fib_500 = low_52 + fib_range * 0.500
    fib_618 = low_52 + fib_range * 0.618
    fib_786 = low_52 + fib_range * 0.786
    
    # Position in 52W range (0% = at low, 100% = at high)
    position_52w = ((price - low_52) / fib_range) * 100
    
    # Day range position
    day_range = day_high - day_low
    position_day = ((price - day_low) / day_range * 100) if day_range > 0 else 50
    
    # Distance from 52W high
    dist_from_high = ((high_52 - price) / high_52) * 100
    
    # Distance from 52W low
    dist_from_low = ((price - low_52) / low_52) * 100
    
    # ===== WAVE DETERMINATION =====
    
    # WAVE 1: Near 52W low, just starting to rally (0-23.6% range)
    if position_52w < 23.6 and change_pct > 0 and price > open_price:
        confidence = 50 + (position_52w * 1.5) + (change_pct * 5)
        return {
            'stage': 'WAVE-1 🟢 (Rally Start)',
            'confidence': min(90, confidence),
            'position': f"{position_52w:.0f}% from 52W low",
            'signal': 'EARLY RALLY - Best time to enter!',
            'entry_zone': f"Rs.{price:.0f} - Rs.{fib_236:.0f}",
            'target': f"Rs.{fib_382:.0f} (+{round(((fib_382-price)/price)*100,1)}%)",
            'stop': f"Rs.{low_52:.0f} (52W low)",
            'fib_levels': {'236': fib_236, '382': fib_382, '500': fib_500, '618': fib_618},
            'priority': 1  # HIGHEST PRIORITY
        }
    
    # WAVE 2: Pulling back to Fib levels (23.6-50% range, correcting)
    if 23.6 <= position_52w < 50 and change_pct < 0.5:
        # Check if near key Fib levels
        near_fib = ""
        if abs(price - fib_382) / price < 0.02:
            near_fib = " at Fib 38.2%"
            confidence = 75
        elif abs(price - fib_500) / price < 0.02:
            near_fib = " at Fib 50%"
            confidence = 80
        elif abs(price - fib_618) / price < 0.02:
            near_fib = " at Fib 61.8% (GOLDEN ZONE)"
            confidence = 90
        else:
            confidence = 55
        
        return {
            'stage': f'WAVE-2 🟡 (Pullback{near_fib})',
            'confidence': min(90, confidence),
            'position': f"{position_52w:.0f}% from 52W low",
            'signal': 'BUY THE DIP - Best risk/reward!',
            'entry_zone': f"Rs.{fib_618:.0f} - Rs.{fib_500:.0f}",
            'target': f"Rs.{fib_236:.0f} (Previous high)",
            'stop': f"Rs.{fib_786:.0f} (Below 78.6% Fib)",
            'fib_levels': {'236': fib_236, '382': fib_382, '500': fib_500, '618': fib_618},
            'priority': 2
        }
    
    # WAVE 3: Strong momentum, above 50% range, moving up
    if position_52w >= 50 and change_pct > 0.5 and position_day > 50:
        confidence = 60 + (change_pct * 8) + (position_day * 0.2)
        return {
            'stage': 'WAVE-3 🔵 (Power Move)',
            'confidence': min(90, confidence),
            'position': f"{position_52w:.0f}% from 52W low",
            'signal': 'STRONG TREND - Ride the momentum!',
            'entry_zone': f"Rs.{price:.0f} (Current)",
            'target': f"Rs.{fib_236:.0f} (+{round(((fib_236-price)/price)*100,1)}%)",
            'stop': f"Rs.{fib_500:.0f} (Below 50% Fib)",
            'fib_levels': {'236': fib_236, '382': fib_382, '500': fib_500, '618': fib_618},
            'priority': 3
        }
    
    # WAVE 4: Consolidation (50-78.6% range, low volatility)
    if 50 <= position_52w < 78.6 and abs(change_pct) < 1:
        confidence = 45
        return {
            'stage': 'WAVE-4 ⚪ (Consolidation)',
            'confidence': confidence,
            'position': f"{position_52w:.0f}% from 52W low",
            'signal': 'WAIT for breakout or buy near Fib support',
            'entry_zone': f"Rs.{fib_500:.0f} - Rs.{fib_618:.0f}",
            'target': f"Rs.{high_52:.0f} (52W high)",
            'stop': f"Rs.{fib_618:.0f}",
            'fib_levels': {'236': fib_236, '382': fib_382, '500': fib_500, '618': fib_618},
            'priority': 4
        }
    
    # WAVE 5: Near 52W high, final push (78.6-100% range)
    if position_52w >= 78.6:
        confidence = 30 + (dist_from_high * 1.5)
        return {
            'stage': 'WAVE-5 🔴 (Final Leg)',
            'confidence': min(70, confidence),
            'position': f"{position_52w:.0f}% from 52W low",
            'signal': 'QUICK TRADE only - Near top! Book fast.',
            'entry_zone': f"Rs.{price:.0f} (Risky entry)",
            'target': f"Rs.{high_52:.0f} (+{round(((high_52-price)/price)*100,1)}%)",
            'stop': f"Rs.{fib_500:.0f} (Tight stop!)",
            'fib_levels': {'236': fib_236, '382': fib_382, '500': fib_500, '618': fib_618},
            'priority': 5  # LOWEST PRIORITY
        }
    
    return None

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900: text = text[:3900]
        resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        return resp.json().get('ok', False)
    except: return False

def run():
    results = []
    now = datetime.now()
    print(f"🌊 MARKET PULSE v4.0 - {now.strftime('%d-%b %I:%M %p')}")
    
    all_stocks = [(sym, sec) for sec, syms in STOCKS.items() for sym in syms]
    
    for symbol, sector in all_stocks:
        try:
            data = robust_nse_fetch(symbol)
            if not data: continue
            
            wave = detect_elliott_wave(
                data['lastPrice'], 
                data['weekHighLow']['max'],
                data['weekHighLow']['min'],
                data['pChange'],
                data['dayHigh'],
                data['dayLow'],
                data['open'],
                data['previousClose']
            )
            
            if wave:
                wave['symbol'] = symbol
                wave['sector'] = sector
                wave['price'] = data['lastPrice']
                wave['change'] = data['pChange']
                results.append(wave)
                print(f"  {symbol:15} {wave['stage']:30} Conf:{wave['confidence']:.0f}% | Priority:{wave['priority']}")
            
            time.sleep(0.1)
        except Exception as e:
            print(f"  {symbol}: Error - {str(e)[:30]}")
    
    if not results:
        send_telegram(f"<b>🌊 Market Pulse</b>\n{now.strftime('%d-%b %I:%M %p')}\n\nNo clear Elliott Wave patterns detected.\nMarket may be in transition.")
        return
    
    # SORT BY PRIORITY (Wave 1 first, Wave 5 last)
    results.sort(key=lambda x: x['priority'])
    
    # Separate by wave type
    wave1 = [r for r in results if 'WAVE-1' in r['stage']]
    wave2 = [r for r in results if 'WAVE-2' in r['stage']]
    wave3 = [r for r in results if 'WAVE-3' in r['stage']]
    
    msg = f"<b>🌊 MARKET PULSE v4.0</b>\n"
    msg += f"{now.strftime('%d-%b %I:%M %p')} IST\n"
    msg += f"{'═'*35}\n\n"
    
    msg += f"📊 <b>Wave Distribution:</b>\n"
    msg += f"🟢 Wave-1 (Rally Start): {len(wave1)} stocks\n"
    msg += f"🟡 Wave-2 (Best Buy): {len(wave2)} stocks\n"
    msg += f"🔵 Wave-3 (Power): {len(wave3)} stocks\n"
    msg += f"🔴 Wave-5 (Final): {len([r for r in results if 'WAVE-5' in r['stage']])} stocks\n\n"
    
    # SHOW WAVE 1 & 2 FIRST (Best opportunities)
    best_opportunities = wave1 + wave2 + wave3
    
    if best_opportunities:
        msg += f"<b>🎯 BEST OPPORTUNITIES (Wave 1-2-3)</b>\n{'═'*35}\n\n"
        
        for i, r in enumerate(best_opportunities[:6], 1):
            emoji = "🟢" if 'WAVE-1' in r['stage'] else "🟡" if 'WAVE-2' in r['stage'] else "🔵"
            
            msg += f"{emoji} <b>#{i} {r['symbol']}</b> | {r['sector']} | Rs.{r['price']:.0f}\n"
            msg += f"{'─'*35}\n"
            msg += f"Wave: <b>{r['stage']}</b>\n"
            msg += f"Confidence: <b>{r['confidence']:.0f}%</b>\n"
            msg += f"Position: {r['position']}\n"
            msg += f"Signal: <b>{r['signal']}</b>\n\n"
            
            msg += f"<b>Trade Plan:</b>\n"
            msg += f"  Entry: {r['entry_zone']}\n"
            msg += f"  Target: {r['target']}\n"
            msg += f"  Stop: {r['stop']}\n"
            msg += f"  Change: {r['change']:+.1f}%\n\n"
    
    msg += f"{'═'*35}\n"
    msg += f"<i>Priority: Wave-1 > Wave-2 > Wave-3 > Wave-4 > Wave-5</i>\n"
    msg += f"<i>Wave-1 & 2 = Best entry points</i>"
    
    send_telegram(msg)
    print(f"\n✅ Sent! Wave-1:{len(wave1)} Wave-2:{len(wave2)} Wave-3:{len(wave3)}")

if __name__ == "__main__":
    run()

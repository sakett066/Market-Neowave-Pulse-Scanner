"""
MARKET PULSE v3.0 - Robust Neo Wave + Breakout Scanner
Multi-fallback data fetching
"""
import os
import time
import requests
import warnings
import json
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
    'Auto': ['MARUTI', 'M&M', 'BAJAJ-AUTO', 'EICHERMOT'],
    'Finance': ['BAJFINANCE', 'BAJAJFINSV', 'CHOLAFIN'],
    'Energy': ['RELIANCE', 'POWERGRID', 'NTPC', 'ONGC', 'TATAPOWER'],
    'Others': ['LT', 'HAL', 'BEL', 'IRCTC', 'ASIANPAINT']
}

def robust_nse_fetch(symbol):
    """Fetch NSE data with fallbacks"""
    # Try nsetools first
    for _ in range(2):
        try:
            from nsetools import Nse
            nse = Nse()
            q = nse.get_quote(symbol)
            if q and q.get('lastPrice') and float(q.get('lastPrice', 0)) > 0:
                return format_data(q, symbol)
        except: pass
        time.sleep(1)
    
    # Yahoo Finance fallback
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info
        hist = ticker.history(period="5d")
        if not hist.empty:
            return format_yahoo(info, hist, symbol)
    except: pass
    
    return None

def format_data(q, symbol):
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

def format_yahoo(info, hist, symbol):
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

def detect_neo_wave(price, high_52, low_52, change_pct):
    if high_52 == 0 or low_52 == 0: return {'stage': 'NO DATA', 'confidence': 0}
    
    fib_range = high_52 - low_52
    fib_236 = low_52 + fib_range * 0.236
    fib_382 = low_52 + fib_range * 0.382
    fib_500 = low_52 + fib_range * 0.500
    fib_618 = low_52 + fib_range * 0.618
    
    position = ((price - low_52) / fib_range * 100) if fib_range > 0 else 50
    
    # Wave detection
    w1 = w2 = w3 = w4 = w5 = 0
    
    if position > 60 and change_pct > 0: w1 += 20
    if position < 40 and change_pct < 0: w1 += 15
    
    if 30 <= position <= 50: w2 += 20
    if abs(price - fib_618) / price < 0.03: w2 += 25
    
    if position > 55 and change_pct > 0.5: w3 += 25
    if price > fib_500: w3 += 15
    
    if 40 <= position <= 60 and abs(change_pct) < 0.5: w4 += 20
    
    if position > 70: w5 += 20
    if ((high_52 - price) / high_52) < 0.08: w5 += 25
    
    waves = {'WAVE-1': w1, 'WAVE-2 (Best Buy)': w2, 'WAVE-3 (Power)': w3, 'WAVE-4 (Pause)': w4, 'WAVE-5 (Final)': w5}
    best = max(waves, key=waves.get)
    conf = min(90, waves[best] + 10)
    
    return {'stage': best if conf > 25 else 'NO PATTERN', 'confidence': conf, 'fib_382': round(fib_382,0), 'fib_618': round(fib_618,0)}

def get_wave_action(wave, price, fib_382, fib_618):
    if 'WAVE-2' in wave:
        return f"BUY at Fib 61.8% ({fib_618}) | Target Fib 38.2% ({fib_382}) | SL below Fib 78.6%"
    elif 'WAVE-3' in wave:
        return f"BUY now - Strongest wave | Target +25% | SL at Fib 50%"
    elif 'WAVE-1' in wave:
        return f"Start 50% position | Add on pullback | Target +15%"
    elif 'WAVE-5' in wave:
        return f"Quick trade only | Book fast | SL tight at -3%"
    return "No clear trade setup"

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
    print(f"MARKET PULSE - {now.strftime('%d-%b %I:%M %p')}")
    
    all_stocks = [(sym, sec) for sec, syms in STOCKS.items() for sym in syms]
    
    for symbol, sector in all_stocks:
        try:
            data = robust_nse_fetch(symbol)
            if not data: continue
            
            wave = detect_neo_wave(data['lastPrice'], data['weekHighLow']['max'], 
                                   data['weekHighLow']['min'], data['pChange'])
            
            if wave['confidence'] >= 30:
                action = get_wave_action(wave['stage'], data['lastPrice'], wave.get('fib_382',0), wave.get('fib_618',0))
                results.append({
                    'symbol': symbol, 'sector': sector, 'price': data['lastPrice'],
                    'change': data['pChange'], 'wave': wave, 'action': action
                })
                print(f"  {symbol:15} {wave['stage']} ({wave['confidence']}%)")
            time.sleep(0.1)
        except: pass
    
    if not results:
        send_telegram(f"<b>Market Pulse</b>\n{now.strftime('%d-%b %I:%M %p')}\n\nNo clear wave patterns detected.")
        return
    
    results.sort(key=lambda x: x['wave']['confidence'], reverse=True)
    
    msg = f"<b>🌊 MARKET PULSE</b>\n{now.strftime('%d-%b %I:%M %p')} IST\n{'═'*30}\n\n"
    msg += f"Neo Wave patterns found: {len(results)}\n\n"
    
    for i, r in enumerate(results[:5], 1):
        emoji = "🟢" if r['wave']['confidence'] >= 60 else "🔵" if r['wave']['confidence'] >= 40 else "🟡"
        msg += f"{emoji} <b>#{i} {r['symbol']}</b> | {r['sector']} | Rs.{r['price']:.0f}\n"
        msg += f"   Wave: {r['wave']['stage']} ({r['wave']['confidence']}%)\n"
        msg += f"   Action: {r['action']}\n"
        msg += f"   Change: {r['change']:+.1f}%\n\n"
    
    msg += f"{'═'*30}\n<i>Neo Wave Scanner | Multi-source data</i>"
    send_telegram(msg)
    print(f"✅ Sent! {len(results)} patterns found")

if __name__ == "__main__":
    run()

"""
MARKET PULSE v3.0 - Neo Wave Priority + Breakout Scanner
Neo Wave (Higher Accuracy) shown first, Breakouts second
Honest delivery data - shows when data is real vs estimated
"""
import os
import time
import requests
from nsetools import Nse
from datetime import datetime
import re
from xml.etree import ElementTree

os.environ['TZ'] = 'Asia/Kolkata'

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_PULSE_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_PULSE_CHAT_ID')

def discover_moving_stocks():
    return [
        'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'SBIN',
        'RELIANCE', 'ITC', 'LT', 'HINDUNILVR', 'SUNPHARMA', 'CIPLA',
        'TITAN', 'MARUTI', 'BAJFINANCE', 'POWERGRID', 'NTPC', 'WIPRO',
        'AXISBANK', 'TECHM', 'ASIANPAINT', 'ADANIPORTS', 'ONGC',
        'TATASTEEL', 'JSWSTEEL', 'DIVISLAB', 'DRREDDY', 'BAJAJFINSV',
        'TRENT', 'DMART', 'PIDILITIND', 'DABUR',
        'BANDHANBNK', 'FEDERALBNK', 'IDFCFIRSTB', 'AUBANK',
        'HAL', 'BEL', 'IRCON', 'JINDALSTEL',
        'LAURUSLABS', 'ALKEM', 'BIOCON', 'CHOLAFIN', 'MUTHOOTFIN',
        'PERSISTENT', 'EICHERMOT', 'TVSMOTOR', 'TATAMOTORS', 'M&M',
        'ZOMATO', 'IRCTC', 'TATACONSUM', 'ADANIGREEN', 'TATAPOWER',
        'NHPC', 'PFC', 'RECLTD', 'CANBK', 'UNIONBANK', 'PNB'
    ]

def detect_neo_wave(price, high, low, open_p, prev_close, high_52, low_52, change_pct):
    signals = []
    if high_52 == 0 or low_52 == 0:
        return {'stage': 'UNKNOWN', 'confidence': 0, 'signals': ['No data'], 'fib_levels': {}}
    
    fib_range = high_52 - low_52
    fib_236 = low_52 + fib_range * 0.236
    fib_382 = low_52 + fib_range * 0.382
    fib_500 = low_52 + fib_range * 0.500
    fib_618 = low_52 + fib_range * 0.618
    fib_786 = low_52 + fib_range * 0.786
    
    day_range = high - low
    body = abs(price - open_p)
    position = ((price - low) / day_range * 100) if day_range > 0 else 50
    
    w1 = w2 = w3 = w4 = w5 = 0
    
    if price > open_p > prev_close: w1 += 15; signals.append("Bullish impulse candle")
    if position > 60: w1 += 10
    if change_pct > 1: w1 += 10; signals.append(f"+{change_pct:.1f}% momentum")
    
    if 30 <= position <= 50: w2 += 15; signals.append("Healthy pullback")
    if abs(price - fib_618) / price < 0.03: w2 += 20; signals.append("At 61.8% Fib Golden Zone")
    elif abs(price - fib_500) / price < 0.03: w2 += 15; signals.append("At 50% Fib retracement")
    
    if price > fib_500: w3 += 15; signals.append("Above 50% Fib (Strong)")
    if position > 55 and change_pct > 0.5: w3 += 20; signals.append("Power move underway")
    if price > open_p and body > (day_range * 0.4): w3 += 15
    
    if body < (day_range * 0.3): w4 += 12; signals.append("Consolidation phase")
    if 40 <= position <= 60: w4 += 10
    if abs(change_pct) < 0.5: w4 += 8
    
    if price > fib_786: w5 += 15; signals.append("Above 78.6% Fib")
    if ((high_52 - price) / high_52) < 0.08: w5 += 20; signals.append("Near 52W high breakout")
    if position > 70 and change_pct > 0: w5 += 12
    
    wave_scores = {'WAVE-1 (Start)': w1, 'WAVE-2 (Pullback)': w2, 'WAVE-3 (Power)': w3, 'WAVE-4 (Pause)': w4, 'WAVE-5 (Final)': w5}
    best_wave = max(wave_scores, key=wave_scores.get)
    best_score = wave_scores[best_wave]
    confidence = min(95, best_score + 10)
    
    if confidence < 25:
        best_wave = "NO PATTERN"
        signals = ["No clear wave"]
    
    return {'stage': best_wave, 'confidence': confidence, 'signals': signals[:3], 'fib_levels': {'236': round(fib_236,0), '382': round(fib_382,0), '500': round(fib_500,0), '618': round(fib_618,0), '786': round(fib_786,0)}}

def detect_breakout(price, high, low, open_p, prev_close, high_52, change_pct, delivery_pct, volume_ratio):
    confirmations, weaknesses = [], []
    is_52w = price > high_52 * 0.98
    is_gap = open_p > prev_close * 1.01
    is_close_strong = ((price - low) / (high - low) * 100) > 65 if (high - low) > 0 else False
    is_mom = change_pct > 1.5
    is_green = price > open_p
    
    # Volume check - only if data available
    is_vol = volume_ratio > 1.3 if volume_ratio > 0 else None
    is_del = delivery_pct > 45 if delivery_pct > 0 else None
    
    # Any breakout trigger
    if is_52w or is_gap or (change_pct > 2 and is_close_strong) or (is_mom and is_close_strong):
        confirms = 0
        
        # Always count these
        if is_52w: confirms += 2; confirmations.append("Near 52W high")
        if is_gap: confirms += 1; confirmations.append("Gap up opening")
        if is_close_strong: confirms += 1; confirmations.append("Strong close")
        if is_mom: confirms += 1; confirmations.append(f"+{change_pct:.1f}% momentum")
        if is_green: confirms += 1; confirmations.append("Green candle")
        
        # Volume - only if available
        if is_vol is True: confirms += 1; confirmations.append("High volume")
        elif is_vol is False: weaknesses.append("Low volume")
        
        # Delivery - only if available
        if is_del is True: confirms += 1; confirmations.append("Strong delivery")
        elif is_del is False: weaknesses.append("Low delivery")
        
        # Strength determination (adjusted for missing data)
        max_possible = 6 if (is_vol is not None and is_del is not None) else 4
        
        if confirms >= max_possible - 1:
            strength, btype = "STRONG", "BREAKOUT"
        elif confirms >= max_possible - 2:
            strength, btype = "MODERATE", "LIKELY BREAKOUT"
        else:
            strength, btype = "WEAK", "WEAK BREAKOUT"
        
        return {
            'type': btype,
            'strength': strength,
            'confirmations': confirmations[:3],
            'weaknesses': weaknesses[:2],
            'is_breakout': True
        }
    
    return {'type': None, 'strength': 'NONE', 'confirmations': [], 'weaknesses': [], 'is_breakout': False}

def get_wave_action(wave_stage, price, fib):
    plan = {'entry_low':0,'entry_high':0,'stop_loss':0,'target1':0,'target2':0,'target1_pct':0,'target2_pct':0,'immediate':'','exit':'','risk_reward':0,'position':'10'}
    
    wave_range = fib['786'] - fib['236']
    if wave_range <= 0: wave_range = price * 0.1
    
    if 'WAVE-1' in wave_stage:
        plan['entry_low'] = round(price * 0.99, 0)
        plan['entry_high'] = round(price * 1.02, 0)
        plan['stop_loss'] = round(fib['786'], 0)
        plan['target1'] = round(fib['382'], 0)
        plan['target2'] = round(fib['618'], 0)
        plan['immediate'] = 'START position 50% - Wave 1 beginning'
        plan['exit'] = 'Trail SL to entry at Target 1, let balance run to T2'
        plan['position'] = '10-15'
        
    elif 'WAVE-2' in wave_stage:
        plan['entry_low'] = round(fib['618'], 0)
        plan['entry_high'] = round(fib['500'], 0)
        plan['stop_loss'] = round(fib['786'] * 0.98, 0)
        plan['target1'] = round(fib['236'], 0)
        plan['target2'] = round(fib['236'] + wave_range * 0.618, 0)
        plan['immediate'] = 'BUY at Golden Zone (61.8% Fib) - Best risk/reward'
        plan['exit'] = 'Book 50% at T1 (old high), trail SL on balance to T2'
        plan['position'] = '15-20'
        
    elif 'WAVE-3' in wave_stage:
        wave_1_range = fib['236'] - fib['786'] if fib['236'] > fib['786'] else wave_range
        plan['entry_low'] = round(price * 0.99, 0)
        plan['entry_high'] = round(price * 1.02, 0)
        plan['stop_loss'] = round(fib['500'], 0)
        plan['target1'] = round(fib['236'] + wave_1_range * 1.618, 0)
        plan['target2'] = round(fib['236'] + wave_1_range * 2.618, 0)
        plan['immediate'] = 'BUY FULL - Wave 3 is the strongest impulse'
        plan['exit'] = 'Book 50% at T1 (161.8% ext), trail SL on balance'
        plan['position'] = '15-20'
        
    elif 'WAVE-4' in wave_stage:
        plan['entry_low'] = round(fib['382'], 0)
        plan['entry_high'] = round(fib['500'], 0)
        plan['stop_loss'] = round(fib['618'] * 0.98, 0)
        plan['target1'] = round(fib['236'], 0)
        plan['target2'] = round(fib['236'] + wave_range * 0.272, 0)
        plan['immediate'] = 'WAIT - Buy only on breakout above consolidation'
        plan['exit'] = 'Tight SL. Book 100% at T1 if momentum weak'
        plan['position'] = '5-10'
        
    elif 'WAVE-5' in wave_stage:
        wave_1_3_range = fib['236'] - fib['786']
        if wave_1_3_range <= 0: wave_1_3_range = wave_range
        plan['entry_low'] = round(price * 0.99, 0)
        plan['entry_high'] = round(price * 1.01, 0)
        plan['stop_loss'] = round(fib['382'], 0)
        plan['target1'] = round(price + wave_1_3_range * 0.618, 0)
        plan['target2'] = round(price + wave_1_3_range * 1.0, 0)
        plan['immediate'] = 'QUICK TRADE - Final wave, limited upside'
        plan['exit'] = 'BOOK 100% at T1 or first reversal signal'
        plan['position'] = '5-10'
        
    else:
        plan['immediate'] = 'NO TRADE - Pattern unclear'
        plan['exit'] = 'Stay in cash, wait for clear wave formation'
        plan['position'] = '0'
    
    if plan['target1'] > 0 and price > 0:
        plan['target1_pct'] = round(((plan['target1'] - price) / price) * 100, 1)
    if plan['target2'] > 0 and price > 0:
        plan['target2_pct'] = round(((plan['target2'] - price) / price) * 100, 1)
    if plan['stop_loss'] > 0 and price > 0:
        risk = abs(price - plan['stop_loss'])
        reward = abs(plan['target1'] - price)
        plan['risk_reward'] = round(reward / risk, 1) if risk > 0 else 0
        
        if plan['risk_reward'] < 1.5:
            plan['stop_loss'] = round(price * 0.97, 0)
            new_risk = abs(price - plan['stop_loss'])
            if new_risk > 0:
                plan['risk_reward'] = round(reward / new_risk, 1)
    
    return plan

def send_pulse_alert(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900: text = text[:3900]
        resp = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        return resp.json().get('ok', False)
    except: return False

def run_pulse_scan():
    nse = Nse()
    alerts = []
    now = datetime.now()
    print(f"Market Pulse - {now.strftime('%d-%b %I:%M %p')}")
    stocks = discover_moving_stocks()
    
    for symbol in stocks:
        try:
            q = nse.get_quote(symbol)
            if not q: continue
            intraday = q.get('intraDayHighLow', {})
            weekly = q.get('weekHighLow', {})
            price = float(q.get('lastPrice', 0))
            if price == 0: continue
            high = float(intraday.get('max', 0))
            low = float(intraday.get('min', 0))
            open_p = float(q.get('open', 0))
            change_pct = float(q.get('pChange', 0))
            prev_close = float(q.get('previousClose', 0))
            high_52 = float(weekly.get('max', 0))
            low_52 = float(weekly.get('min', 0))
            
            # HONEST delivery data
            try:
                vol = float(q.get('totalTradedVolume', 0))
                dq = float(q.get('deliveryQuantity', 0))
                bq = float(q.get('totalBuyQuantity', 0))
                sq = float(q.get('totalSellQuantity', 0))
                
                if vol > 0 and dq > 0:
                    dp = (dq / vol * 100)
                    delivery_label = f"Del: {dp:.0f}%"
                elif vol > 0:
                    total = bq + sq
                    if total > 0:
                        buy_pct = (bq / total) * 100
                        delivery_label = f"Buy: {buy_pct:.0f}%"
                        dp = buy_pct
                    else:
                        delivery_label = "N/A"
                        dp = 0
                else:
                    delivery_label = "N/A"
                    dp = 0
                    
                vr = bq / sq if sq > 0 else 1.0
                
            except:
                delivery_label = "N/A"
                dp = 0
                vr = 1.0
            
            wave = detect_neo_wave(price, high, low, open_p, prev_close, high_52, low_52, change_pct)
            breakout = detect_breakout(price, high, low, open_p, prev_close, high_52, change_pct, dp, vr)
            
            if wave['confidence'] >= 30 or breakout['is_breakout']:
                alerts.append({
                    'symbol':symbol,
                    'price':price,
                    'change':change_pct,
                    'wave':wave,
                    'breakout':breakout,
                    'delivery':dp,
                    'delivery_label':delivery_label,
                    'volume_ratio':vr,
                    'time':now.strftime('%I:%M %p')
                })
            time.sleep(0.08)
        except: pass
    return alerts, now

def build_message(alerts, now):
    if not alerts: return None
    alerts.sort(key=lambda x: x['wave']['confidence'], reverse=True)
    
    patterns = [a for a in alerts if a['wave']['confidence'] >= 30]
    breakouts = [a for a in alerts if a['breakout']['is_breakout']]
    
    good_patterns = []
    for a in patterns:
        w = a['wave']; p = a['price']; fib = w['fib_levels']
        action = get_wave_action(w['stage'], p, fib)
        if action['risk_reward'] >= 1.0:
            a['action'] = action
            good_patterns.append(a)
    patterns = good_patterns
    
    msg = f"<b>MARKET PULSE</b>\n{now.strftime('%d-%b %I:%M %p')} IST\n{'='*30}\n\n"
    msg += f"Neo Wave: {len(patterns)} | Breakouts: {len(breakouts)}\n\n"
    
    if patterns:
        msg += f"<b>NEO WAVE PATTERNS</b>\n{'='*30}\n\n"
        for i, a in enumerate(patterns[:3], 1):
            w = a['wave']
            p = a['price']
            action = a['action']
            emoji = "🟢" if w['confidence']>=60 else "🔵" if w['confidence']>=40 else "🟡"
            
            msg += f"{emoji} <b>{i}. {a['symbol']}</b> | Rs.{p:.0f} | {a['change']:+.1f}%\n"
            msg += f"   Wave: {w['stage']} ({w['confidence']}%)\n"
            msg += f"   Entry: Rs.{action['entry_low']}-{action['entry_high']} | SL: Rs.{action['stop_loss']}\n"
            msg += f"   T1: Rs.{action['target1']} (+{action['target1_pct']}%) | T2: Rs.{action['target2']} (+{action['target2_pct']}%)\n"
            msg += f"   Action: {action['immediate']}\n"
            msg += f"   Exit: {action['exit']}\n"
            msg += f"   Risk: 1:{action['risk_reward']} | Pos: {action['position']}%\n\n"
    
    if breakouts:
        msg += f"<b>BREAKOUT SCANS</b>\n{'='*30}\n\n"
        for i, a in enumerate(breakouts[:3], 1):
            b = a['breakout']
            emoji = "🟢" if b['strength']=="STRONG" else "🔵" if b['strength']=="MODERATE" else "🟡"
            
            msg += f"{emoji} <b>{i}. {a['symbol']}</b> | Rs.{a['price']:.0f} | {a['change']:+.1f}%\n"
            msg += f"   Type: {b['type']} | Strength: {b['strength']}\n"
            if b['confirmations']: msg += f"   + {', '.join(b['confirmations'][:2])}\n"
            if b['weaknesses']: msg += f"   - {', '.join(b['weaknesses'][:2])}\n"
            msg += f"   {a['delivery_label']}\n\n"
    
    msg += f"{'='*30}\nAuto-Scanner | Every Hour"
    return msg

if __name__ == "__main__":
    alerts, now = run_pulse_scan()
    if alerts:
        msg = build_message(alerts, now)
        if msg and send_pulse_alert(msg): print(f"Sent! {len(alerts)} alerts")
        else: print("Failed")
    else:
        send_pulse_alert(f"<b>Market Pulse</b>\n{now.strftime('%d-%b %I:%M %p')}\n\nAll quiet. No patterns detected.")

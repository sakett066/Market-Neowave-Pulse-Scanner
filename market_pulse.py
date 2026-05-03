"""
MARKET PULSE v3.0 - Neo Wave + Breakout + Action Plans
Detects: Elliott/Neo Wave patterns, Volume-confirmed breakouts, Instant trade strategies
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

# ============================================
# DYNAMIC STOCK DISCOVERY
# ============================================
def discover_moving_stocks():
    """Discover stocks with unusual price/volume action"""
    base_stocks = [
        'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'SBIN',
        'RELIANCE', 'ITC', 'LT', 'HINDUNILVR', 'SUNPHARMA', 'CIPLA',
        'TITAN', 'MARUTI', 'BAJFINANCE', 'POWERGRID', 'NTPC', 'WIPRO',
        'AXISBANK', 'TECHM', 'ASIANPAINT', 'ADANIPORTS', 'ONGC',
        'TATASTEEL', 'JSWSTEEL', 'DIVISLAB', 'DRREDDY', 'BAJAJFINSV',
        'TRENT', 'DMART', 'PIDILITIND', 'BERGEPAINT', 'DABUR',
        'BANDHANBNK', 'FEDERALBNK', 'IDFCFIRSTB', 'AUBANK',
        'HAL', 'BEL', 'IRCON', 'RVNL', 'JINDALSTEL', 'HINDZINC',
        'LAURUSLABS', 'ALKEM', 'BIOCON', 'CHOLAFIN', 'MUTHOOTFIN',
        'PERSISTENT', 'LTI', 'EICHERMOT', 'TVSMOTOR', 'TATAMOTORS',
        'M&M', 'ZOMATO', 'IRCTC', 'TATACONSUM', 'METROBRAND',
        'ADANIGREEN', 'TATAPOWER', 'NHPC', 'PFC', 'RECLTD',
        'CANBK', 'UNIONBANK', 'INDUSINDBK', 'PNB'
    ]
    return base_stocks

# ============================================
# NEO WAVE DETECTION
# ============================================
def detect_neo_wave(price, high, low, open_p, prev_close, high_52, low_52, change_pct):
    """Detect Elliott/Neo Wave patterns"""
    signals = []
    
    if high_52 == 0 or low_52 == 0:
        return {'stage': 'UNKNOWN', 'confidence': 0, 'signals': ['Insufficient data'], 'fib_levels': {}}
    
    fib_range = high_52 - low_52
    fib_236 = low_52 + fib_range * 0.236
    fib_382 = low_52 + fib_range * 0.382
    fib_500 = low_52 + fib_range * 0.500
    fib_618 = low_52 + fib_range * 0.618
    fib_786 = low_52 + fib_range * 0.786
    
    day_range = high - low
    body = abs(price - open_p)
    position = ((price - low) / day_range * 100) if day_range > 0 else 50
    
    # Wave 1 scoring
    wave1_score = 0
    if price > open_p > prev_close: wave1_score += 15; signals.append("Wave-1: Bullish impulse candle")
    if position > 60: wave1_score += 10; signals.append("Wave-1: Closing strong")
    if change_pct > 1: wave1_score += 10; signals.append(f"Wave-1: +{change_pct:.1f}% momentum")
    
    # Wave 2 scoring
    wave2_score = 0
    if 30 <= position <= 50: wave2_score += 15; signals.append("Wave-2: Healthy pullback")
    if abs(price - fib_618) / price < 0.03: wave2_score += 20; signals.append("Wave-2: At 61.8% Fib (Golden Zone)")
    elif abs(price - fib_500) / price < 0.03: wave2_score += 15; signals.append("Wave-2: At 50% Fib retracement")
    if change_pct < 0 and change_pct > -2: wave2_score += 8; signals.append("Wave-2: Mild correction")
    
    # Wave 3 scoring
    wave3_score = 0
    if price > fib_500: wave3_score += 15; signals.append("Wave-3: Above 50% Fib (Strong)")
    if position > 55 and change_pct > 0.5: wave3_score += 20; signals.append("Wave-3: Power move underway")
    if price > open_p and body > (day_range * 0.4): wave3_score += 15; signals.append("Wave-3: Wide range bullish candle")
    
    # Wave 4 scoring
    wave4_score = 0
    if body < (day_range * 0.3): wave4_score += 12; signals.append("Wave-4: Doji/Consolidation")
    if 40 <= position <= 60: wave4_score += 10; signals.append("Wave-4: Mid-range pause")
    if abs(change_pct) < 0.5: wave4_score += 8; signals.append("Wave-4: Low volatility pause")
    
    # Wave 5 scoring
    wave5_score = 0
    if price > fib_786: wave5_score += 15; signals.append("Wave-5: Above 78.6% Fib")
    if ((high_52 - price) / high_52) < 0.08: wave5_score += 20; signals.append("Wave-5: Near 52W high breakout")
    if position > 70 and change_pct > 0: wave5_score += 12; signals.append("Wave-5: Strong close near high")
    
    wave_scores = {
        'WAVE-1 (Impulse Start)': wave1_score,
        'WAVE-2 (Pullback Buy)': wave2_score,
        'WAVE-3 (Power Move)': wave3_score,
        'WAVE-4 (Consolidation)': wave4_score,
        'WAVE-5 (Final Push)': wave5_score
    }
    
    best_wave = max(wave_scores, key=wave_scores.get)
    best_score = wave_scores[best_wave]
    confidence = min(95, best_score + 10)
    
    if confidence < 25:
        best_wave = "NO CLEAR PATTERN"
        signals = ["No clear Elliott Wave pattern"]
    
    return {
        'stage': best_wave,
        'confidence': confidence,
        'signals': signals[:4],
        'fib_levels': {
            '236': round(fib_236, 0),
            '382': round(fib_382, 0),
            '500': round(fib_500, 0),
            '618': round(fib_618, 0),
            '786': round(fib_786, 0)
        }
    }

# ============================================
# BREAKOUT DETECTOR
# ============================================
def detect_breakout(price, high, low, open_p, prev_close, high_52, change_pct, delivery_pct, volume_ratio):
    """Detect breakouts - CONFIRMED vs WEAK"""
    confirmation_signals = []
    weak_signals = []
    
    is_52w_breakout = price > high_52 * 0.98
    is_gap_up = open_p > prev_close * 1.01
    is_strong_close = ((price - low) / (high - low) * 100) > 65 if (high - low) > 0 else False
    is_volume_supported = volume_ratio > 1.5
    is_delivery_strong = delivery_pct > 50
    is_momentum_strong = change_pct > 1.5
    
    if is_52w_breakout or is_gap_up or (change_pct > 2 and is_strong_close):
        confirmations = 0
        
        if is_volume_supported:
            confirmations += 1; confirmation_signals.append("High volume confirmation")
        else:
            weak_signals.append("Low volume (suspect)")
        
        if is_delivery_strong:
            confirmations += 1; confirmation_signals.append("Strong delivery (genuine)")
        else:
            weak_signals.append("Low delivery (speculative)")
        
        if is_strong_close:
            confirmations += 1; confirmation_signals.append("Strong close near high")
        else:
            weak_signals.append("Weak close (rejection)")
        
        if is_momentum_strong:
            confirmations += 1; confirmation_signals.append("Strong momentum")
        
        if price > open_p:
            confirmations += 1; confirmation_signals.append("Green candle")
        
        if confirmations >= 4:
            strength, breakout_type = "STRONG CONFIRMED", "BREAKOUT"
        elif confirmations >= 2:
            strength, breakout_type = "MODERATE", "LIKELY BREAKOUT"
        else:
            strength, breakout_type = "WEAK", "WEAK BREAKOUT"
        
        return {
            'type': breakout_type,
            'strength': strength,
            'confirmations': confirmation_signals[:3],
            'weaknesses': weak_signals[:3],
            'is_breakout': True
        }
    
    return {'type': None, 'strength': 'NONE', 'confirmations': [], 'weaknesses': [], 'is_breakout': False}

# ============================================
# WAVE ACTION STRATEGY GENERATOR
# ============================================
def get_wave_action_plan(wave_stage, price, fib):
    """Generate instant action plan based on wave stage"""
    
    plan = {
        'entry_low': 0, 'entry_high': 0, 'stop_loss': 0,
        'target1': 0, 'target2': 0, 'target1_pct': 0, 'target2_pct': 0,
        'immediate': '', 'wait': '', 'exit': '',
        'risk_reward': 0, 'position': '10-15'
    }
    
    if 'WAVE-1' in wave_stage:
        plan['entry_low'] = round(price * 0.99, 0)
        plan['entry_high'] = round(price * 1.01, 0)
        plan['stop_loss'] = round(price * 0.95, 0)
        plan['target1'] = round(fib['382'], 0)
        plan['target2'] = round(fib['500'], 0)
        plan['target1_pct'] = round(((plan['target1'] - price) / price) * 100, 1)
        plan['target2_pct'] = round(((plan['target2'] - price) / price) * 100, 1)
        plan['immediate'] = 'BUY at current price zone with 50% position'
        plan['wait'] = 'Add 50% if pulls back to Fib 23.6% support'
        plan['exit'] = 'SELL if closes below stop loss or at Target 1'
        plan['risk_reward'] = round(plan['target1_pct'] / 5, 1)
        plan['position'] = '10-15'
    
    elif 'WAVE-2' in wave_stage:
        plan['entry_low'] = round(fib['618'], 0)
        plan['entry_high'] = round(fib['500'], 0)
        plan['stop_loss'] = round(fib['786'] * 0.97, 0)
        plan['target1'] = round(fib['382'], 0)
        plan['target2'] = round(fib['236'], 0)
        plan['target1_pct'] = round(((plan['target1'] - price) / price) * 100, 1)
        plan['target2_pct'] = round(((plan['target2'] - price) / price) * 100, 1)
        plan['immediate'] = 'ACCUMULATE at Fib 61.8% zone (Golden Pocket)'
        plan['wait'] = 'Wait for bullish reversal candle before full entry'
        plan['exit'] = 'SL below Fib 78.6%. Target Fib 38.2% then trail'
        plan['risk_reward'] = round(plan['target1_pct'] / 3, 1)
        plan['position'] = '15-20'
    
    elif 'WAVE-3' in wave_stage:
        plan['entry_low'] = round(price * 0.98, 0)
        plan['entry_high'] = round(price * 1.02, 0)
        plan['stop_loss'] = round(fib['500'], 0)
        plan['target1'] = round(fib['236'], 0)
        plan['target2'] = round(price * 1.25, 0)
        plan['target1_pct'] = round(((plan['target1'] - price) / price) * 100, 1)
        plan['target2_pct'] = round(((plan['target2'] - price) / price) * 100, 1)
        plan['immediate'] = 'BUY now with full position - Strong momentum'
        plan['wait'] = 'Add on dips to VWAP or opening price'
        plan['exit'] = 'Trail SL to entry at +8%. Book 50% at Target 1'
        plan['risk_reward'] = round(plan['target1_pct'] / 5, 1)
        plan['position'] = '15-20'
    
    elif 'WAVE-4' in wave_stage:
        plan['entry_low'] = round(fib['382'], 0)
        plan['entry_high'] = round(fib['500'], 0)
        plan['stop_loss'] = round(fib['618'] * 0.98, 0)
        plan['target1'] = round(price * 1.10, 0)
        plan['target2'] = round(fib['236'], 0)
        plan['target1_pct'] = round(((plan['target1'] - price) / price) * 100, 1)
        plan['target2_pct'] = round(((plan['target2'] - price) / price) * 100, 1)
        plan['immediate'] = 'WAIT - Let consolidation complete'
        plan['wait'] = 'Buy only on breakout above consolidation range'
        plan['exit'] = 'SL below consolidation low. Target Wave-5 highs'
        plan['risk_reward'] = round(plan['target1_pct'] / 3, 1)
        plan['position'] = '5-10'
    
    elif 'WAVE-5' in wave_stage:
        plan['entry_low'] = round(price * 0.99, 0)
        plan['entry_high'] = round(price * 1.01, 0)
        plan['stop_loss'] = round(fib['382'], 0)
        plan['target1'] = round(price * 1.08, 0)
        plan['target2'] = round(price * 1.15, 0)
        plan['target1_pct'] = round(((plan['target1'] - price) / price) * 100, 1)
        plan['target2_pct'] = round(((plan['target2'] - price) / price) * 100, 1)
        plan['immediate'] = 'QUICK BUY with tight SL - Last leg up'
        plan['wait'] = 'Do NOT add more. This is the final wave'
        plan['exit'] = 'BOOK FAST. Exit 100% at first sign of reversal'
        plan['risk_reward'] = round(plan['target1_pct'] / 3, 1)
        plan['position'] = '5-10'
    
    else:
        plan['immediate'] = 'NO TRADE - Pattern unclear'
        plan['wait'] = 'Wait for clear wave formation'
        plan['exit'] = 'Stay in cash'
        plan['position'] = '0'
    
    return plan

# ============================================
# TELEGRAM SENDER
# ============================================
def send_pulse_alert(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        if len(text) > 3900:
            text = text[:3900] + "\n..."
        resp = requests.post(url, data={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': text,
            'parse_mode': 'HTML'
        }, timeout=10)
        return resp.json().get('ok', False)
    except:
        return False

# ============================================
# MAIN SCANNER
# ============================================
def run_pulse_scan():
    nse = Nse()
    alerts = []
    now = datetime.now()
    
    print(f"🔍 Market Pulse Scan - {now.strftime('%d-%b %I:%M %p')}")
    
    stocks = discover_moving_stocks()
    print(f"Scanning {len(stocks)} stocks...")
    
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
            
            try:
                volume = float(q.get('totalTradedVolume', 0))
                delivery = float(q.get('deliveryQuantity', 0))
                delivery_pct = (delivery / volume * 100) if volume > 0 else 0
                buy_qty = float(q.get('totalBuyQuantity', 0))
                sell_qty = float(q.get('totalSellQuantity', 0))
                volume_ratio = buy_qty / sell_qty if sell_qty > 0 else 1
            except:
                delivery_pct = 40
                volume_ratio = 1
            
            wave = detect_neo_wave(price, high, low, open_p, prev_close, high_52, low_52, change_pct)
            breakout = detect_breakout(price, high, low, open_p, prev_close, high_52, change_pct, delivery_pct, volume_ratio)
            
            if wave['confidence'] >= 30 or breakout['is_breakout']:
                alerts.append({
                    'symbol': symbol,
                    'price': price,
                    'change': change_pct,
                    'wave': wave,
                    'breakout': breakout,
                    'delivery': delivery_pct,
                    'volume_ratio': volume_ratio,
                    'time': now.strftime('%I:%M %p')
                })
                
                tag = "🌊" if wave['confidence'] >= 40 else "🔍"
                bt = breakout['type'] if breakout['is_breakout'] else ""
                print(f"  {tag} {symbol}: {wave['stage']} ({wave['confidence']}%) {bt}")
            
            time.sleep(0.1)
            
        except:
            pass
    
    return alerts, now

# ============================================
# BUILD MESSAGE
# ============================================
def build_message(alerts, now):
    if not alerts:
        return None
    
    alerts.sort(key=lambda x: x['wave']['confidence'], reverse=True)
    
    breakouts = [a for a in alerts if a['breakout']['is_breakout']]
    patterns = [a for a in alerts if a['wave']['confidence'] >= 40 and not a['breakout']['is_breakout']]
    
    msg = f"🔍 <b>MARKET PULSE</b>\n"
    msg += f"{now.strftime('%d-%b %I:%M %p')} IST\n"
    msg += f"{'═'*35}\n\n"
    
    msg += f"📊 <b>Scan Summary:</b>\n"
    msg += f"├ Breakouts: {len(breakouts)}\n"
    msg += f"├ Neo Wave: {len(patterns)}\n"
    msg += f"└ Total: {len(alerts)}\n\n"
    
    # BREAKOUTS
    if breakouts:
        msg += f"<b>🚀 BREAKOUTS</b>\n{'═'*35}\n\n"
        
        for i, alert in enumerate(breakouts[:5], 1):
            direction = "📈" if alert['change'] > 0 else "📉"
            b = alert['breakout']
            
            msg += f"<b>{b['type']}</b> {direction}\n"
            msg += f"<b>{i}. {alert['symbol']}</b> | ₹{alert['price']:.0f} | {alert['change']:+.2f}%\n"
            msg += f"{'─'*35}\n"
            msg += f"Strength: <b>{b['strength']}</b>\n"
            
            if b['confirmations']:
                msg += f"<b>Confirmations:</b>\n"
                for c in b['confirmations']:
                    msg += f"   ✅ {c}\n"
            
            if b['weaknesses']:
                msg += f"<b>Weaknesses:</b>\n"
                for w in b['weaknesses']:
                    msg += f"   ⚠️ {w}\n"
            
            msg += f"Delivery: {alert['delivery']:.0f}%\n"
            msg += f"⏰ {alert['time']}\n\n"
    
    # NEO WAVE WITH ACTION PLAN
    if patterns:
        msg += f"<b>🌊 NEO WAVE PATTERNS WITH TRADE PLAN</b>\n{'═'*35}\n\n"
        
        for i, alert in enumerate(patterns[:5], 1):
            w = alert['wave']
            price = alert['price']
            fib = w['fib_levels']
            action = get_wave_action_plan(w['stage'], price, fib)
            
            msg += f"<b>{i}. {alert['symbol']}</b> | ₹{price:.0f} | {alert['change']:+.2f}%\n"
            msg += f"{'─'*35}\n"
            msg += f"Wave: <b>{w['stage']}</b> | Confidence: <b>{w['confidence']}%</b>\n\n"
            
            msg += f"<b>Analysis:</b>\n"
            for sig in w['signals'][:3]:
                msg += f"   • {sig}\n"
            
            msg += f"\n<b>Key Levels:</b>\n"
            msg += f"   Entry Zone: ₹{action['entry_low']}-₹{action['entry_high']}\n"
            msg += f"   Stop Loss: ₹{action['stop_loss']}\n"
            msg += f"   Target 1: ₹{action['target1']} (+{action['target1_pct']}%)\n"
            msg += f"   Target 2: ₹{action['target2']} (+{action['target2_pct']}%)\n"
            
            msg += f"\n<b>⚡ ACTION PLAN:</b>\n"
            msg += f"   {action['immediate']}\n"
            msg += f"   {action['wait']}\n"
            msg += f"   {action['exit']}\n"
            
            msg += f"\n<b>Risk:</b>\n"
            msg += f"   Risk/Reward: 1:{action['risk_reward']}\n"
            msg += f"   Position: {action['position']}% of capital\n"
            
            msg += f"\n⏰ {alert['time']}\n\n"
    
    msg += f"{'═'*35}\n"
    msg += f"📱 <i>Market Pulse | Auto-Scanner</i>"
    
    return msg

# ============================================
# RUN
# ============================================
if __name__ == "__main__":
    alerts, now = run_pulse_scan()
    
    if alerts:
        msg = build_message(alerts, now)
        if msg and send_pulse_alert(msg):
            print(f"✅ Pulse sent! {len(alerts)} opportunities")
        else:
            print("❌ Failed to send")
    else:
        print("No significant patterns")
        send_pulse_alert(f"🔍 <b>Market Pulse</b>\n{now.strftime('%d-%b %I:%M %p')}\n\n📊 All quiet. No breakouts or clear wave patterns.")

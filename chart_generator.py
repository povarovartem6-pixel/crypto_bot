import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import ccxt
import io

def generate_signal_chart(coin: str, signal_type: str, entry: float, sl: float, tp1: float):
    exchange = ccxt.binance({'options': {'defaultType': 'future'}})
    try: ohlcv = exchange.fetch_ohlcv(f'{coin}/USDT', '15m', limit=50)
    except: return None
    
    df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    
    fig, ax = plt.subplots(figsize=(10, 5), facecolor='#1e1e1e')
    ax.set_facecolor('#1e1e1e')
    
    for i, row in df.iterrows():
        color = '#26a69a' if row['close'] >= row['open'] else '#ef5350'
        ax.plot([row['time'], row['time']], [row['low'], row['high']], color=color, linewidth=1)
        ax.add_patch(plt.Rectangle((row['time'] - pd.Timedelta(minutes=2), min(row['open'], row['close'])), 
                                   pd.Timedelta(minutes=4), abs(row['close'] - row['open']), 
                                   color=color, alpha=0.8))

    ax.axhline(entry, color='#2196f3', linestyle='-', linewidth=2, label=f'Entry: ${entry:.4f}')
    ax.axhline(sl, color='#f44336', linestyle='--', linewidth=1.5, label=f'SL: ${sl:.4f}')
    ax.axhline(tp1, color='#4caf50', linestyle='--', linewidth=1.5, label=f'TP1: ${tp1:.4f}')
    
    ax.set_title(f'{coin}/USDT - {signal_type}', color='white', fontsize=14, fontweight='bold')
    ax.tick_params(colors='white')
    for spine in ax.spines.values(): spine.set_color('white')
    ax.legend(facecolor='#1e1e1e', labelcolor='white')
    ax.grid(color='#333333', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, facecolor='#1e1e1e')
    buf.seek(0)
    plt.close()
    return buf

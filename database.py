import sqlite3, json
from datetime import datetime
from typing import Optional, List, Dict

DB_PATH = 'shiper_signal.db'

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT,
        tariff TEXT DEFAULT 'free', tariff_expiry TEXT, trial_used INTEGER DEFAULT 0,
        exchange TEXT DEFAULT 'binance', created_at TEXT, is_blocked INTEGER DEFAULT 0,
        notifications_enabled INTEGER DEFAULT 1, balance_usdt REAL DEFAULT 0.0
    );
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, coin TEXT, timeframe TEXT, signal_type TEXT,
        entry_price REAL, stop_loss REAL, target_prices TEXT, confidence REAL,
        risk_reward REAL, atr_pct REAL, created_at TEXT, status TEXT DEFAULT 'active'
    );
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, signal_id INTEGER,
        entry_price REAL, stop_loss REAL, tp1 REAL, tp2 REAL, tp3 REAL, size REAL,
        status TEXT DEFAULT 'open', realized_pnl REAL DEFAULT 0,
        opened_at TEXT, closed_at TEXT, notes TEXT
    );
    CREATE TABLE IF NOT EXISTS paid_invoices (
        invoice_id TEXT PRIMARY KEY, user_id INTEGER, tariff TEXT, paid_at TEXT
    );
    ''')
    conn.commit()
    conn.close()

class Database:
    def __init__(self): init_db()

    def add_user(self, user_id, username, first_name, last_name):
        conn = get_conn()
        conn.execute('''INSERT OR IGNORE INTO users
            (user_id, username, first_name, last_name, created_at)
            VALUES (?,?,?,?,?)''', (user_id, username, first_name, last_name, datetime.now().isoformat()))
        conn.commit(); conn.close()

    def get_user(self, uid) -> Optional[Dict]:
        conn = get_conn()
        row = conn.execute('SELECT * FROM users WHERE user_id = ?', (uid,)).fetchone()
        conn.close()
        return dict(row) if row else None

    def update_user(self, uid, **kw):
        if not kw: return
        conn = get_conn()
        keys = ', '.join(f'{k} = ?' for k in kw)
        conn.execute(f'UPDATE users SET {keys} WHERE user_id = ?', (*kw.values(), uid))
        conn.commit(); conn.close()

    def get_all_users(self) -> List[Dict]:
        conn = get_conn()
        rows = conn.execute('SELECT * FROM users').fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def add_signal(self, **kw) -> int:
        conn = get_conn(); c = conn.cursor()
        c.execute('''INSERT INTO signals
            (coin, timeframe, signal_type, entry_price, stop_loss, target_prices,
             confidence, risk_reward, atr_pct, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (kw['coin'], kw['timeframe'], kw['signal_type'], kw['entry_price'],
             kw['stop_loss'], json.dumps(kw['target_prices']), kw['confidence'],
             kw.get('risk_reward', 0), kw.get('atr_pct', 1.0), datetime.now().isoformat()))
        sid = c.lastrowid
        conn.commit(); conn.close()
        return sid

    def open_trade(self, uid, sid, entry, sl, tp1, tp2, tp3, size):
        conn = get_conn(); c = conn.cursor()
        c.execute('''INSERT INTO trades (user_id, signal_id, entry_price, stop_loss,
            tp1, tp2, tp3, size, opened_at) VALUES (?,?,?,?,?,?,?,?,?)''',
            (uid, sid, entry, sl, tp1, tp2, tp3, size, datetime.now().isoformat()))
        tid = c.lastrowid
        conn.commit(); conn.close()
        return tid

    def get_open_trades(self, uid=None) -> List[Dict]:
        conn = get_conn()
        if uid:
            rows = conn.execute('SELECT * FROM trades WHERE status="open" AND user_id=?', (uid,)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM trades WHERE status="open"').fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def close_trade(self, tid, exit_price, pnl, notes=''):
        conn = get_conn()
        conn.execute('UPDATE trades SET status="closed", realized_pnl=?, closed_at=?, notes=? WHERE id=?',
                     (pnl, datetime.now().isoformat(), notes, tid))
        conn.commit(); conn.close()

    def invoice_already_used(self, invoice_id):
        conn = get_conn()
        r = conn.execute('SELECT 1 FROM paid_invoices WHERE invoice_id=?', (str(invoice_id),)).fetchone()
        conn.close()
        return r is not None

    def mark_invoice_paid(self, invoice_id, user_id, tariff):
        conn = get_conn()
        conn.execute('INSERT OR IGNORE INTO paid_invoices (invoice_id, user_id, tariff, paid_at) VALUES (?,?,?,?)',
                     (str(invoice_id), user_id, tariff, datetime.now().isoformat()))
        conn.commit(); conn.close()

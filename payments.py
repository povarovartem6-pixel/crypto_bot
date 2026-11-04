import requests
from config import CRYPTOBOT_API_TOKEN, TARIFFS

class CryptoBotPayment:
    def __init__(self):
        self.api_url = 'https://pay.crypt.bot/api'
        self.headers = {'Crypto-Pay-API-Token': CRYPTOBOT_API_TOKEN, 'Content-Type': 'application/json'}

    def create_invoice(self, user_id: int, tariff: str):
        t = TARIFFS.get(tariff)
        if not t or t['price'] == 0: return None
        data = {
            'asset': 'USDT', 'amount': str(t['price']),
            'description': f"Подписка {t['name']} на 30 дней",
            'payload': f"user_{user_id}_tariff_{tariff}", 'expires_in': 3600
        }
        try:
            res = requests.post(f'{self.api_url}/createInvoice', headers=self.headers, json=data, timeout=10).json()
            if res.get('ok'):
                inv = res['result']
                return {'invoice_id': inv['invoice_id'], 'pay_url': inv['pay_url'], 'amount': t['price']}
        except: pass
        return None

    def check_invoice(self, invoice_id: int, expected_user_id=None):
        try:
            res = requests.get(f'{self.api_url}/getInvoices', headers=self.headers, params={'invoice_ids': str(invoice_id)}, timeout=10).json()
            if res.get('ok') and res['result']['items']:
                inv = res['result']['items'][0]
                if inv['status'] != 'paid': return False
                if expected_user_id and f"user_{expected_user_id}" not in inv.get('payload', ''): return False
                return True
        except: pass
        return False

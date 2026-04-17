import requests

class BinanceHandler:
    BASE_URL = 'https://api.binance.com/api/v3/'

    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret

    def verify_payment(self, transaction_id):
        # Example function to verify a payment
        response = requests.get(f'{self.BASE_URL}transaction/{transaction_id}', headers=self._get_headers())
        return response.json()

    def get_deposit_address(self, coin):
        # Example function to retrieve deposit address
        response = requests.get(f'{self.BASE_URL}depositAddress', headers=self._get_headers(), params={'coin': coin})
        return response.json()

    def _get_headers(self):
        return {
            'X-MBX-APIKEY': self.api_key
        }
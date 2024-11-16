import requests
from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class FireflyAccount:
    id: int
    name: str
    type: str

class FireflyClient:
    def __init__(self, base_url: str, personal_access_token: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {personal_access_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })

    def get_accounts(self) -> list[FireflyAccount]:
        """Get list of asset accounts from Firefly III"""
        response = self.session.get(f"{self.base_url}/api/v1/accounts")
        response.raise_for_status()
        accounts = []
        for acc in response.json()['data']:
            if acc['attributes']['type'] == 'asset':
                accounts.append(FireflyAccount(
                    id=acc['id'],
                    name=acc['attributes']['name'],
                    type=acc['attributes']['type']
                ))
        return accounts

    def create_transaction(self, account_id: int, amount: float, date: date, 
                         description: str, notes: str, external_id: str,
                         payee: Optional[str] = None):
        """Create a transaction in Firefly III"""
        data = {
            "transactions": [{
                "type": "withdrawal" if amount < 0 else "deposit",
                "date": date.isoformat(),
                "amount": str(abs(amount)),
                "description": description,
                "notes": notes,
                "external_id": external_id,
                "source_id": account_id if amount < 0 else None,
                "destination_id": account_id if amount > 0 else None,
                "destination_name": payee if amount < 0 else None,
                "source_name": payee if amount > 0 else None,
            }]
        }
        
        response = self.session.post(f"{self.base_url}/api/v1/transactions", json=data)
        response.raise_for_status()
        return response.json()

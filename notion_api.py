import json

import requests

base_url = "https://api.notion.com/v1"


class NotionAPI:
    def __init__(self, access_token):
        self.access_token = access_token

    def search(self):
        req = requests.post(
            f"{base_url}/search",
            headers={"Authorization": f"Bearer {self.access_token}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"},
            data=json.dumps({
                "query": "AskNotes",
                "page_size": 1
            })
        )
        response = req.json()
        return response

    def get_block_children(self, block_id):
        req = requests.get(
            f"{base_url}/blocks/{block_id}/children",
            headers={"Authorization": f"Bearer {self.access_token}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
        )
        response = req.json()
        return response

    def get_database(self, database_id):
        req = requests.get(
            f"{base_url}/databases/{database_id}",
            headers={"Authorization": f"Bearer {self.access_token}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
        )
        response = req.json()
        return response

    def query_database(self, database_id, query):
        req = requests.post(
            f"{base_url}/databases/{database_id}/query",
            headers={"Authorization": f"Bearer {self.access_token}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"},
            data=json.dumps(query)
        )
        response = req.json()
        return response

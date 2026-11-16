import json
import os
from urllib.parse import quote
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession


def load_sheet():
    info = json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
    credentials = service_account.Credentials.from_service_account_info(info,
                    scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    spreadsheet = os.getenv('SPREADSHEET_ID', '1swhGmEQhrn0tyMUrRHA0q6LaxWg4WFl9CnGJtM1Jg4w')
    sheet = os.getenv('SHEET_NAME', 'DB Resolved').replace("'", "''")
    with AuthorizedSession(credentials) as client:
        response = client.get(f'https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet, safe="")}/values/'
                              + quote(f"'{sheet}'!A:M", safe=''),
                              params={'valueRenderOption':'UNFORMATTED_VALUE', 'dateTimeRenderOption':'SERIAL_NUMBER'},
                              timeout=(10,90))
        response.raise_for_status()
        return response.json().get('values', [])

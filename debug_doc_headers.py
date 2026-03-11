import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

FILE_ID = "1p0nmiiZq7O22Clwq0dixYTUlTykBQTL73-LtF4LtKd0"

def check_doc_structure():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/documents'
    ]
    
    os.chdir('/Users/renancarvalho/Desktop/vicelos_sistema')
    creds = Credentials.from_authorized_user_file('token.json', scopes)
    doc_service = build('docs', 'v1', credentials=creds)
    
    document = doc_service.documents().get(documentId=FILE_ID).execute()
    
    # Check headers
    headers = document.get('headers', {})
    if headers:
        print("\n--- HEADERS FOUND ---")
        for h_id, h_data in headers.items():
            print(f"Header ID: {h_id}")
            for elem in h_data.get('content', []):
                if 'paragraph' in elem:
                    for p_elem in elem['paragraph']['elements']:
                        if 'textRun' in p_elem:
                            print(f"Text in header: '{p_elem['textRun'].get('content', '')}'")

    # Check footers
    footers = document.get('footers', {})
    if footers:
        print("\n--- FOOTERS FOUND ---")
        for f_id, f_data in footers.items():
            print(f"Footer ID: {f_id}")
            for elem in f_data.get('content', []):
                if 'paragraph' in elem:
                    for p_elem in elem['paragraph']['elements']:
                        if 'textRun' in p_elem:
                            print(f"Text in footer: '{p_elem['textRun'].get('content', '')}'")

if __name__ == '__main__':
    check_doc_structure()

import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

FILE_ID = "1p0nmiiZq7O22Clwq0dixYTUlTykBQTL73-LtF4LtKd0"

def clean_doc():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/documents'
    ]
    
    os.chdir('/Users/renancarvalho/Desktop/vicelos_sistema')
    creds = Credentials.from_authorized_user_file('token.json', scopes)
    doc_service = build('docs', 'v1', credentials=creds)
    
    # We will just try to delete all headers and footers to ensure nothing is pushing content down
    document = doc_service.documents().get(documentId=FILE_ID).execute()
    
    requests = []
    
    if document.get('headers'):
        for h_id in document['headers']:
            requests.append({'deleteHeader': {'headerId': h_id}})
            
    if document.get('footers'):
        for f_id in document['footers']:
            requests.append({'deleteFooter': {'footerId': f_id}})
            
    if requests:
        doc_service.documents().batchUpdate(documentId=FILE_ID, body={'requests': requests}).execute()
        print("Limpou os headers e footers do modelo com sucesso.")
    else:
        print("Nenhum header ou footer para remover.")

if __name__ == '__main__':
    clean_doc()

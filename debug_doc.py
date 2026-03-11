import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import io

# ID do modelo 05. Acordo Compensação
FILE_ID = "1p0nmiiZq7O22Clwq0dixYTUlTykBQTL73-LtF4LtKd0"

def check_pdf():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/documents'
    ]
    
    # Needs to match the env/token path inside the project
    os.chdir('/Users/renancarvalho/Desktop/vicelos_sistema')
    
    creds = Credentials.from_authorized_user_file('token.json', scopes)
    drive_service = build('drive', 'v3', credentials=creds)
    
    # Export it directly to see if Google's raw export is doing it
    request = drive_service.files().export_media(fileId=FILE_ID, mimeType='application/pdf')
    pdf_bytes = request.execute()
    
    with open('test_export_acordo.pdf', 'wb') as f:
        f.write(pdf_bytes)
        
    print("Raw PDF Exportado para test_export_acordo.pdf na pasta do projeto.")
    
    # Get document metadata to see what's actually in there
    doc_service = build('docs', 'v1', credentials=creds)
    document = doc_service.documents().get(documentId=FILE_ID).execute()
    
    content = document.get('body').get('content')
    print("Primeiros elementos de conteúdo do Documento:")
    for elem in content[:10]: # Look at the first 10 elements to see where "Guia 1" might be hiding
        if 'paragraph' in elem:
            for p_elem in elem.get('paragraph').get('elements'):
                if 'textRun' in p_elem:
                    text = p_elem.get('textRun').get('content').strip()
                    if text:
                        print(f"TEXTO ENCONTRADO: '{text}'")

if __name__ == '__main__':
    check_pdf()

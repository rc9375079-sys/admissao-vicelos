import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

# Scopes exigidos pelo ERP Vicelos
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents'
]

def generate_new_token():
    client_secret_path = 'client_secret.json'
    
    if not os.path.exists(client_secret_path):
        print(f"Erro: Arquivo '{client_secret_path}' não encontrado!")
        print("Certifique-se de estar na pasta '/Users/renancarvalho/Desktop/vicelos_sistema'")
        return

    # Inicia o fluxo de autenticação via navegador
    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    creds = flow.run_local_server(port=0)

    # Salva localmente
    with open('token.json', 'w') as token_file:
        token_file.write(creds.to_json())
    
    print("\n" + "="*50)
    print("✅ NOVO TOKEN GERADO COM SUCESSO!")
    print("="*50)
    print("\nCOPIE O CONTEÚDO ABAIXO PARA O 'GOOGLE_TOKEN_JSON' NOS SECRETS DO STREAMLIT CLOUD:\n")
    print(creds.to_json())
    print("\n" + "="*50)

if __name__ == "__main__":
    generate_new_token()

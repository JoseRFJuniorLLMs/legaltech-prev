from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

# CPF vinculado ao token de dev. Em produção, o JWT do gov.br carrega o CPF
# do cidadão como claim; o decode JWT extrai e retorna aqui.
_MOCK_TOKEN = "mock-gov-br-token-123"
_MOCK_CPF = ""  # Vazio = não forçar cruzamento no ambiente dev/mock.
# Para testar o guard de segurança, preencha com um CPF real e envie o token correto.

def verify_gov_br_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    # Mock validation — em produção: decodificar JWT assinado pela ICP-Brasil/gov.br
    if token != _MOCK_TOKEN:
        raise HTTPException(status_code=401, detail="Token Gov.br inválido ou expirado")

    # B6 Fix: retornar o campo 'cpf' extraído do token para que o guard em main.py funcione.
    # Em produção este CPF vem do claim 'sub' ou 'cpf' do JWT assinado pelo gov.br.
    return {"user_id": "12345", "auth_provider": "gov.br", "cpf": _MOCK_CPF}

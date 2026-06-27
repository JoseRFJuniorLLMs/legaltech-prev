from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def verify_gov_br_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    # Mock validation - em produção isso seria a validação do JWT assinado pelo Gov.br
    if token != "mock-gov-br-token-123":
        raise HTTPException(status_code=401, detail="Token Gov.br inválido ou expirado")
    
    return {"user_id": "12345", "auth_provider": "gov.br"}

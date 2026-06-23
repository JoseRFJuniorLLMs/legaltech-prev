import os
import re
from pathlib import Path
from fastapi import HTTPException, UploadFile

class LocalStorageService:
    def __init__(self, base_dir: str = "/tmp/legaltech_storage"):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_cpf(self, cpf: str) -> str:
        sanitized = re.sub(r"\\D", "", cpf)
        if len(sanitized) != 11:
            raise HTTPException(status_code=400, detail="CPF inválido. Deve conter 11 dígitos numéricos.")
        return sanitized

    def get_client_dir(self, cpf: str) -> Path:
        sanitized_cpf = self._sanitize_cpf(cpf)
        client_path = (self.base_dir / sanitized_cpf).resolve()
        
        # Guardião contra ataques de Path Traversal (../)
        if not str(client_path).startswith(str(self.base_dir)):
            raise HTTPException(status_code=403, detail="Violação de segurança detectada no Path.")
        
        client_path.mkdir(exist_ok=True)
        (client_path / "docs").mkdir(exist_ok=True)
        (client_path / "outputs").mkdir(exist_ok=True)
        return client_path

    async def save_uploaded_file(self, cpf: str, file: UploadFile, filename: str) -> Path:
        client_dir = self.get_client_dir(cpf)
        target_path = client_dir / "docs" / filename
        
        temp_path = target_path.with_suffix(".tmp")
        try:
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)
            os.replace(temp_path, target_path) # Escrita atômica segura
            return target_path
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise HTTPException(status_code=500, detail=f"Erro crítico de I/O atômico: {str(e)}")

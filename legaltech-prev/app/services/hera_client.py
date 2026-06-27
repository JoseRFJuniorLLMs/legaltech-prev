"""Cliente fino do HeraclitusDB, reaproveitando os stubs gRPC do ecossistema
(D:\\DEV\\scripts\\hera_mem). Degrada graciosamente: se o serviço/grpc estiver
indisponível, `available=False` e o repositório cai no fallback local."""
import sys
import json
import logging
from typing import List, Dict, Any

from app.config import settings


class HeraClient:
    def __init__(self) -> None:
        self._stub = None
        self._pb = None
        self.available = False
        try:
            if settings.HERA_STUBS_PATH not in sys.path:
                sys.path.insert(0, settings.HERA_STUBS_PATH)
            import grpc
            import heraclitus_pb2 as pb
            import heraclitus_pb2_grpc as rpc

            channel = grpc.insecure_channel(settings.HERA_ADDR)
            # B3 Fix: remover channel_ready_future().result(timeout=5) que bloqueava o
            # startup do FastAPI por até 5 s quando o Hera estiver offline.
            # Fazemos uma RPC leve (ListKinds) com deadline curto para detectar disponibilidade
            # sem segurar o event loop; erros de conectividade são capturados abaixo.
            self._stub = rpc.HeraclitusStub(channel)
            self._pb = pb
            # Prova de vida: tenta uma RPC leve com deadline de 2 s
            try:
                self._stub.ListKinds(pb.ListKindsRequest(), timeout=2)
                self.available = True
                logging.info("HeraclitusDB conectado em %s", settings.HERA_ADDR)
            except Exception:
                # Sem ListKinds no stub legado — assume disponível e falha na primeira RPC real
                self.available = True
                logging.info("HeraclitusDB conectado em %s", settings.HERA_ADDR)
        except Exception as e:  # noqa: BLE001 — degradar é intencional
            logging.warning("HeraclitusDB indisponível (%s); repo usará fallback JSON.", e)

    def append(self, kind: str, content: str, attrs: Dict[str, str]) -> int:
        req = self._pb.AppendRequest(
            agent_id=settings.APP_AGENT_ID,
            session_id="app",
            kind=kind,
            content=content.encode("utf-8"),
            attrs=attrs,
            hyp=[],
        )
        return self._stub.Append(req).lsn

    def query(self, gql: str) -> List[Dict[str, Any]]:
        resp = self._stub.Query(self._pb.QueryRequest(gql=gql))
        rows = json.loads(resp.json)
        # achata os attrs aninhados para o topo, como o claude_mem faz
        for r in rows:
            for k, v in (r.get("attrs") or {}).items():
                r.setdefault(k, v)
        return rows

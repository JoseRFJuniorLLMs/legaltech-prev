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
            grpc.channel_ready_future(channel).result(timeout=5)
            self._stub = rpc.HeraclitusStub(channel)
            self._pb = pb
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

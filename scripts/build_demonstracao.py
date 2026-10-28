"""Regrava o exemplo da demonstração (data/demonstracao/naturametrics.json).

    python scripts/build_demonstracao.py

Calcula o conglomerado de exemplo pelos mesmos serviços da interface
(services/demonstracao.py::instantaneo) e grava o pacote sem as camadas, com as
geometrias simplificadas, para a página /demonstracao abrir na hora. Rode de
novo quando uma coleção mudar (MapBiomas, Hansen) e faça commit do arquivo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from naturametrics.services import demonstracao  # noqa: E402


def main() -> int:
    dados = demonstracao.instantaneo()
    if dados["erros"]:
        print("Análises com erro, nada gravado:", dados["erros"])
        return 1
    alvo = demonstracao.ARQUIVO_EXEMPLO
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{alvo} — {alvo.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

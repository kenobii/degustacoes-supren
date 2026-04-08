#!/usr/bin/env python3
"""
sincronizar_portal.py — Supren Veg · Estrutura de Degustações
Lê as degustações agendadas no Notion e atualiza o portal.html com os links pré-preenchidos.
Após atualizar, faz upload de todos os arquivos para o Supabase Storage (acesso público).

Como usar:
  1. Abra o terminal nesta pasta
  2. Execute: python sincronizar_portal.py
  3. Pronto! O portal.html será atualizado e publicado online.

Requisitos:
  pip install requests python-dotenv
"""

import os
import re
import json
import sys
import logging
import requests

# Garante saída UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime
from urllib.parse import urlencode, quote
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# ── Logging ───────────────────────────────────────────────────────────────────
_log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(_log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(_log_dir, "sync.log"),
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger(__name__)

# ── Configuração — Notion ──────────────────────────────────────────────────────
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID  = os.environ["DATABASE_ID"]

# ── Configuração — Supabase ────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}


PORTAL_FILE = os.path.join(os.path.dirname(__file__), "portal.html")

# ── Funções auxiliares ────────────────────────────────────────────────────────

def get_text(prop, default=""):
    """Extrai texto de uma propriedade rich_text ou title."""
    try:
        items = prop.get("rich_text") or prop.get("title") or []
        return "".join(t.get("plain_text", "") for t in items).strip() or default
    except Exception:
        return default

def get_select(prop, default=""):
    """Extrai valor de uma propriedade select."""
    try:
        sel = prop.get("select")
        return sel.get("name", default) if sel else default
    except Exception:
        return default

def get_status(prop, default=""):
    """Extrai valor de uma propriedade status (tipo nativo do Notion)."""
    try:
        s = prop.get("status")
        return s.get("name", default) if s else default
    except Exception:
        return default

def get_multi_select(prop, default=""):
    """Extrai valores de uma propriedade multi_select, separados por vírgula."""
    try:
        items = prop.get("multi_select", [])
        names = [item.get("name", "") for item in items if item.get("name")]
        return ", ".join(names) if names else default
    except Exception:
        return default

def get_date(prop, default=""):
    """Extrai data de uma propriedade date."""
    try:
        d = prop.get("date")
        if not d:
            return default
        start = d.get("start", default)
        # Formata como DD/MM/YYYY para exibição
        if start and len(start) >= 10:
            parts = start[:10].split("-")
            if len(parts) == 3:
                return f"{parts[2]}/{parts[1]}/{parts[0]}"
        return start
    except Exception:
        return default

def get_date_iso(prop, default=""):
    """Extrai data no formato ISO (YYYY-MM-DD) para uso nos formulários."""
    try:
        d = prop.get("date")
        if not d:
            return default
        start = d.get("start", default)
        return start[:10] if start else default
    except Exception:
        return default

def get_horario(prop, default=""):
    """Extrai horário de uma propriedade date com datetime."""
    try:
        d = prop.get("date")
        if not d:
            return default
        start = d.get("start", "")
        if start and "T" in start:
            return start.split("T")[1][:5]
        return default
    except Exception:
        return default

def _query_notion(payload):
    """Executa query no Notion com paginação automática."""
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    results = []
    cursor = None
    try:
        while True:
            body = {**payload}
            if cursor:
                body["start_cursor"] = cursor
            resp = requests.post(url, headers=HEADERS, json=body, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            results += data.get("results", [])
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return results
    except requests.exceptions.ConnectionError:
        log.error("Sem conexão com a internet. Verifique sua rede.")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        log.error("Erro da API Notion: %s — %s", e.response.status_code, e.response.text[:200])
        sys.exit(1)
    except Exception as e:
        log.error("Erro inesperado na query Notion: %s", e)
        sys.exit(1)

def fetch_degustacoes():
    """Busca degustações ativas do Notion (exceto Finalizadas) — para o portal."""
    return _query_notion({
        "filter": {"property": "Status", "status": {"does_not_equal": "Finalizado"}},
        "sorts": [{"property": "Data", "direction": "ascending"}],
    })

def fetch_todas_degustacoes():
    """Busca TODAS as degustações do Notion incluindo Finalizadas — para o dashboard."""
    return _query_notion({
        "sorts": [{"property": "Data", "direction": "ascending"}],
    })

def parse_degustacao(page):
    """Converte uma página do Notion em dicionário de dados (schema: Degustação/Eventos)."""
    props = page.get("properties", {})

    # Campo Local pode incluir horário no formato "Nome do Local - 8h às 12h"
    local_raw = get_text(props.get("Local", {}))
    # Separa horário se estiver embutido no nome (ex: "Dedé Doces - 8h às 12h")
    horario_embutido = ""
    cliente_limpo = local_raw
    import re
    m = re.search(r'[-–]\s*(\d{1,2}h[^\d].*)', local_raw)
    if m:
        horario_embutido = m.group(1).strip()
        cliente_limpo = local_raw[:m.start()].strip()

    # Horário da data (se tiver datetime)
    horario_data = get_horario(props.get("Data", {}))
    horario = horario_data or horario_embutido

    # Degustador pode ser multi_select
    degustador = get_multi_select(props.get("Degustador", {}))

    # Tipo de evento
    tipo = get_multi_select(props.get("Tipo de evento", {}))

    # Status é tipo "status" nativo
    status_raw = get_status(props.get("Status", {}), "A confirmar")
    # Normaliza para os valores do portal
    status_map = {
        "A confirmar": "Agendado",
        "Confirmado":  "Confirmado",
        "Concluído":   "Concluído",
        "Finalizado":  "Finalizado",
    }
    status = status_map.get(status_raw, status_raw)

    return {
        "id":          page.get("id", ""),
        "cliente":     cliente_limpo,
        "data":        get_date_iso(props.get("Data", {})),
        "data_br":     get_date(props.get("Data", {})),
        "horario":     horario,
        "vendedor":    get_text(props.get("Vendedor", {})),
        "degustador":  degustador,
        "responsavel": get_text(props.get("Responsável", {})),
        "endereco":    get_text(props.get("Local 1", {})),
        "kit":         get_select(props.get("Kit", {}), "Kit 01"),
        "contato":     get_text(props.get("Contato no Cliente", {})),
        "status":      status,
        "tipo":        tipo,
    }

def _serialize(degustacoes):
    """Serializa lista de degustações para JSON (campos padronizados)."""
    return [
        {
            "id":          d["id"],
            "cliente":     d["cliente"],
            "data":        d["data"],
            "data_br":     d["data_br"],
            "horario":     d["horario"],
            "vendedor":    d["vendedor"],
            "degustador":  d["degustador"],
            "responsavel": d["responsavel"],
            "endereco":    d["endereco"],
            "kit":         d["kit"],
            "contato":     d["contato"],
            "status":      d["status"],
        }
        for d in degustacoes
    ]

def write_api_config_js():
    """Gera api_config.js com as variáveis da API do gestao-supren, lidas do .env."""
    pasta   = os.path.dirname(__file__)
    destino = os.path.join(pasta, "api_config.js")

    api_base = os.environ.get("FORMS_API_BASE", "")
    api_key  = os.environ.get("FORMS_API_KEY", "")

    conteudo = (
        f"// Supren Veg — gerado automaticamente por sincronizar_portal.py\n"
        f"// NÃO EDITE MANUALMENTE ESTE ARQUIVO\n\n"
        f"window.FORMS_API_BASE = {json.dumps(api_base)};\n"
        f"window.FORMS_API_KEY  = {json.dumps(api_key)};\n"
    )

    with open(destino, "w", encoding="utf-8") as f:
        f.write(conteudo)

    log.info("api_config.js gerado (base: %s)", api_base or "não configurado")


def write_dados_js(degustacoes, todas, last_update):
    """Gera dados.js com DEGUSTACOES, TODAS_DEGUSTACOES e ULTIMA_SINCRONIZACAO."""
    pasta = os.path.dirname(__file__)
    destino = os.path.join(pasta, "dados.js")

    ativas_json = json.dumps(_serialize(degustacoes), ensure_ascii=False, indent=2)
    todas_json  = json.dumps(_serialize(todas),       ensure_ascii=False, indent=2)

    conteudo = (
        f"// Supren Veg — gerado automaticamente por sincronizar_portal.py\n"
        f"// Última sincronização: {last_update}\n"
        f"// NÃO EDITE MANUALMENTE ESTE ARQUIVO\n\n"
        f"const ULTIMA_SINCRONIZACAO = {json.dumps(last_update)};\n\n"
        f"const DEGUSTACOES = {ativas_json};\n\n"
        f"const TODAS_DEGUSTACOES = {todas_json};\n"
    )

    with open(destino, "w", encoding="utf-8") as f:
        f.write(conteudo)

    log.info("dados.js gerado (%d ativas, %d total)", len(degustacoes), len(todas))

# ── Sync Supabase ─────────────────────────────────────────────────────────────

def sync_supabase(degustacoes):
    """Upsert de todas as degustações no Supabase (chave: notion_id)."""
    url = f"{SUPABASE_URL}/rest/v1/degustacoes?on_conflict=notion_id"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

    payload = [
        {
            "notion_id":   d["id"],
            "cliente":     d["cliente"],
            "data":        d["data"] or None,
            "horario":     d["horario"],
            "vendedor":    d["vendedor"],
            "degustador":  d["degustador"],
            "responsavel": d["responsavel"],
            "endereco":    d["endereco"],
            "kit":         d["kit"],
            "contato":     d["contato"],
            "status":      d["status"],
        }
        for d in degustacoes
    ]

    print("\n🗄️  Sincronizando com Supabase...")
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    if resp.status_code in (200, 201):
        print(f"   ✅ {len(payload)} registro(s) sincronizados")
    else:
        log.error("Supabase sync erro %s: %s", resp.status_code, resp.text[:120])

# ── Publicar no GitHub Pages ──────────────────────────────────────────────────

def publicar_github_pages(last_update):
    """Faz commit e push do portal.html para o GitHub Pages."""
    import subprocess
    pasta = os.path.dirname(__file__) or "."

    def run(cmd):
        result = subprocess.run(cmd, cwd=pasta, capture_output=True, text=True, shell=True)
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    print("\n☁️  Publicando no GitHub Pages...")

    code, out, err = run("git add portal.html dashboard.html dados.js && git add -f api_config.js")
    if code != 0:
        log.error("git add falhou: %s", err)
        return

    code, out, err = run(f'git diff --cached --quiet')
    if code == 0:
        print("   ℹ️  Sem alterações para publicar.")
        return

    code, out, err = run(f'git commit -m "chore: sincronização automática {last_update}"')
    if code != 0:
        log.error("git commit falhou: %s", err)
        return

    code, out, err = run("git push")
    if code != 0:
        log.error("git push falhou: %s", err)
        return

    print("   ✅ Publicado com sucesso!")
    print(f"\n🌐 Portal disponível em:")
    print(f"   https://supren-veg.github.io/degustacoes-supren/portal.html")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("🔄 Sincronizando portal com o Notion...")

    # Uma única query — filtra ativas em Python (evita segundo request)
    todas_pages = fetch_todas_degustacoes()
    todas       = [parse_degustacao(p) for p in todas_pages]
    degustacoes = [d for d in todas if d["status"] != "Finalizado"]

    print(f"   ✅ {len(degustacoes)} ativa(s) / {len(todas)} total")

    for d in degustacoes:
        nome   = d["cliente"] or "(sem nome)"
        data   = d["data_br"] or "sem data"
        status = d["status"]
        degu   = f" | {d['degustador']}" if d['degustador'] else ""
        print(f"      • {nome} — {data}{degu} [{status}]")

    last_update = datetime.now().strftime("%d/%m/%Y às %H:%M")
    write_dados_js(degustacoes, todas, last_update)
    write_api_config_js()

    print(f"\n✅ Portal atualizado com sucesso!")
    print(f"   Última atualização: {last_update}")

    sync_supabase(degustacoes)
    publicar_github_pages(last_update)

if __name__ == "__main__":
    main()

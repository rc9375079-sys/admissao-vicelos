import os
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor


def _conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "vicelos_erp"),
        user=os.getenv("DB_USER", "vicelos"),
        password=os.getenv("DB_PASSWORD", "vicelos"),
    )


def _to_decimal(raw: Optional[str]) -> Optional[Decimal]:
    if raw is None:
        return None
    try:
        txt = str(raw).replace("R$", "").strip()
        txt = txt.replace(".", "").replace(",", ".")
        return Decimal(txt)
    except (InvalidOperation, ValueError):
        return None


def upsert_entidade(nome: str, cpf: str, tipo: str = "funcionario") -> str:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO entidades (tipo, nome, cpf_cnpj)
            VALUES (%s, %s, %s)
            ON CONFLICT (cpf_cnpj) DO UPDATE SET nome = EXCLUDED.nome
            RETURNING id;
            """,
            (tipo, nome, cpf),
        )
        return cur.fetchone()[0]


def get_or_create_cargo(nome: str, cbo: Optional[str], salario_base: Optional[Decimal]) -> Optional[str]:
    nome_clean = nome.strip() if nome else "Cargo não informado"
    with _conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id FROM cargos
            WHERE nome = %s AND (cbo IS NOT DISTINCT FROM %s);
            """,
            (nome_clean, cbo),
        )
        row = cur.fetchone()
        if row:
            return row["id"]

        cur.execute(
            """
            INSERT INTO cargos (id, nome, cbo, salario_base)
            VALUES (gen_random_uuid(), %s, %s, %s)
            RETURNING id;
            """,
            (nome_clean, cbo, salario_base),
        )
        return cur.fetchone()["id"]


def upsert_funcionario(entidade_id: str, cargo_id: Optional[str], data_admissao: Optional[date], salario_atual: Optional[Decimal], ctps_numero: Optional[str]) -> str:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO funcionarios (id, entidade_id, cargo_id, data_admissao, salario_atual, ctps_numero)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s)
            ON CONFLICT (entidade_id) DO UPDATE
            SET cargo_id = EXCLUDED.cargo_id,
                data_admissao = COALESCE(EXCLUDED.data_admissao, funcionarios.data_admissao),
                salario_atual = COALESCE(EXCLUDED.salario_atual, funcionarios.salario_atual),
                ctps_numero = COALESCE(EXCLUDED.ctps_numero, funcionarios.ctps_numero)
            RETURNING id;
            """,
            (entidade_id, cargo_id, data_admissao, salario_atual, ctps_numero),
        )
        return cur.fetchone()[0]


def save_admission_record(dados: dict) -> Optional[str]:
    """
    Recebe o dicionário do formulário e garante persistência mínima:
    - entidades (tipo=funcionario)
    - cargos (opcional)
    - funcionarios (FK entidade/cargo)
    """
    nome = (dados.get("nome") or dados.get("Nome Completo") or "").strip()
    cpf = (dados.get("cpf") or dados.get("CPF") or "").strip()
    if not nome or not cpf:
        return None

    cargo_nome = dados.get("cargo") or dados.get("Cargo") or "Cargo não informado"
    cbo = dados.get("cbo") or dados.get("CBO")
    salario = _to_decimal(dados.get("salario") or dados.get("salario_base") or dados.get("Salario"))
    ctps = dados.get("CTPS Numero") or dados.get("ctps_num") or dados.get("ctps")

    data_inicio_txt = dados.get("data_inicio") or dados.get("Data de Admissao") or dados.get("data_admissao")
    data_inicio = None
    if data_inicio_txt:
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                data_inicio = datetime.strptime(data_inicio_txt, fmt).date()
                break
            except Exception:
                continue

    entidade_id = upsert_entidade(nome, cpf, tipo="funcionario")
    cargo_id = get_or_create_cargo(cargo_nome, cbo, salario)
    return upsert_funcionario(entidade_id, cargo_id, data_inicio, salario, ctps)

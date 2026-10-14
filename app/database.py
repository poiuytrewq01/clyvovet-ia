"""Banco de dados SQLite do CLYVO VET: criação das tabelas e dados de exemplo."""
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = os.getenv("CLYVO_DB", str(Path(__file__).resolve().parent.parent / "clyvovet.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS tutores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    telefone TEXT,
    email TEXT
);
CREATE TABLE IF NOT EXISTS pets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tutor_id INTEGER NOT NULL REFERENCES tutores(id),
    nome TEXT NOT NULL,
    especie TEXT NOT NULL,          -- cachorro | gato
    raca TEXT,
    data_nascimento TEXT NOT NULL,  -- AAAA-MM-DD
    peso_kg REAL
);
CREATE TABLE IF NOT EXISTS vacinas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    nome TEXT NOT NULL,
    data_aplicacao TEXT,
    data_vencimento TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS consultas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    data TEXT NOT NULL,
    motivo TEXT NOT NULL,
    veterinario TEXT,
    observacoes TEXT,
    retorno_em TEXT,                -- data prevista de retorno (pode ser nula)
    retorno_realizado INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS medicamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    nome TEXT NOT NULL,
    dosagem TEXT,
    frequencia TEXT,
    inicio TEXT,
    fim TEXT
);
CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    data TEXT NOT NULL,
    tipo TEXT NOT NULL              -- passeio | alimentacao | peso | remedio ...
);
CREATE TABLE IF NOT EXISTS mensagens_ia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id INTEGER NOT NULL REFERENCES pets(id),
    tipo TEXT NOT NULL,             -- lembrete | chat
    entrada TEXT,
    resposta TEXT NOT NULL,
    urgencia TEXT,
    origem TEXT NOT NULL,           -- gemini | simulado
    criado_em TEXT DEFAULT (datetime('now', 'localtime'))
);
"""


def conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _d(dias: int) -> str:
    """Data relativa a hoje, pra demo sempre ter pendências atuais."""
    return (date.today() + timedelta(days=dias)).isoformat()


def popular_exemplos(conn: sqlite3.Connection) -> None:
    """Cria tutores e pets cobrindo os cenários da demonstração."""
    c = conn.cursor()
    c.executemany(
        "INSERT INTO tutores (nome, telefone, email) VALUES (?, ?, ?)",
        [
            ("Ana Souza", "(11) 99999-0001", "ana@exemplo.com"),
            ("Carlos Lima", "(11) 99999-0002", "carlos@exemplo.com"),
            ("Juliana Reis", "(11) 99999-0003", "juliana@exemplo.com"),
        ],
    )
    pets = [
        # tutor, nome, especie, raca, nascimento, peso
        (1, "Rex", "cachorro", "Labrador", _d(-2 * 365 - 31), 28.0),   # adulto, vacina vencendo
        (2, "Mia", "gato", "Siamês", _d(-12 * 365 - 10), 4.1),              # idosa, vacina muito atrasada, tutor sumido
        (3, "Thor", "cachorro", "Golden Retriever", _d(-95), 9.5),     # filhote, dose atrasada
        (1, "Luna", "gato", "SRD", _d(-5 * 365 - 10), 4.5),                 # tudo em dia
        (3, "Bob", "cachorro", "Beagle", _d(-8 * 365 - 10), 13.2),          # retorno de consulta pendente
    ]
    c.executemany(
        "INSERT INTO pets (tutor_id, nome, especie, raca, data_nascimento, peso_kg) VALUES (?, ?, ?, ?, ?, ?)",
        pets,
    )
    c.executemany(
        "INSERT INTO vacinas (pet_id, nome, data_aplicacao, data_vencimento) VALUES (?, ?, ?, ?)",
        [
            (1, "Antirrábica", _d(-360), _d(5)),
            (1, "V10", _d(-200), _d(165)),
            (2, "Antirrábica", _d(-410), _d(-45)),
            (2, "V4 (quádrupla felina)", _d(-380), _d(-15)),
            (3, "V10 - 2ª dose (reforço)", None, _d(-19)),   # 1ª dose há 40 dias, reforço era pra 21 dias depois
            (4, "Antirrábica", _d(-100), _d(265)),
            (4, "V4 (quádrupla felina)", _d(-100), _d(265)),
            (5, "Antirrábica", _d(-300), _d(65)),
        ],
    )
    c.executemany(
        "INSERT INTO consultas (pet_id, data, motivo, veterinario, observacoes, retorno_em) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, _d(-60), "Check-up anual", "Dra. Paula", "Saudável", None),
            (2, _d(-400), "Check-up geriátrico", "Dr. Marcos", "Função renal no limite, repetir exame", _d(-220)),
            (3, _d(-40), "Primeira consulta + 1ª dose V10", "Dra. Paula", "Iniciar protocolo vacinal", None),
            (5, _d(-25), "Otite no ouvido esquerdo", "Dr. Marcos", "Limpeza + antibiótico por 14 dias", _d(-4)),
        ],
    )
    c.executemany(
        "INSERT INTO medicamentos (pet_id, nome, dosagem, frequencia, inicio, fim) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (5, "Otomax (gotas)", "4 gotas", "2x ao dia", _d(-25), _d(-11)),
            (2, "Ração renal", "60 g", "2x ao dia", _d(-400), None),
        ],
    )
    c.executemany(
        "INSERT INTO checkins (pet_id, data, tipo) VALUES (?, ?, ?)",
        [
            (1, _d(-1), "passeio"), (1, _d(-2), "alimentacao"), (1, _d(-3), "passeio"),
            (2, _d(-70), "alimentacao"),
            (3, _d(-2), "peso"), (3, _d(-6), "passeio"),
            (4, _d(0), "alimentacao"),
            (5, _d(-9), "remedio"),
        ],
    )
    conn.commit()


def inicializar(recriar: bool = False) -> None:
    if recriar and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = conectar()
    conn.executescript(SCHEMA)
    vazio = conn.execute("SELECT COUNT(*) FROM pets").fetchone()[0] == 0
    if vazio:
        popular_exemplos(conn)
    conn.close()


if __name__ == "__main__":
    inicializar(recriar=True)
    print(f"Banco recriado com dados de exemplo em {DB_PATH}")

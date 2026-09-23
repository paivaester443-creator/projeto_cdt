import sqlite3
import json
import os

from werkzeug.security import generate_password_hash, check_password_hash


# ============================================================
# CONFIGURAÇÃO
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")


# ============================================================
# CONEXÃO COM O BANCO
# ============================================================

def conectar():
    conexao = sqlite3.connect(DATABASE)
    conexao.row_factory = sqlite3.Row
    return conexao


# ============================================================
# CRIAÇÃO DAS TABELAS
# ============================================================

def inicializar_banco():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            cidade TEXT,
            clima TEXT,
            temperatura REAL,
            humor TEXT,
            artista TEXT,
            spotify_url TEXT,
            criada_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)

    conexao.commit()
    conexao.close()


# ============================================================
# CRIAÇÃO DO USUÁRIO ROOT
# ============================================================

def criar_usuario_root():
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute(
        "SELECT id FROM usuarios WHERE usuario = ?",
        ("root",)
    )

    usuario_existente = cursor.fetchone()

    if usuario_existente is None:
        senha_hash = generate_password_hash("root")

        cursor.execute(
            """
            INSERT INTO usuarios (usuario, senha)
            VALUES (?, ?)
            """,
            ("root", senha_hash)
        )

        conexao.commit()

        print("Usuário root criado.")
        print("Usuário: root")
        print("Senha: root")

    conexao.close()


# ============================================================
# CRIAÇÃO DE USUÁRIO
# ============================================================

def criar_usuario(usuario, senha):
    usuario = usuario.strip()

    if not usuario or not senha:
        return False, "Preencha todos os campos."

    if len(usuario) < 3:
        return False, "O usuário precisa ter pelo menos 3 caracteres."

    if len(senha) < 4:
        return False, "A senha precisa ter pelo menos 4 caracteres."

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute(
        "SELECT id FROM usuarios WHERE usuario = ?",
        (usuario,)
    )

    existente = cursor.fetchone()

    if existente:
        conexao.close()
        return False, "Esse usuário já existe."

    senha_hash = generate_password_hash(senha)

    cursor.execute(
        """
        INSERT INTO usuarios (usuario, senha)
        VALUES (?, ?)
        """,
        (usuario, senha_hash)
    )

    conexao.commit()
    conexao.close()

    return True, "Usuário criado com sucesso."


# ============================================================
# AUTENTICAÇÃO
# ============================================================

def autenticar_usuario(usuario, senha):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute(
        """
        SELECT *
        FROM usuarios
        WHERE usuario = ?
        """,
        (usuario.strip(),)
    )

    usuario_encontrado = cursor.fetchone()

    conexao.close()

    if usuario_encontrado is None:
        return None

    if check_password_hash(usuario_encontrado["senha"], senha):
        return dict(usuario_encontrado)

    return None


# ============================================================
# BUSCAR USUÁRIO PELO ID
# ============================================================

def buscar_usuario_por_id(usuario_id):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute(
        """
        SELECT *
        FROM usuarios
        WHERE id = ?
        """,
        (usuario_id,)
    )

    usuario = cursor.fetchone()

    conexao.close()

    if usuario:
        return dict(usuario)

    return None


# ============================================================
# SALVAR PLAYLIST
# ============================================================

def salvar_playlist(
    usuario_id,
    nome,
    cidade,
    clima,
    temperatura,
    humor,
    artista,
    spotify_url
):
    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute(
        """
        INSERT INTO playlists (
            usuario_id,
            nome,
            cidade,
            clima,
            temperatura,
            humor,
            artista,
            spotify_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            usuario_id,
            nome,
            cidade,
            clima,
            temperatura,
            humor,
            artista,
            spotify_url
        )
    )

    conexao.commit()
    conexao.close()


# ============================================================
# EXPORTAÇÃO DO BANCO PARA JSON
# ============================================================

def exportar_banco_json(caminho_arquivo=None):
    if caminho_arquivo is None:
        caminho_arquivo = os.path.join(
            BASE_DIR,
            "sintonia_database.json"
        )

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name NOT LIKE 'sqlite_%'
    """)

    tabelas = cursor.fetchall()

    banco = {}

    for tabela in tabelas:
        nome_tabela = tabela["name"]

        cursor.execute(
            f'SELECT * FROM "{nome_tabela}"'
        )

        registros = cursor.fetchall()

        banco[nome_tabela] = [
            dict(registro)
            for registro in registros
        ]

    conexao.close()

    with open(
        caminho_arquivo,
        "w",
        encoding="utf-8"
    ) as arquivo:
        json.dump(
            banco,
            arquivo,
            ensure_ascii=False,
            indent=4
        )

    return caminho_arquivo


# ============================================================
# INICIALIZAÇÃO
# ============================================================

def preparar_banco():
    inicializar_banco()
    criar_usuario_root()


if __name__ == "__main__":
    preparar_banco()

    print()
    print("=" * 50)
    print("BANCO DE DADOS DO SINTONIA")
    print("=" * 50)
    print(f"Banco: {DATABASE}")
    print("Usuário master: root")
    print("Senha master: root")
    print("=" * 50)
import sqlite3
import os

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE = os.path.join(
    BASE_DIR,
    "database.db"
)


def conectar():

    return sqlite3.connect(
        DATABASE
    )


def criar_tabelas():

    conexao = conectar()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            cidade TEXT,
            humor TEXT,
            artista TEXT,
            clima TEXT,
            temperatura REAL,
            playlist TEXT,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conexao.commit()
    conexao.close()


if __name__ == "__main__":

    criar_tabelas()

    print("Banco de dados criado com sucesso.")
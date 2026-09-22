import os
import sqlite3
import json
import unicodedata

import requests
import spotipy

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    send_file
)

from spotipy.oauth2 import SpotifyOAuth
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv


# =========================================================
# CONFIGURAÇÃO
# =========================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "chave-temporaria-sintonia"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(BASE_DIR, "database.db")

SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

SPOTIPY_REDIRECT_URI = "http://127.0.0.1:8888/callback"

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

SCOPE = (
    "playlist-modify-public "
    "playlist-modify-private "
    "user-read-private"
)


# =========================================================
# BANCO DE DADOS
# =========================================================

def conectar_banco():
    conexao = sqlite3.connect(DATABASE)
    conexao.row_factory = sqlite3.Row
    return conexao


def criar_banco():
    conexao = conectar_banco()
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

    # Usuário root pré-cadastrado
    cursor.execute(
        "SELECT id FROM usuarios WHERE usuario = ?",
        ("root",)
    )

    root_existe = cursor.fetchone()

    if not root_existe:
        senha_root = generate_password_hash("root")

        cursor.execute(
            """
            INSERT INTO usuarios (usuario, senha)
            VALUES (?, ?)
            """,
            ("root", senha_root)
        )

    conexao.commit()
    conexao.close()


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def remover_acentos(texto):
    if not texto:
        return ""

    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caractere) != "Mn"
    )


def obter_clima_por_cidade(cidade):
    """
    Consulta o clima usando o nome da cidade.
    """

    if not WEATHER_API_KEY:
        return {
            "temp": 22.0,
            "tag": "Ensolarado",
            "desc": "Clima indisponível"
        }

    if not cidade:
        cidade = "São Paulo"

    url = "https://api.openweathermap.org/data/2.5/weather"

    parametros = {
        "q": cidade,
        "appid": WEATHER_API_KEY,
        "units": "metric",
        "lang": "pt_br"
    }

    try:
        resposta = requests.get(
            url,
            params=parametros,
            timeout=10
        )

        resposta.raise_for_status()

        dados = resposta.json()

        condicao = dados["weather"][0]["main"]

        if condicao in ["Rain", "Drizzle", "Thunderstorm"]:
            tag = "Chuvoso"

        elif condicao == "Clouds":
            tag = "Nublado"

        elif condicao in ["Snow"]:
            tag = "Nevando"

        else:
            tag = "Ensolarado"

        return {
            "temp": dados["main"]["temp"],
            "tag": tag,
            "desc": dados["weather"][0]["description"]
        }

    except Exception as erro:

        print("Erro ao obter clima:", erro)

        return {
            "temp": 22.0,
            "tag": "Ensolarado",
            "desc": "Clima indisponível"
        }


def obter_clima_por_localizacao(latitude, longitude):
    """
    Consulta o clima diretamente pelas coordenadas.
    Isso evita depender do nome da cidade.
    """

    if not WEATHER_API_KEY:
        return {
            "temp": 22.0,
            "tag": "Ensolarado",
            "desc": "Clima indisponível"
        }

    url = "https://api.openweathermap.org/data/2.5/weather"

    parametros = {
        "lat": latitude,
        "lon": longitude,
        "appid": WEATHER_API_KEY,
        "units": "metric",
        "lang": "pt_br"
    }

    try:

        resposta = requests.get(
            url,
            params=parametros,
            timeout=10
        )

        resposta.raise_for_status()

        dados = resposta.json()

        condicao = dados["weather"][0]["main"]

        if condicao in ["Rain", "Drizzle", "Thunderstorm"]:
            tag = "Chuvoso"

        elif condicao == "Clouds":
            tag = "Nublado"

        elif condicao == "Snow":
            tag = "Nevando"

        else:
            tag = "Ensolarado"

        return {
            "temp": dados["main"]["temp"],
            "tag": tag,
            "desc": dados["weather"][0]["description"],
            "cidade": dados.get("name", "")
        }

    except Exception as erro:

        print("Erro ao obter clima pela localização:", erro)

        return {
            "temp": 22.0,
            "tag": "Ensolarado",
            "desc": "Clima indisponível",
            "cidade": ""
        }


# =========================================================
# SPOTIFY
# =========================================================

def criar_autenticador_spotify():

    return SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        show_dialog=True
    )


def obter_spotify_cliente():

    token_info = session.get("token_info")

    if not token_info:
        return None

    try:

        sp_oauth = criar_autenticador_spotify()

        if sp_oauth.is_token_expired(token_info):

            refresh_token = token_info.get("refresh_token")

            if not refresh_token:
                session.pop("token_info", None)
                return None

            token_info = sp_oauth.refresh_access_token(
                refresh_token
            )

            session["token_info"] = token_info

        return spotipy.Spotify(
            auth=token_info["access_token"]
        )

    except Exception as erro:

        print("Erro ao obter cliente Spotify:", erro)

        session.pop("token_info", None)

        return None


# =========================================================
# LOGIN DO SINTONIA
# =========================================================

@app.route("/")
def inicio():

    if session.get("usuario"):
        return redirect(url_for("spotify_login"))

    return render_template("login.html")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():

    erro = None

    if request.method == "POST":

        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        confirmar = request.form.get("confirmar_senha", "")

        if not usuario or not senha:

            erro = "Preencha todos os campos."

        elif len(usuario) < 3:

            erro = "O usuário precisa ter pelo menos 3 caracteres."

        elif senha != confirmar:

            erro = "As senhas não coincidem."

        else:

            conexao = conectar_banco()
            cursor = conexao.cursor()

            cursor.execute(
                "SELECT id FROM usuarios WHERE usuario = ?",
                (usuario,)
            )

            usuario_existe = cursor.fetchone()

            if usuario_existe:

                erro = "Esse usuário já existe."

            else:

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

                session["usuario"] = usuario

                return redirect(
                    url_for("spotify_login")
                )

            conexao.close()

    return render_template(
        "cadastro.html",
        erro=erro
    )


@app.route("/entrar", methods=["POST"])
def entrar():

    usuario = request.form.get("usuario", "").strip()
    senha = request.form.get("senha", "")

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
        """
        SELECT *
        FROM usuarios
        WHERE usuario = ?
        """,
        (usuario,)
    )

    usuario_banco = cursor.fetchone()

    conexao.close()

    if not usuario_banco:

        return render_template(
            "login.html",
            erro="Usuário ou senha incorretos."
        )

    if not check_password_hash(
        usuario_banco["senha"],
        senha
    ):

        return render_template(
            "login.html",
            erro="Usuário ou senha incorretos."
        )

    session["usuario"] = usuario

    return redirect(
        url_for("spotify_login")
    )


# =========================================================
# LOGIN SPOTIFY
# =========================================================

@app.route("/spotify-login")
def spotify_login():

    if not session.get("usuario"):
        return redirect(url_for("inicio"))

    sp = obter_spotify_cliente()

    if sp:
        return redirect(url_for("dashboard"))

    sp_oauth = criar_autenticador_spotify()

    auth_url = sp_oauth.get_authorize_url()

    return redirect(auth_url)


@app.route("/callback")
def callback():

    if not session.get("usuario"):
        return redirect(url_for("inicio"))

    erro = request.args.get("error")

    if erro:

        return f"""
        <h2>Erro ao conectar com o Spotify</h2>
        <p>{erro}</p>
        <p><a href="/">Voltar</a></p>
        """

    codigo = request.args.get("code")

    if not codigo:

        return """
        <h2>Erro ao conectar com o Spotify</h2>
        <p>Código de autorização não recebido.</p>
        <p><a href="/">Voltar</a></p>
        """

    try:

        sp_oauth = criar_autenticador_spotify()

        token_info = sp_oauth.get_access_token(
            codigo,
            as_dict=True
        )

        session["token_info"] = token_info

        return redirect(
            url_for("dashboard")
        )

    except Exception as erro:

        print("Erro Spotify:", erro)

        return f"""
        <h2>Erro ao conectar com o Spotify</h2>
        <p>{erro}</p>
        <p><a href="/">Voltar</a></p>
        """


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if not session.get("usuario"):
        return redirect(url_for("inicio"))

    sp = obter_spotify_cliente()

    if not sp:
        return redirect(
            url_for("spotify_login")
        )

    return render_template(
        "dashboard.html",
        usuario=session.get("usuario")
    )


# =========================================================
# CLIMA POR LOCALIZAÇÃO
# =========================================================

@app.route("/clima-localizacao", methods=["POST"])
def clima_localizacao():

    if not session.get("usuario"):
        return {
            "erro": "Usuário não autenticado."
        }, 401

    dados = request.get_json()

    if not dados:
        return {
            "erro": "Localização não recebida."
        }, 400

    latitude = dados.get("latitude")
    longitude = dados.get("longitude")

    if latitude is None or longitude is None:

        return {
            "erro": "Latitude ou longitude não informada."
        }, 400

    clima = obter_clima_por_localizacao(
        latitude,
        longitude
    )

    return clima


# =========================================================
# CRIAR PLAYLIST
# =========================================================

@app.route("/gerar", methods=["POST"])
def gerar():

    if not session.get("usuario"):
        return redirect(url_for("inicio"))

    sp = obter_spotify_cliente()

    if not sp:
        return redirect(
            url_for("spotify_login")
        )

    cidade = request.form.get(
        "cidade",
        ""
    ).strip()

    humor = request.form.get(
        "humor",
        "Feliz"
    ).strip()

    artista = request.form.get(
        "artista",
        ""
    ).strip()

    latitude = request.form.get(
        "latitude",
        ""
    ).strip()

    longitude = request.form.get(
        "longitude",
        ""
    ).strip()

    # -----------------------------------------------------
    # O clima será obtido pela localização se disponível.
    # Caso contrário, usa a cidade digitada.
    # -----------------------------------------------------

    if latitude and longitude:

        try:

            clima = obter_clima_por_localizacao(
                float(latitude),
                float(longitude)
            )

            if clima.get("cidade"):
                cidade = clima["cidade"]

        except Exception as erro:

            print(
                "Erro ao usar localização:",
                erro
            )

            clima = obter_clima_por_cidade(
                cidade
            )

    else:

        clima = obter_clima_por_cidade(
            cidade
        )

    clima_tag = clima["tag"]

    humor_busca = remover_acentos(
        humor
    )

    clima_busca = remover_acentos(
        clima_tag
    )

    # -----------------------------------------------------
    # Busca no Spotify
    # -----------------------------------------------------

    if artista:

        termo_busca = (
            f"{remover_acentos(artista)} "
            f"{humor_busca}"
        )

    else:

        termo_busca = (
            f"{humor_busca} "
            f"{clima_busca}"
        )

    print()
    print("=" * 50)
    print("SINTONIA")
    print("=" * 50)
    print("Usuário:", session.get("usuario"))
    print("Cidade:", cidade)
    print("Humor:", humor)
    print("Artista:", artista)
    print("Clima:", clima_tag)
    print("Temperatura:", clima["temp"])
    print("Busca:", termo_busca)
    print("=" * 50)

    tracks_uris = []

    try:

        resultados = sp.search(
            q=termo_busca,
            type="track",
            limit=10
        )

        tracks_uris = [
            item["uri"]
            for item in resultados["tracks"]["items"]
        ]

    except Exception as erro:

        print(
            "Erro na busca principal:",
            erro
        )

    # Segunda tentativa
    if not tracks_uris:

        try:

            resultados = sp.search(
                q=humor_busca,
                type="track",
                limit=10
            )

            tracks_uris = [
                item["uri"]
                for item in resultados["tracks"]["items"]
            ]

        except Exception as erro:

            print(
                "Erro na segunda busca:",
                erro
            )

    # -----------------------------------------------------
    # Nome da playlist
    # -----------------------------------------------------

    nome_playlist = (
        f"Sintonia | "
        f"{humor} | "
        f"{clima_tag}"
    )

    if cidade:
        nome_playlist += f" | {cidade}"

    if artista:
        nome_playlist += f" | {artista}"

    # -----------------------------------------------------
    # Criação da playlist
    # -----------------------------------------------------

    try:

        playlist = sp.current_user_playlist_create(
            name=nome_playlist,
            public=True,
            description=(
                f"Playlist criada pelo Sintonia para "
                f"{cidade or 'sua localização'}. "
                f"Clima: {clima['desc']}, "
                f"{clima['temp']:.1f}°C."
            )
        )

    except Exception as erro:

        print(
            "Erro ao criar playlist:",
            erro
        )

        return f"""
        <h2>Não foi possível criar a playlist.</h2>
        <p>{erro}</p>
        <p><a href="/dashboard">Voltar</a></p>
        """

    # -----------------------------------------------------
    # Adicionar músicas
    # -----------------------------------------------------

    if tracks_uris:

        try:

            sp.playlist_add_items(
                playlist_id=playlist["id"],
                items=tracks_uris
            )

        except Exception as erro:

            print(
                "Erro ao adicionar músicas:",
                erro
            )

    # -----------------------------------------------------
    # Salvar no banco
    # -----------------------------------------------------

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
        """
        INSERT INTO playlists
        (
            usuario,
            cidade,
            humor,
            artista,
            clima,
            temperatura,
            playlist
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session.get("usuario"),
            cidade,
            humor,
            artista,
            clima_tag,
            clima["temp"],
            nome_playlist
        )
    )

    conexao.commit()
    conexao.close()

    # -----------------------------------------------------
    # Abrir playlist
    # -----------------------------------------------------

    url_spotify = (
        playlist["external_urls"]["spotify"]
    )

    return redirect(url_spotify)


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("inicio")
    )


# =========================================================
# ÁREA ROOT
# =========================================================

@app.route("/root", methods=["GET", "POST"])
def root_login():

    if session.get("root_authenticated"):
        return redirect(
            url_for("root_panel")
        )

    erro = None

    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        senha = request.form.get(
            "senha",
            ""
        )

        conexao = conectar_banco()
        cursor = conexao.cursor()

        cursor.execute(
            """
            SELECT *
            FROM usuarios
            WHERE usuario = ?
            """,
            (usuario,)
        )

        usuario_banco = cursor.fetchone()

        conexao.close()

        if (
            usuario_banco
            and usuario == "root"
            and check_password_hash(
                usuario_banco["senha"],
                senha
            )
        ):

            session["root_authenticated"] = True

            return redirect(
                url_for("root_panel")
            )

        erro = "Usuário ou senha incorretos."

    return render_template(
        "root_login.html",
        erro=erro
    )


@app.route("/root/painel")
def root_panel():

    if not session.get(
        "root_authenticated"
    ):

        return redirect(
            url_for("root_login")
        )

    return render_template(
        "root_panel.html"
    )


@app.route("/root/exportar")
def root_exportar():

    if not session.get(
        "root_authenticated"
    ):

        return redirect(
            url_for("root_login")
        )

    arquivo_json = os.path.join(
        BASE_DIR,
        "sintonia_database.json"
    )

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name NOT LIKE 'sqlite_%'
        """
    )

    tabelas = cursor.fetchall()

    dados = {}

    for tabela in tabelas:

        nome_tabela = tabela["name"]

        cursor.execute(
            f'SELECT * FROM "{nome_tabela}"'
        )

        registros = cursor.fetchall()

        dados[nome_tabela] = [
            dict(registro)
            for registro in registros
        ]

    conexao.close()

    with open(
        arquivo_json,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            dados,
            arquivo,
            ensure_ascii=False,
            indent=4
        )

    return send_file(
        arquivo_json,
        as_attachment=True,
        download_name="sintonia_database.json"
    )


@app.route("/root/logout")
def root_logout():

    session.pop(
        "root_authenticated",
        None
    )

    return redirect(
        url_for("root_login")
    )


# =========================================================
# INICIALIZAÇÃO
# =========================================================

criar_banco()


if __name__ == "__main__":

    print()
    print("=" * 50)
    print("SINTONIA")
    print("=" * 50)
    print()
    print(
        "Aplicação: "
        "http://127.0.0.1:8888"
    )
    print()
    print(
        "Acesso Root: "
        "http://127.0.0.1:8888/root"
    )
    print()
    print("Usuário Root: root")
    print("Senha Root: root")
    print()
    print("=" * 50)
    print()

    app.run(
        debug=True,
        port=8888
    )
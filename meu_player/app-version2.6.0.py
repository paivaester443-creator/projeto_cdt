import os
import sqlite3
import unicodedata
import requests

from flask import (
    Flask,
    redirect,
    request,
    render_template,
    session,
    url_for
)

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv


# =========================================================
# CONFIGURAÇÃO
# =========================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "chave-secreta-do-sintonia"
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
    return sqlite3.connect(DATABASE)


def criar_banco():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'usuario'
        )
    """)

    # Cria o usuário root automaticamente
    cursor.execute("""
        SELECT id
        FROM usuarios
        WHERE usuario = ?
    """, ("root",))

    root_existente = cursor.fetchone()

    if not root_existente:
        cursor.execute("""
            INSERT INTO usuarios (usuario, senha, tipo)
            VALUES (?, ?, ?)
        """, ("root", "root", "master"))

    conexao.commit()
    conexao.close()


def verificar_usuario(usuario, senha):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, usuario, tipo
        FROM usuarios
        WHERE usuario = ?
        AND senha = ?
    """, (usuario, senha))

    resultado = cursor.fetchone()

    conexao.close()

    return resultado


def cadastrar_usuario(usuario, senha):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    try:
        cursor.execute("""
            INSERT INTO usuarios (usuario, senha, tipo)
            VALUES (?, ?, ?)
        """, (usuario, senha, "usuario"))

        conexao.commit()
        sucesso = True

    except sqlite3.IntegrityError:
        sucesso = False

    conexao.close()

    return sucesso


# =========================================================
# FUNÇÃO PARA REMOVER ACENTOS
# =========================================================

def remover_acentos(texto):
    if not texto:
        return ""

    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caractere) != "Mn"
    )


# =========================================================
# CLIMA
# =========================================================

def obter_clima(cidade):
    if not cidade:
        cidade = "São Paulo"

    if not WEATHER_API_KEY:
        print("ERRO: WEATHER_API_KEY não encontrada no .env")

        return {
            "temp": None,
            "tag": "Indisponível",
            "desc": "Chave da API do clima não configurada."
        }

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

        print()
        print("===================================")
        print("OPENWEATHER")
        print("===================================")
        print("Cidade pesquisada:", cidade)
        print("Status:", resposta.status_code)

        resposta.raise_for_status()

        dados = resposta.json()

        print("Cidade encontrada:", dados.get("name"))
        print("Temperatura:", dados["main"]["temp"])
        print("Descrição:", dados["weather"][0]["description"])
        print("===================================")

        condicao = dados["weather"][0]["main"]

        if condicao in [
            "Rain",
            "Drizzle",
            "Thunderstorm"
        ]:
            tag = "Chuvoso"

        elif condicao == "Clouds":
            tag = "Nublado"

        else:
            tag = "Ensolarado"

        return {
            "temp": dados["main"]["temp"],
            "tag": tag,
            "desc": dados["weather"][0]["description"]
        }

    except Exception as erro:

        print()
        print("===================================")
        print("ERRO AO OBTER CLIMA")
        print("===================================")
        print(erro)
        print("===================================")

        return {
            "temp": None,
            "tag": "Indisponível",
            "desc": "Não foi possível obter o clima."
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

    sp_oauth = criar_autenticador_spotify()

    try:

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
# INÍCIO
# =========================================================

@app.route("/", methods=["GET", "POST"])
def home():

    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        senha = request.form.get(
            "senha",
            ""
        ).strip()

        resultado = verificar_usuario(
            usuario,
            senha
        )

        if resultado:

            session["usuario_id"] = resultado[0]
            session["usuario_logado"] = resultado[1]
            session["tipo_usuario"] = resultado[2]

            if resultado[2] == "master":
                return redirect(
                    url_for("root_panel")
                )

            return redirect(
                url_for("spotify_login")
            )

        return render_template(
            "login.html",
            erro="Usuário ou senha incorretos."
        )

    if session.get("usuario_logado"):

        if session.get("token_info"):
            return redirect(
                url_for("dashboard")
            )

        if session.get("tipo_usuario") == "master":
            return redirect(
                url_for("root_panel")
            )

        return redirect(
            url_for("spotify_login")
        )

    return render_template("login.html")

# =========================================================
# LOGIN DO SINTONIA
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        senha = request.form.get(
            "senha",
            ""
        ).strip()

        resultado = verificar_usuario(
            usuario,
            senha
        )

        if resultado:

            id_usuario = resultado[0]
            nome_usuario = resultado[1]
            tipo_usuario = resultado[2]

            session["usuario_id"] = id_usuario
            session["usuario_logado"] = nome_usuario
            session["tipo_usuario"] = tipo_usuario

            if tipo_usuario == "master":

                return redirect(
                    url_for("root_panel")
                )

            return redirect(
                url_for("spotify_login")
            )

        return render_template(
            "login.html",
            erro="Usuário ou senha incorretos."
        )

    return render_template("login.html")


# =========================================================
# CADASTRO
# =========================================================

@app.route("/cadastro", methods=["GET", "POST"])
def cadastrar():

    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        senha = request.form.get(
            "senha",
            ""
        ).strip()

        confirmar_senha = request.form.get(
            "confirmar_senha",
            ""
        ).strip()

        if not usuario or not senha:

            return render_template(
                "cadastro.html",
                erro="Preencha todos os campos."
            )

        if senha != confirmar_senha:

            return render_template(
                "cadastro.html",
                erro="As senhas não coincidem."
            )

        sucesso = cadastrar_usuario(
            usuario,
            senha
        )

        if not sucesso:

            return render_template(
                "cadastro.html",
                erro="Esse usuário já existe."
            )

        resultado = verificar_usuario(
            usuario,
            senha
        )

        session["usuario_id"] = resultado[0]
        session["usuario_logado"] = resultado[1]
        session["tipo_usuario"] = resultado[2]

        return redirect(
            url_for("spotify_login")
        )

    return render_template("cadastro.html")


# =========================================================
# LOGIN DO SPOTIFY
# =========================================================

@app.route("/spotify")
def spotify_login():

    if not session.get("usuario_logado"):

        return redirect(
            url_for("login")
        )

    if session.get("token_info"):

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "spotify_login.html"
    )


@app.route("/login-spotify")
def login_spotify():

    if not session.get("usuario_logado"):

        return redirect(
            url_for("login")
        )

    sp_oauth = criar_autenticador_spotify()

    auth_url = sp_oauth.get_authorize_url()

    return redirect(auth_url)


# =========================================================
# CALLBACK DO SPOTIFY
# =========================================================

@app.route("/callback")
def callback():

    if not session.get("usuario_logado"):

        return redirect(
            url_for("login")
        )

    sp_oauth = criar_autenticador_spotify()

    if request.args.get("error"):

        erro = request.args.get("error")

        return (
            "<h2>Erro na autenticação do Spotify</h2>"
            f"<p>{erro}</p>"
        )

    code = request.args.get("code")

    if not code:

        return (
            "<h2>Erro</h2>"
            "<p>Código de autorização não recebido.</p>"
        )

    try:

        token_info = sp_oauth.get_access_token(
            code
        )

        session["token_info"] = token_info

        return redirect(
            url_for("dashboard")
        )

    except Exception as erro:

        print(
            "Erro ao obter token do Spotify:",
            erro
        )

        return (
            "<h2>Erro ao conectar ao Spotify</h2>"
            f"<p>{erro}</p>"
        )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if not session.get("usuario_logado"):

        return redirect(
            url_for("login")
        )

    sp = obter_spotify_cliente()

    if not sp:

        return redirect(
            url_for("spotify_login")
        )

    try:

        usuario_spotify = sp.current_user()

        nome_spotify = usuario_spotify.get(
            "display_name",
            ""
        )

    except Exception as erro:

        print(
            "Erro ao obter usuário do Spotify:",
            erro
        )

        nome_spotify = ""

    return render_template(
        "dashboard.html",
        nome_usuario=session.get(
            "usuario_logado"
        ),
        nome_spotify=nome_spotify
    )


# =========================================================
# GERAR PLAYLIST
# =========================================================

@app.route("/gerar", methods=["POST"])
def gerar():

    if not session.get("usuario_logado"):

        return redirect(
            url_for("login")
        )

    sp = obter_spotify_cliente()

    if not sp:

        return redirect(
            url_for("spotify_login")
        )

    # -----------------------------------------------------
    # DADOS DO FORMULÁRIO
    # -----------------------------------------------------

    cidade = request.form.get(
        "cidade",
        ""
    ).strip()

    artista = request.form.get(
        "artista",
        ""
    ).strip()

    humor = request.form.get(
        "humor",
        "Feliz"
    ).strip()

    if not cidade:

        cidade = "São Paulo"

    # -----------------------------------------------------
    # CLIMA
    # -----------------------------------------------------

    clima = obter_clima(cidade)

    humor_limpo = remover_acentos(
        humor
    )

    clima_limpo = remover_acentos(
        clima["tag"]
    )

    # -----------------------------------------------------
    # BUSCA DAS MÚSICAS
    # -----------------------------------------------------

    if artista:

        termo_busca = (
            f"{remover_acentos(artista)} "
            f"{humor_limpo}"
        )

    else:

        termo_busca = (
            f"{humor_limpo} "
            f"{clima_limpo}"
        )

    print()
    print("===================================")
    print("SINTONIA")
    print("BUSCA DE MÚSICAS")
    print("===================================")
    print("Usuário:", session.get("usuario_logado"))
    print("Cidade:", cidade)
    print("Humor:", humor)
    print("Clima:", clima["tag"])
    print("Temperatura:", clima["temp"])
    print("Artista:", artista)
    print("Termo pesquisado:", termo_busca)
    print("===================================")

    tracks_uris = []

    try:

        resultados = sp.search(
            q=termo_busca,
            type="track",
            limit=10
        )

        tracks_uris = [
            item["uri"]
            for item in resultados[
                "tracks"
            ]["items"]
        ]

        print(
            "Músicas encontradas:",
            len(tracks_uris)
        )

    except Exception as erro:

        print(
            "Erro ao buscar músicas:",
            erro
        )

    # -----------------------------------------------------
    # SEGUNDA TENTATIVA DE BUSCA
    # -----------------------------------------------------

    if not tracks_uris:

        try:

            resultados = sp.search(
                q=humor_limpo,
                type="track",
                limit=10
            )

            tracks_uris = [
                item["uri"]
                for item in resultados[
                    "tracks"
                ]["items"]
            ]

            print(
                "Músicas encontradas na segunda busca:",
                len(tracks_uris)
            )

        except Exception as erro:

            print(
                "Erro na segunda busca:",
                erro
            )

    # -----------------------------------------------------
    # NOME DA PLAYLIST
    # -----------------------------------------------------

    nome_playlist = (
        f"Sintonia | {humor} | "
        f"{clima['tag']}"
    )

    if artista:

        nome_playlist += (
            f" | {artista}"
        )

    # -----------------------------------------------------
    # DESCRIÇÃO DO CLIMA
    # -----------------------------------------------------

    if clima["temp"] is not None:

        descricao_clima = (
            f"{clima['desc']}, "
            f"{clima['temp']:.1f}°C"
        )

    else:

        descricao_clima = (
            clima["desc"]
        )

    # -----------------------------------------------------
    # CRIAR PLAYLIST
    # -----------------------------------------------------

    try:

        playlist = sp.current_user_playlist_create(
            name=nome_playlist,
            public=True,
            description=(
                f"Playlist criada pelo Sintonia "
                f"para {cidade}. "
                f"Clima: {descricao_clima}."
            )
        )

        print(
            "Playlist criada com sucesso."
        )

    except Exception as erro:

        print(
            "ERRO AO CRIAR PLAYLIST:",
            erro
        )

        return (
            "<h2>Não foi possível criar "
            "a playlist.</h2>"
            f"<p>{erro}</p>"
        )

    # -----------------------------------------------------
    # ADICIONAR MÚSICAS
    # -----------------------------------------------------

    if tracks_uris:

        try:

            sp.playlist_add_items(
                playlist_id=playlist["id"],
                items=tracks_uris
            )

            print(
                "Músicas adicionadas:",
                len(tracks_uris)
            )

        except Exception as erro:

            print(
                "Erro ao adicionar músicas:",
                erro
            )

    else:

        print(
            "Nenhuma música foi encontrada."
        )

    # -----------------------------------------------------
    # ABRIR PLAYLIST
    # -----------------------------------------------------

    url_spotify = (
        playlist[
            "external_urls"
        ]["spotify"]
    )

    return redirect(
        url_spotify
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# ÁREA MASTER
# =========================================================

@app.route(
    "/root",
    methods=["GET", "POST"]
)
def root_login():

    if session.get("tipo_usuario") == "master":

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
        ).strip()

        resultado = verificar_usuario(
            usuario,
            senha
        )

        if resultado and resultado[2] == "master":

            session["usuario_id"] = resultado[0]
            session["usuario_logado"] = resultado[1]
            session["tipo_usuario"] = resultado[2]

            return redirect(
                url_for("root_panel")
            )

        erro = (
            "Acesso restrito à área Master."
        )

    return render_template(
        "root_login.html",
        erro=erro
    )


@app.route("/root/painel")
def root_panel():

    if session.get("tipo_usuario") != "master":

        return redirect(
            url_for("root_login")
        )

    return render_template(
        "root_panel.html"
    )


@app.route("/root/logout")
def root_logout():

    session.pop(
        "tipo_usuario",
        None
    )

    session.pop(
        "usuario_id",
        None
    )

    session.pop(
        "usuario_logado",
        None
    )

    return redirect(
        url_for("root_login")
    )


# =========================================================
# EXECUÇÃO
# =========================================================

if __name__ == "__main__":

    criar_banco()

    print()
    print("===================================")
    print("SINTONIA")
    print("===================================")
    print("Aplicação rodando em:")
    print("http://127.0.0.1:8888")
    print()
    print("Acesso Master:")
    print("http://127.0.0.1:8888/root")
    print("Usuário: root")
    print("Senha: root")
    print("===================================")
    print()

    app.run(
        debug=True,
        port=8888
    )
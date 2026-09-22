import os
import json
import sqlite3
import unicodedata

import requests
import spotipy

from flask import (
    Flask,
    redirect,
    request,
    render_template,
    session,
    url_for,
    send_file,
    jsonify
)

from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

from database import conectar, criar_tabelas


# ============================================================
# CONFIGURAÇÃO
# ============================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "chave-secreta-temporaria"
)

DATABASE = "database.db"

SPOTIPY_CLIENT_ID = os.getenv(
    "SPOTIPY_CLIENT_ID"
)

SPOTIPY_CLIENT_SECRET = os.getenv(
    "SPOTIPY_CLIENT_SECRET"
)

SPOTIPY_REDIRECT_URI = (
    "http://127.0.0.1:8888/callback"
)

SCOPE = (
    "playlist-modify-public "
    "playlist-modify-private "
    "user-read-private"
)

WEATHER_API_KEY = os.getenv(
    "WEATHER_API_KEY"
)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def remover_acentos(texto):

    if not texto:
        return ""

    return "".join(
        caractere
        for caractere in unicodedata.normalize(
            "NFD",
            texto
        )
        if unicodedata.category(caractere) != "Mn"
    )


# ============================================================
# CLIMA POR CIDADE
# ============================================================

def obter_clima(cidade):
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

        print("Cidade enviada para o OpenWeather:", cidade)
        print("Status do OpenWeather:", resposta.status_code)

        resposta.raise_for_status()

        dados = resposta.json()

        print("Dados recebidos:", dados)

        condicao = dados["weather"][0]["main"]

        if condicao in ["Rain", "Drizzle", "Thunderstorm"]:
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
        print("ERRO AO OBTER CLIMA:", erro)

        return {
            "temp": None,
            "tag": "Indisponível",
            "desc": "Não foi possível obter o clima."
        }

    except Exception as erro:

        print(
            "Erro ao obter clima:",
            erro
        )

    return {
        "temp": 22.0,
        "tag": "Ensolarado",
        "desc": "céu limpo"
    }


# ============================================================
# CLIMA POR LOCALIZAÇÃO
# ============================================================

def obter_clima_por_coordenadas(latitude, longitude):

    url = (
        "https://api.openweathermap.org/"
        "data/2.5/weather"
    )

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
            timeout=5
        )

        resposta.raise_for_status()

        dados = resposta.json()

        if dados.get("cod") == 200:

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
                "desc": dados["weather"][0]["description"],
                "cidade": dados.get("name", "")
            }

    except Exception as erro:

        print(
            "Erro ao obter clima por localização:",
            erro
        )

    return None


# ============================================================
# SPOTIFY
# ============================================================

def criar_autenticador_spotify():

    return SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SCOPE,
        show_dialog=True
    )


def obter_spotify_cliente():

    token_info = session.get(
        "token_info"
    )

    if not token_info:

        return None

    sp_oauth = criar_autenticador_spotify()

    try:

        if sp_oauth.is_token_expired(
            token_info
        ):

            refresh_token = token_info.get(
                "refresh_token"
            )

            if not refresh_token:

                session.pop(
                    "token_info",
                    None
                )

                return None

            token_info = (
                sp_oauth.refresh_access_token(
                    refresh_token
                )
            )

            session["token_info"] = token_info

        return spotipy.Spotify(
            auth=token_info["access_token"]
        )

    except Exception as erro:

        print(
            "Erro ao obter cliente Spotify:",
            erro
        )

        session.pop(
            "token_info",
            None
        )

        return None


# ============================================================
# LOGIN DO SINTONIA
# ============================================================

@app.route("/", methods=["GET", "POST"])
def home():

    if session.get("usuario"):

        return redirect(
            url_for("spotify_login")
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

        conexao = conectar()

        conta = conexao.execute(
            """
            SELECT *
            FROM usuarios
            WHERE usuario = ?
            """,
            (usuario,)
        ).fetchone()

        conexao.close()

        if conta and check_password_hash(
            conta["senha"],
            senha
        ):

            session["usuario"] = (
                conta["usuario"]
            )

            return redirect(
                url_for("spotify_login")
            )

        erro = (
            "Usuário ou senha incorretos."
        )

    return render_template(
        "login.html",
        erro=erro
    )


# ============================================================
# CADASTRO
# ============================================================

@app.route(
    "/cadastrar",
    methods=["GET", "POST"]
)
def cadastrar():

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

        if not usuario or not senha:

            erro = (
                "Preencha todos os campos."
            )

            return render_template(
                "cadastro.html",
                erro=erro
            )

        if usuario.lower() == "root":

            erro = (
                "Esse usuário não está disponível."
            )

            return render_template(
                "cadastro.html",
                erro=erro
            )

        conexao = conectar()

        existente = conexao.execute(
            """
            SELECT id
            FROM usuarios
            WHERE usuario = ?
            """,
            (usuario,)
        ).fetchone()

        if existente:

            conexao.close()

            erro = (
                "Esse usuário já existe."
            )

            return render_template(
                "cadastro.html",
                erro=erro
            )

        senha_hash = generate_password_hash(
            senha
        )

        conexao.execute(
            """
            INSERT INTO usuarios (
                usuario,
                senha
            )
            VALUES (?, ?)
            """,
            (
                usuario,
                senha_hash
            )
        )

        conexao.commit()
        conexao.close()

        session["usuario"] = usuario

        return redirect(
            url_for("spotify_login")
        )

    return render_template(
        "cadastro.html",
        erro=erro
    )


# ============================================================
# TELA ANTES DO SPOTIFY
# ============================================================

@app.route("/spotify-login")
def spotify_login():

    if not session.get("usuario"):

        return redirect(
            url_for("home")
        )

    if session.get("token_info"):

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "spotify_login.html",
        usuario=session.get("usuario")
    )


# ============================================================
# ENTRAR NO SPOTIFY
# ============================================================

@app.route("/spotify-auth")
def spotify_auth():

    if not session.get("usuario"):

        return redirect(
            url_for("home")
        )

    sp_oauth = (
        criar_autenticador_spotify()
    )

    auth_url = (
        sp_oauth.get_authorize_url()
    )

    return redirect(auth_url)


# ============================================================
# CALLBACK DO SPOTIFY
# ============================================================

@app.route("/callback")
def callback():

    if not session.get("usuario"):

        return redirect(
            url_for("home")
        )

    sp_oauth = (
        criar_autenticador_spotify()
    )

    if request.args.get("error"):

        erro = request.args.get(
            "error"
        )

        return render_template(
            "spotify_login.html",
            usuario=session.get("usuario"),
            erro=erro
        )

    code = request.args.get(
        "code"
    )

    if not code:

        return render_template(
            "spotify_login.html",
            usuario=session.get("usuario"),
            erro=(
                "Código de autorização "
                "não recebido."
            )
        )

    try:

        token_info = (
            sp_oauth.get_access_token(
                code
            )
        )

        session["token_info"] = (
            token_info
        )

        return redirect(
            url_for("dashboard")
        )

    except Exception as erro:

        print(
            "Erro ao obter token:",
            erro
        )

        return render_template(
            "spotify_login.html",
            usuario=session.get("usuario"),
            erro=str(erro)
        )


# ============================================================
# LOCALIZAÇÃO DO USUÁRIO
# ============================================================

@app.route("/localizacao", methods=["POST"])
def localizacao():

    if not session.get("usuario"):

        return jsonify({
            "erro": "Usuário não autenticado."
        }), 401

    dados = request.get_json()

    if not dados:

        return jsonify({
            "erro": "Localização não recebida."
        }), 400

    latitude = dados.get(
        "latitude"
    )

    longitude = dados.get(
        "longitude"
    )

    if latitude is None or longitude is None:

        return jsonify({
            "erro": "Coordenadas inválidas."
        }), 400

    clima = obter_clima_por_coordenadas(
        latitude,
        longitude
    )

    if not clima:

        return jsonify({
            "erro": (
                "Não foi possível "
                "identificar a localização."
            )
        }), 400

    return jsonify({
        "cidade": clima["cidade"],
        "latitude": latitude,
        "longitude": longitude
    })


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if not session.get("usuario"):

        return redirect(
            url_for("home")
        )

    sp = obter_spotify_cliente()

    if not sp:

        return redirect(
            url_for("spotify_login")
        )

    return render_template(
        "dashboard.html",
        usuario=session.get(
            "usuario"
        )
    )


# ============================================================
# GERAR PLAYLIST
# ============================================================

@app.route(
    "/gerar",
    methods=["POST"]
)
def gerar():

    if not session.get("usuario"):

        return redirect(
            url_for("home")
        )

    sp = obter_spotify_cliente()

    if not sp:

        return redirect(
            url_for("spotify_login")
        )

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
    )

    if not cidade:

        return """
        <h2>Informe uma cidade.</h2>
        <a href="/dashboard">
            Voltar
        </a>
        """

    clima = obter_clima(
        cidade
    )

    humor_limpo = remover_acentos(
        humor
    )

    clima_limpo = remover_acentos(
        clima["tag"]
    )

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
    print("BUSCA DE MÚSICAS")
    print("===================================")
    print(
        "Usuário:",
        session.get("usuario")
    )
    print(
        "Cidade:",
        cidade
    )
    print(
        "Humor:",
        humor
    )
    print(
        "Clima:",
        clima["tag"]
    )
    print(
        "Artista:",
        artista
    )
    print(
        "Termo pesquisado:",
        termo_busca
    )
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
            for item
            in resultados["tracks"]["items"]
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

    if not tracks_uris:

        try:

            resultados = sp.search(
                q=humor_limpo,
                type="track",
                limit=10
            )

            tracks_uris = [
                item["uri"]
                for item
                in resultados["tracks"]["items"]
            ]

        except Exception as erro:

            print(
                "Erro na segunda busca:",
                erro
            )

            nome_playlist = f"Sintonia | {humor} | {clima['tag']}"

        if artista:
            nome_playlist += f" | {artista}"

        if clima["temp"] is not None:
            descricao_clima = f"{clima['desc']}, {clima['temp']:.1f}°C"
        else:
            descricao_clima = clima["desc"]

    try:
            playlist = sp.current_user_playlist_create(
                name=nome_playlist,
                public=True,
                description=(
                    f"Playlist criada pelo Sintonia para {cidade}. "
                    f"Clima: {descricao_clima}."
                )
            )

    except Exception as erro:

        print(
            "Erro ao criar playlist:",
            erro
        )

        return f"""
        <h2>
            Não foi possível criar
            a playlist.
        </h2>

        <p>{erro}</p>
        """

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

    url_spotify = (
        playlist["external_urls"]
        ["spotify"]
    )

    return redirect(
        url_spotify
    )


# ============================================================
# LOGOUT DO USUÁRIO
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# ============================================================
# ÁREA MASTER
# ============================================================

ROOT_USER = "root"
ROOT_PASSWORD = "root"


@app.route(
    "/root",
    methods=["GET", "POST"]
)
def root_login():

    if session.get(
        "root_authenticated"
    ):

        return redirect(
            url_for("root_panel")
        )

    erro = None

    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        )

        senha = request.form.get(
            "senha",
            ""
        )

        if (
            usuario == ROOT_USER
            and senha == ROOT_PASSWORD
        ):

            session[
                "root_authenticated"
            ] = True

            return redirect(
                url_for("root_panel")
            )

        erro = (
            "Usuário ou senha incorretos."
        )

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

    nome_arquivo = (
        "sintonia_database.json"
    )

    conexao = sqlite3.connect(
        DATABASE
    )

    conexao.row_factory = sqlite3.Row

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
        nome_arquivo,
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            banco,
            arquivo,
            ensure_ascii=False,
            indent=4
        )

    return send_file(
        nome_arquivo,
        as_attachment=True,
        download_name=nome_arquivo,
        mimetype="application/json"
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


# ============================================================
# INICIALIZAÇÃO
# ============================================================

criar_tabelas()


if __name__ == "__main__":

    print()
    print("===================================")
    print("SINTONIA")
    print("===================================")
    print(
        "Aplicação rodando em:"
    )
    print(
        "http://127.0.0.1:8888"
    )
    print()
    print(
        "Usuário pré-cadastrado:"
    )
    print(
        "Usuário: root"
    )
    print(
        "Senha: root"
    )
    print()
    print(
        "Acesso Master:"
    )
    print(
        "http://127.0.0.1:8888/root"
    )
    print("===================================")
    print()

    app.run(
        debug=True,
        port=8888
    )
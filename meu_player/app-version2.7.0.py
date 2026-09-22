import os
import sqlite3
import unicodedata
import requests
import json
from flask import send_file

from flask import (
    Flask,
    redirect,
    request,
    render_template,
    session,
    url_for,
    jsonify
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
    "chave-secreta-sintonia"
)

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE = os.path.join(
    BASE_DIR,
    "database.db"
)

SPOTIPY_CLIENT_ID = os.getenv(
    "SPOTIPY_CLIENT_ID"
)

SPOTIPY_CLIENT_SECRET = os.getenv(
    "SPOTIPY_CLIENT_SECRET"
)

SPOTIPY_REDIRECT_URI = (
    "http://127.0.0.1:8888/callback"
)

WEATHER_API_KEY = os.getenv(
    "WEATHER_API_KEY"
)

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

    cursor.execute("""
        SELECT id
        FROM usuarios
        WHERE usuario = ?
    """, ("root",))

    root = cursor.fetchone()

    if not root:

        cursor.execute("""
            INSERT INTO usuarios
            (
                usuario,
                senha,
                tipo
            )
            VALUES (?, ?, ?)
        """, (
            "root",
            "root",
            "master"
        ))

    conexao.commit()
    conexao.close()


def verificar_usuario(
    usuario,
    senha
):

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            id,
            usuario,
            tipo
        FROM usuarios
        WHERE usuario = ?
        AND senha = ?
    """, (
        usuario,
        senha
    ))

    resultado = cursor.fetchone()

    conexao.close()

    return resultado


def cadastrar_usuario(
    usuario,
    senha
):

    conexao = conectar_banco()
    cursor = conexao.cursor()

    try:

        cursor.execute("""
            INSERT INTO usuarios
            (
                usuario,
                senha,
                tipo
            )
            VALUES (?, ?, ?)
        """, (
            usuario,
            senha,
            "usuario"
        ))

        conexao.commit()

        sucesso = True

    except sqlite3.IntegrityError:

        sucesso = False

    conexao.close()

    return sucesso


# =========================================================
# TEXTO
# =========================================================

def remover_acentos(texto):

    if not texto:
        return ""

    return "".join(
        caractere
        for caractere in unicodedata.normalize(
            "NFD",
            texto
        )
        if unicodedata.category(
            caractere
        ) != "Mn"
    )


# =========================================================
# CLIMA POR CIDADE
# =========================================================

def obter_clima_por_cidade(cidade):

    if not WEATHER_API_KEY:

        return {
            "sucesso": False,
            "erro": "Chave do OpenWeather não configurada."
        }

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
    )

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

        dados = resposta.json()

        if resposta.status_code != 200:

            return {
                "sucesso": False,
                "erro": dados.get(
                    "message",
                    "Cidade não encontrada."
                )
            }

        return preparar_clima(
            dados
        )

    except Exception as erro:

        return {
            "sucesso": False,
            "erro": str(erro)
        }


# =========================================================
# CLIMA POR LOCALIZAÇÃO
# =========================================================

def obter_clima_por_coordenadas(
    latitude,
    longitude
):

    if not WEATHER_API_KEY:

        return {
            "sucesso": False,
            "erro": "Chave do OpenWeather não configurada."
        }

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
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
            timeout=10
        )

        dados = resposta.json()

        if resposta.status_code != 200:

            return {
                "sucesso": False,
                "erro": dados.get(
                    "message",
                    "Não foi possível obter o clima."
                )
            }

        return preparar_clima(
            dados
        )

    except Exception as erro:

        return {
            "sucesso": False,
            "erro": str(erro)
        }


# =========================================================
# ORGANIZAÇÃO DOS DADOS DO CLIMA
# =========================================================

def preparar_clima(dados):

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

    temperatura = dados["main"].get(
        "temp"
    )

    return {
        "sucesso": True,

        "cidade": dados.get(
            "name",
            "Localização atual"
        ),

        "temp": temperatura,

        "tag": tag,

        "desc": dados["weather"][0].get(
            "description",
            ""
        )
    }


# =========================================================
# ROTA PARA TESTAR CLIMA
# =========================================================

@app.route(
    "/api/clima",
    methods=["GET"]
)
def api_clima():

    latitude = request.args.get(
        "latitude"
    )

    longitude = request.args.get(
        "longitude"
    )

    cidade = request.args.get(
        "cidade"
    )

    if latitude and longitude:

        try:

            latitude = float(latitude)
            longitude = float(longitude)

        except ValueError:

            return jsonify({
                "sucesso": False,
                "erro": "Coordenadas inválidas."
            })

        resultado = obter_clima_por_coordenadas(
            latitude,
            longitude
        )

    elif cidade:

        resultado = obter_clima_por_cidade(
            cidade
        )

    else:

        resultado = obter_clima_por_cidade(
            "São Paulo"
        )

    return jsonify(resultado)


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
            auth=token_info[
                "access_token"
            ]
        )

    except Exception as erro:

        print(
            "Erro no Spotify:",
            erro
        )

        session.pop(
            "token_info",
            None
        )

        return None


# =========================================================
# INÍCIO
# =========================================================

@app.route("/")
def home():

    if session.get(
        "usuario_logado"
    ):

        if session.get(
            "tipo_usuario"
        ) == "master":

            return redirect(
                url_for("root_panel")
            )

        if not session.get(
            "token_info"
        ):

            return redirect(
                url_for("spotify_login")
            )

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "login.html"
    )


# =========================================================
# LOGIN DO SINTONIA
# =========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
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

        if not resultado:

            return render_template(
                "login.html",
                erro="Usuário ou senha incorretos."
            )

        session["usuario_id"] = resultado[0]

        session["usuario_logado"] = (
            resultado[1]
        )

        session["tipo_usuario"] = (
            resultado[2]
        )

        if resultado[2] == "master":

            return redirect(
                url_for("root_panel")
            )

        # Aqui está a mudança principal:
        # o usuário vai diretamente para
        # a autorização do Spotify.

        return redirect(
            url_for("spotify_login")
        )

    return render_template(
        "login.html"
    )


# =========================================================
# CADASTRO
# =========================================================

@app.route(
    "/cadastro",
    methods=["GET", "POST"]
)
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

        session["usuario_logado"] = (
            resultado[1]
        )

        session["tipo_usuario"] = (
            resultado[2]
        )

        # Cadastro também vai diretamente
        # para o Spotify.

        return redirect(
            url_for("spotify_login")
        )

    return render_template(
        "cadastro.html"
    )


# =========================================================
# SPOTIFY
# =========================================================

@app.route("/spotify")
def spotify_login():

    if not session.get(
        "usuario_logado"
    ):

        return redirect(
            url_for("login")
        )

    # Se já houver uma sessão válida,
    # não pede autorização novamente.

    if session.get(
        "token_info"
    ):

        return redirect(
            url_for("dashboard")
        )

    sp_oauth = criar_autenticador_spotify()

    auth_url = (
        sp_oauth.get_authorize_url()
    )

    return redirect(
        auth_url
    )


# =========================================================
# CALLBACK DO SPOTIFY
# =========================================================

@app.route("/callback")
def callback():

    if not session.get(
        "usuario_logado"
    ):

        return redirect(
            url_for("login")
        )

    if request.args.get(
        "error"
    ):

        erro = request.args.get(
            "error"
        )

        return (
            "<h2>Erro na autorização "
            "do Spotify</h2>"
            f"<p>{erro}</p>"
        )

    code = request.args.get(
        "code"
    )

    if not code:

        return (
            "<h2>Erro</h2>"
            "<p>Código de autorização "
            "não recebido.</p>"
        )

    sp_oauth = criar_autenticador_spotify()

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
            "Erro ao conectar ao Spotify:",
            erro
        )

        return (
            "<h2>Erro ao conectar "
            "ao Spotify</h2>"
            f"<p>{erro}</p>"
        )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if not session.get(
        "usuario_logado"
    ):

        return redirect(
            url_for("login")
        )

    sp = obter_spotify_cliente()

    if not sp:

        return redirect(
            url_for("spotify_login")
        )

    return render_template(
        "dashboard.html",
        nome_usuario=session.get(
            "usuario_logado"
        )
    )


# =========================================================
# GERAR PLAYLIST
# =========================================================

@app.route(
    "/gerar",
    methods=["POST"]
)
def gerar():

    if not session.get(
        "usuario_logado"
    ):

        return redirect(
            url_for("login")
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

    latitude = request.form.get(
        "latitude",
        ""
    ).strip()

    longitude = request.form.get(
        "longitude",
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

    # -----------------------------------------------------
    # O CLIMA É OBTIDO POR COORDENADAS QUANDO DISPONÍVEL
    # -----------------------------------------------------

    clima = None

    if latitude and longitude:

        try:

            clima = obter_clima_por_coordenadas(
                float(latitude),
                float(longitude)
            )

        except ValueError:

            clima = None

    # -----------------------------------------------------
    # SE NÃO HOUVER COORDENADAS, USA A CIDADE DIGITADA
    # -----------------------------------------------------

    if not clima or not clima.get(
        "sucesso"
    ):

        if not cidade:

            cidade = "São Paulo"

        clima = obter_clima_por_cidade(
            cidade
        )

    # -----------------------------------------------------
    # SE AINDA ASSIM DER ERRO
    # -----------------------------------------------------

    if not clima.get(
        "sucesso"
    ):

        return (
            "<h2>Não foi possível "
            "obter o clima.</h2>"
            f"<p>{clima.get('erro')}</p>"
        )

    cidade_real = clima.get(
        "cidade"
    ) or cidade or "Localização atual"

    humor_limpo = remover_acentos(
        humor
    )

    clima_limpo = remover_acentos(
        clima["tag"]
    )

    # -----------------------------------------------------
    # BUSCA
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
    print("===================================")
    print(
        "Usuário:",
        session.get("usuario_logado")
    )
    print(
        "Cidade:",
        cidade_real
    )
    print(
        "Clima:",
        clima["tag"]
    )
    print(
        "Temperatura:",
        clima["temp"]
    )
    print(
        "Humor:",
        humor
    )
    print(
        "Artista:",
        artista
    )
    print(
        "Busca:",
        termo_busca
    )
    print("===================================")

    # -----------------------------------------------------
    # BUSCAR MÚSICAS
    # -----------------------------------------------------

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

    except Exception as erro:

        print(
            "Erro na busca:",
            erro
        )

    # Segunda tentativa

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

        except Exception as erro:

            print(
                "Erro na segunda busca:",
                erro
            )

    # -----------------------------------------------------
    # NOME DA PLAYLIST
    # -----------------------------------------------------

    nome_playlist = (
        f"Sintonia | "
        f"{humor} | "
        f"{clima['tag']}"
    )

    if artista:

        nome_playlist += (
            f" | {artista}"
        )

    # -----------------------------------------------------
    # DESCRIÇÃO
    # -----------------------------------------------------

    if clima["temp"] is not None:

        descricao = (
            f"Playlist criada pelo "
            f"Sintonia para "
            f"{cidade_real}. "
            f"Clima: "
            f"{clima['desc']}, "
            f"{clima['temp']:.1f}°C."
        )

    else:

        descricao = (
            f"Playlist criada pelo "
            f"Sintonia para "
            f"{cidade_real}."
        )

    # -----------------------------------------------------
    # CRIAR PLAYLIST
    # -----------------------------------------------------

    try:

        playlist = (
            sp.current_user_playlist_create(
                name=nome_playlist,
                public=True,
                description=descricao
            )
        )

    except Exception as erro:

        print(
            "Erro ao criar playlist:",
            erro
        )

        return (
            "<h2>Não foi possível "
            "criar a playlist.</h2>"
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

        except Exception as erro:

            print(
                "Erro ao adicionar músicas:",
                erro
            )

    # -----------------------------------------------------
    # REDIRECIONAR PARA SPOTIFY
    # -----------------------------------------------------

    return redirect(
        playlist[
            "external_urls"
        ]["spotify"]
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
# MASTER
# =========================================================

@app.route(
    "/root",
    methods=["GET", "POST"]
)
def root_login():

    if session.get(
        "tipo_usuario"
    ) == "master":

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

        if (
            resultado
            and resultado[2] == "master"
        ):

            session["usuario_id"] = (
                resultado[0]
            )

            session["usuario_logado"] = (
                resultado[1]
            )

            session["tipo_usuario"] = (
                resultado[2]
            )

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

    if session.get(
        "tipo_usuario"
    ) != "master":

        return redirect(
            url_for("root_login")
        )

    return render_template(
        "root_panel.html"
    )


@app.route("/root/logout")
def root_logout():

    session.pop(
        "usuario_id",
        None
    )

    session.pop(
        "usuario_logado",
        None
    )

    session.pop(
        "tipo_usuario",
        None
    )

    return redirect(
        url_for("root_login")
    )


# =========================================================
# EXECUÇÃO
# =========================================================

    if __name__ == "__main__":

        @app.route("/root/exportar")
        def root_exportar():

            if not session.get("root_authenticated"):
                return redirect(url_for("root_login"))

        banco = "database.db"
        arquivo_json = "sintonia_database.json"

        conexao = sqlite3.connect(banco)
        conexao.row_factory = sqlite3.Row
        cursor = conexao.cursor()

        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
        """)

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

        with open(arquivo_json, "w", encoding="utf-8") as arquivo:
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

    criar_banco()

    print()
    print("===================================")
    print("SINTONIA")
    print("===================================")
    print(
        "http://127.0.0.1:8888"
    )
    print()
    print("MASTER")
    print(
        "http://127.0.0.1:8888/root"
    )
    print("Usuário: root")
    print("Senha: root")
    print("===================================")
    print()

    app.run(
        debug=True,
        port=8888
    )
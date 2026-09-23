import os
import json
import sqlite3
import secrets
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

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

from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth


# ============================================================
# CONFIGURAÇÃO
# ============================================================

load_dotenv()

SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

REDIRECT_URI = "http://127.0.0.1:8888/callback"

SCOPE = (
    "playlist-modify-public "
    "playlist-modify-private "
    "user-read-private"
)

DATABASE = "database.db"

ROOT_USUARIO = "root"
ROOT_SENHA = "root"


app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    secrets.token_hex(32)
)


# ============================================================
# VERIFICAÇÃO DAS CONFIGURAÇÕES
# ============================================================

def verificar_configuracoes():

    faltando = []

    if not SPOTIPY_CLIENT_ID:
        faltando.append("SPOTIPY_CLIENT_ID")

    if not SPOTIPY_CLIENT_SECRET:
        faltando.append("SPOTIPY_CLIENT_SECRET")

    if not WEATHER_API_KEY:
        faltando.append("WEATHER_API_KEY")

    if faltando:
        print()
        print("=" * 60)
        print("ERRO: configurações ausentes no arquivo .env")
        print("=" * 60)

        for item in faltando:
            print(f"- {item}")

        print("=" * 60)
        print()


# ============================================================
# BANCO DE DADOS
# ============================================================

def conectar_banco():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def criar_banco():

    conn = conectar_banco()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            spotify_id TEXT,
            data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # --------------------------------------------------------
    # Migração para bancos antigos
    # --------------------------------------------------------

    cursor.execute("PRAGMA table_info(usuarios)")
    colunas = [linha["name"] for linha in cursor.fetchall()]

    if "usuario" not in colunas:
        try:
            cursor.execute(
                "ALTER TABLE usuarios ADD COLUMN usuario TEXT"
            )
        except sqlite3.OperationalError:
            pass

    if "senha" not in colunas:
        try:
            cursor.execute(
                "ALTER TABLE usuarios ADD COLUMN senha TEXT"
            )
        except sqlite3.OperationalError:
            pass

    if "spotify_id" not in colunas:
        try:
            cursor.execute(
                "ALTER TABLE usuarios ADD COLUMN spotify_id TEXT"
            )
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()


# ============================================================
# USUÁRIO
# ============================================================

def obter_usuario_por_id(usuario_id):

    conn = conectar_banco()

    usuario = conn.execute(
        """
        SELECT *
        FROM usuarios
        WHERE id = ?
        """,
        (usuario_id,)
    ).fetchone()

    conn.close()

    return usuario


def obter_usuario_por_login(usuario):

    conn = conectar_banco()

    resultado = conn.execute(
        """
        SELECT *
        FROM usuarios
        WHERE usuario = ?
        """,
        (usuario,)
    ).fetchone()

    conn.close()

    return resultado


def atualizar_spotify_usuario(usuario_id, spotify_id):

    conn = conectar_banco()

    conn.execute(
        """
        UPDATE usuarios
        SET spotify_id = ?
        WHERE id = ?
        """,
        (spotify_id, usuario_id)
    )

    conn.commit()
    conn.close()


# ============================================================
# SPOTIFY OAUTH
# ============================================================

def criar_spotify_oauth():

    return SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=None,
        show_dialog=True
    )


def obter_spotify():

    token_info = session.get("token_info")

    if not token_info:
        return None

    oauth = criar_spotify_oauth()

    if oauth.is_token_expired(token_info):

        try:
            token_info = oauth.refresh_access_token(
                token_info["refresh_token"]
            )

            session["token_info"] = token_info

        except Exception:
            session.pop("token_info", None)
            return None

    return spotipy.Spotify(
        auth=token_info["access_token"]
    )


# ============================================================
# LOGIN / CADASTRO
# ============================================================

@app.route("/")
def index():

    if session.get("usuario_id"):
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():

    if request.method == "POST":

        nome = request.form.get("nome", "").strip()
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        confirmar = request.form.get("confirmar_senha", "")

        if not nome or not usuario or not senha:
            return render_template(
                "cadastro.html",
                erro="Preencha todos os campos."
            )

        if len(senha) < 4:
            return render_template(
                "cadastro.html",
                erro="A senha deve possuir pelo menos 4 caracteres."
            )

        if senha != confirmar:
            return render_template(
                "cadastro.html",
                erro="As senhas não coincidem."
            )

        existente = obter_usuario_por_login(usuario)

        if existente:
            return render_template(
                "cadastro.html",
                erro="Esse nome de usuário já está cadastrado."
            )

        senha_hash = generate_password_hash(senha)

        conn = conectar_banco()

        try:

            cursor = conn.execute(
                """
                INSERT INTO usuarios
                (nome, usuario, senha)
                VALUES (?, ?, ?)
                """,
                (
                    nome,
                    usuario,
                    senha_hash
                )
            )

            usuario_id = cursor.lastrowid

            conn.commit()

        except sqlite3.IntegrityError:

            conn.rollback()
            conn.close()

            return render_template(
                "cadastro.html",
                erro="Esse nome de usuário já está cadastrado."
            )

        conn.close()

        session.clear()

        session["usuario_id"] = usuario_id
        session["nome_sintonia"] = nome

        return redirect(
            url_for("spotify_login")
        )

    return render_template("cadastro.html")


@app.route("/login", methods=["POST"])
def login():

    usuario = request.form.get("usuario", "").strip()
    senha = request.form.get("senha", "")

    if not usuario or not senha:

        return render_template(
            "login.html",
            erro="Informe usuário e senha."
        )

    usuario_db = obter_usuario_por_login(usuario)

    if not usuario_db:

        return render_template(
            "login.html",
            erro="Usuário ou senha incorretos."
        )

    senha_hash = usuario_db["senha"]

    if not senha_hash:

        return render_template(
            "login.html",
            erro="Essa conta precisa ser cadastrada novamente."
        )

    if not check_password_hash(senha_hash, senha):

        return render_template(
            "login.html",
            erro="Usuário ou senha incorretos."
        )

    session.clear()

    session["usuario_id"] = usuario_db["id"]
    session["nome_sintonia"] = usuario_db["nome"]

    # Se já existe Spotify vinculado, ainda pedimos
    # autorização novamente para garantir um token válido.
    return redirect(
        url_for("spotify_login")
    )


# ============================================================
# LOGOUT DO SINTONIA
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("index")
    )


# ============================================================
# LOGIN SPOTIFY
# ============================================================

@app.route("/spotify/login")
def spotify_login():

    if not session.get("usuario_id"):

        return redirect(
            url_for("index")
        )

    oauth = criar_spotify_oauth()

    return redirect(
        oauth.get_authorize_url()
    )


# ============================================================
# CALLBACK SPOTIFY
# ============================================================

@app.route("/callback")
def callback():

    codigo = request.args.get("code")

    if not codigo:

        erro = request.args.get(
            "error",
            "Autorização cancelada."
        )

        return render_template(
            "erro.html",
            mensagem=f"Não foi possível conectar ao Spotify: {erro}"
        )

    if not session.get("usuario_id"):

        return redirect(
            url_for("index")
        )

    try:

        oauth = criar_spotify_oauth()

        token_info = oauth.get_access_token(
            codigo,
            as_dict=True
        )

        session["token_info"] = token_info

        spotify = spotipy.Spotify(
            auth=token_info["access_token"]
        )

        perfil = spotify.current_user()

        spotify_id = perfil.get("id")

        if spotify_id:

            atualizar_spotify_usuario(
                session["usuario_id"],
                spotify_id
            )

        return redirect(
            url_for("dashboard")
        )

    except Exception as e:

        print()
        print("ERRO NO CALLBACK DO SPOTIFY:")
        print(e)
        print()

        return render_template(
            "erro.html",
            mensagem=(
                "Não foi possível concluir a conexão "
                "com o Spotify."
            )
        )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if not session.get("usuario_id"):

        return redirect(
            url_for("index")
        )

    spotify = obter_spotify()

    if not spotify:

        return redirect(
            url_for("spotify_login")
        )

    usuario = obter_usuario_por_id(
        session["usuario_id"]
    )

    return render_template(
        "dashboard.html",
        usuario=usuario
    )


# ============================================================
# CLIMA
# ============================================================

def normalizar_texto(texto):

    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    return texto.lower().strip()


def obter_clima(cidade):

    clima_padrao = {
        "ok": False,
        "temp": 0,
        "tag": "neutro",
        "desc": "Clima não disponível",
        "cidade": cidade
    }

    if not WEATHER_API_KEY:
        return clima_padrao

    if not cidade:
        return clima_padrao

    try:

        resposta = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q": cidade,
                "appid": WEATHER_API_KEY,
                "units": "metric",
                "lang": "pt_br"
            },
            timeout=10
        )

        if resposta.status_code != 200:
            return clima_padrao

        dados = resposta.json()

        temperatura = dados.get(
            "main",
            {}
        ).get(
            "temp"
        )

        descricao = dados.get(
            "weather",
            [{}]
        )[0].get(
            "description",
            "Clima não informado"
        )

        cidade_real = dados.get(
            "name",
            cidade
        )

        tag = classificar_clima(
            descricao,
            temperatura
        )

        return {
            "ok": True,
            "temp": temperatura,
            "tag": tag,
            "desc": descricao,
            "cidade": cidade_real
        }

    except Exception as e:

        print("Erro ao consultar clima:", e)

        return clima_padrao


def classificar_clima(descricao, temperatura):

    texto = normalizar_texto(
        descricao
    )

    try:
        temperatura = float(
            temperatura
        )
    except (TypeError, ValueError):
        temperatura = 20

    if any(
        palavra in texto
        for palavra in [
            "chuva",
            "garoa",
            "tempestade"
        ]
    ):
        return "chuvoso"

    if any(
        palavra in texto
        for palavra in [
            "neve",
            "nevasca"
        ]
    ):
        return "frio"

    if any(
        palavra in texto
        for palavra in [
            "nublado",
            "nuvem"
        ]
    ):
        return "nublado"

    if temperatura >= 28:
        return "quente"

    if temperatura <= 15:
        return "frio"

    return "agradavel"


# ============================================================
# ARTISTAS
# ============================================================

def similaridade(a, b):

    a = normalizar_texto(a)
    b = normalizar_texto(b)

    return SequenceMatcher(
        None,
        a,
        b
    ).ratio()


def encontrar_artista(spotify, nome_digitado):

    nome_digitado = nome_digitado.strip()

    if not nome_digitado:
        return None

    candidatos = []

    # --------------------------------------------------------
    # Busca exata por artista
    # --------------------------------------------------------

    consultas = [
        f'artist:"{nome_digitado}"',
        nome_digitado
    ]

    for consulta in consultas:

        try:

            resultado = spotify.search(
                q=consulta,
                type="artist",
                limit=10,
                offset=0
            )

            artistas = resultado.get(
                "artists",
                {}
            ).get(
                "items",
                []
            )

            candidatos.extend(
                artistas
            )

        except Exception as e:

            print(
                "Erro na busca do artista:",
                e
            )

    # Remove duplicados
    unicos = {}

    for artista in candidatos:

        artista_id = artista.get("id")

        if artista_id:
            unicos[artista_id] = artista

    candidatos = list(
        unicos.values()
    )

    if not candidatos:
        return None

    nome_normalizado = normalizar_texto(
        nome_digitado
    )

    # --------------------------------------------------------
    # 1. Correspondência exata
    # --------------------------------------------------------

    for artista in candidatos:

        nome = artista.get(
            "name",
            ""
        )

        if normalizar_texto(nome) == nome_normalizado:
            return artista

    # --------------------------------------------------------
    # 2. Correspondência por similaridade
    # --------------------------------------------------------

    melhor = None
    melhor_nota = 0

    for artista in candidatos:

        nome = artista.get(
            "name",
            ""
        )

        nota = similaridade(
            nome_digitado,
            nome
        )

        if nota > melhor_nota:

            melhor_nota = nota
            melhor = artista

    # Limite para evitar escolher artista completamente diferente
    if melhor and melhor_nota >= 0.60:

        return melhor

    return None


def buscar_musicas_do_artista(
    spotify,
    artista
):

    artista_id = artista.get(
        "id"
    )

    artista_nome = artista.get(
        "name",
        ""
    )

    if not artista_id:
        return []

    musicas = []
    ids_adicionados = set()

    # Spotify atualmente permite no máximo 10 resultados
    # por busca, então fazemos paginação.
    offsets = [0, 10, 20, 30, 40]

    for offset in offsets:

        try:

            resultado = spotify.search(
                q=f'artist:"{artista_nome}"',
                type="track",
                limit=10,
                offset=offset
            )

        except Exception as e:

            print(
                "Erro na busca das músicas:",
                e
            )

            continue

        tracks = resultado.get(
            "tracks",
            {}
        ).get(
            "items",
            []
        )

        if not tracks:
            break

        for faixa in tracks:

            faixa_id = faixa.get(
                "id"
            )

            if not faixa_id:
                continue

            if faixa_id in ids_adicionados:
                continue

            artistas_faixa = faixa.get(
                "artists",
                []
            )

            pertence = any(
                artista_faixa.get("id") == artista_id
                for artista_faixa in artistas_faixa
            )

            if not pertence:
                continue

            musicas.append(
                faixa
            )

            ids_adicionados.add(
                faixa_id
            )

        if len(musicas) >= 30:
            break

    return musicas


# ============================================================
# MÚSICAS POR HUMOR / CLIMA
# ============================================================

def buscar_musicas_por_humor(
    spotify,
    humor,
    clima
):

    termos = []

    humor_normalizado = normalizar_texto(
        humor
    )

    mapa_humor = {

        "feliz": [
            "happy",
            "feel good",
            "dance"
        ],

        "triste": [
            "sad",
            "melancholic",
            "ballad"
        ],

        "calmo": [
            "chill",
            "acoustic",
            "calm"
        ],

        "animado": [
            "party",
            "dance",
            "energetic"
        ],

        "romantico": [
            "love",
            "romantic",
            "love songs"
        ],

        "focado": [
            "focus",
            "instrumental",
            "study"
        ]
    }

    termos.extend(
        mapa_humor.get(
            humor_normalizado,
            ["pop"]
        )
    )

    mapa_clima = {

        "chuvoso": [
            "rainy",
            "lofi"
        ],

        "frio": [
            "cozy",
            "acoustic"
        ],

        "quente": [
            "summer",
            "sun"
        ],

        "nublado": [
            "indie",
            "alternative"
        ],

        "agradavel": [
            "chill",
            "pop"
        ],

        "neutro": [
            "pop"
        ]
    }

    termos.extend(
        mapa_clima.get(
            clima,
            ["pop"]
        )
    )

    musicas = []
    ids_adicionados = set()

    for termo in termos:

        try:

            resultado = spotify.search(
                q=termo,
                type="track",
                limit=10,
                offset=0
            )

        except Exception as e:

            print(
                "Erro ao buscar músicas:",
                e
            )

            continue

        tracks = resultado.get(
            "tracks",
            {}
        ).get(
            "items",
            []
        )

        for faixa in tracks:

            faixa_id = faixa.get(
                "id"
            )

            if not faixa_id:
                continue

            if faixa_id in ids_adicionados:
                continue

            musicas.append(
                faixa
            )

            ids_adicionados.add(
                faixa_id
            )

            if len(musicas) >= 30:
                return musicas

    return musicas


# ============================================================
# CRIAÇÃO DA PLAYLIST
# ============================================================

def criar_playlist_spotify(
    spotify,
    nome,
    descricao,
    uris
):

    if not uris:
        raise ValueError(
            "Nenhuma música foi encontrada."
        )

    token_info = session.get(
        "token_info"
    )

    if not token_info:
        raise ValueError(
            "Token do Spotify não encontrado."
        )

    access_token = token_info.get(
        "access_token"
    )

    if not access_token:
        raise ValueError(
            "Token de acesso do Spotify inválido."
        )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # --------------------------------------------------------
    # A API atual usa POST /me/playlists
    # --------------------------------------------------------

    resposta = requests.post(
        "https://api.spotify.com/v1/me/playlists",
        headers=headers,
        json={
            "name": nome,
            "description": descricao,
            "public": False
        },
        timeout=15
    )

    if resposta.status_code not in [200, 201]:

        print(
            "Erro ao criar playlist:",
            resposta.status_code,
            resposta.text
        )

        raise RuntimeError(
            "O Spotify não permitiu criar a playlist."
        )

    playlist = resposta.json()

    playlist_id = playlist.get(
        "id"
    )

    if not playlist_id:
        raise RuntimeError(
            "O Spotify não retornou o ID da playlist."
        )

    # --------------------------------------------------------
    # A API atual usa /items
    # --------------------------------------------------------

    for inicio in range(
        0,
        len(uris),
        100
    ):

        bloco = uris[
            inicio:inicio + 100
        ]

        resposta_itens = requests.post(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/items",
            headers=headers,
            json={
                "uris": bloco
            },
            timeout=15
        )

        if resposta_itens.status_code not in [200, 201]:

            print(
                "Erro ao adicionar músicas:",
                resposta_itens.status_code,
                resposta_itens.text
            )

            raise RuntimeError(
                "A playlist foi criada, mas não foi possível adicionar as músicas."
            )

    return playlist


# ============================================================
# GERAR PLAYLIST
# ============================================================

@app.route("/gerar", methods=["POST"])
def gerar():

    if not session.get("usuario_id"):

        return redirect(
            url_for("index")
        )

    spotify = obter_spotify()

    if not spotify:

        return redirect(
            url_for("spotify_login")
        )

    cidade = request.form.get(
        "cidade",
        ""
    ).strip()

    humor = request.form.get(
        "humor",
        ""
    ).strip()

    artista_digitado = request.form.get(
        "artista",
        ""
    ).strip()

    if not cidade:

        return render_template(
            "erro.html",
            mensagem="Informe uma cidade."
        )

    if not humor:

        return render_template(
            "erro.html",
            mensagem="Selecione um humor."
        )

    # --------------------------------------------------------
    # CLIMA
    # --------------------------------------------------------

    clima = obter_clima(
        cidade
    )

    if not clima["ok"]:

        return render_template(
            "erro.html",
            mensagem=(
                "Não foi possível encontrar essa cidade "
                "ou consultar o clima."
            )
        )

    # --------------------------------------------------------
    # BUSCA DE MÚSICAS
    # --------------------------------------------------------

    artista = None

    if artista_digitado:

        artista = encontrar_artista(
            spotify,
            artista_digitado
        )

        if not artista:

            return render_template(
                "erro.html",
                mensagem=(
                    f'O artista "{artista_digitado}" '
                    "não foi encontrado no Spotify."
                )
            )

        musicas = buscar_musicas_do_artista(
            spotify,
            artista
        )

        if not musicas:

            return render_template(
                "erro.html",
                mensagem=(
                    f'Não foram encontradas músicas '
                    f'disponíveis para "{artista["name"]}".'
                )
            )

        nome_artista = artista["name"]

    else:

        musicas = buscar_musicas_por_humor(
            spotify,
            humor,
            clima["tag"]
        )

        if not musicas:

            return render_template(
                "erro.html",
                mensagem=(
                    "Não foi possível encontrar músicas "
                    "para essa combinação."
                )
            )

        nome_artista = ""

    # --------------------------------------------------------
    # LIMITA A PLAYLIST
    # --------------------------------------------------------

    musicas = musicas[:30]

    tracks_uris = []

    for faixa in musicas:

        uri = faixa.get(
            "uri"
        )

        if uri and uri not in tracks_uris:
            tracks_uris.append(uri)

    if not tracks_uris:

        return render_template(
            "erro.html",
            mensagem="Nenhuma música válida foi encontrada."
        )

    # --------------------------------------------------------
    # NOME DA PLAYLIST
    # --------------------------------------------------------

    nome_playlist = (
        f"Sintonia - {humor.capitalize()}"
    )

    descricao = (
        f"Playlist criada pelo Sintonia para "
        f"{clima['cidade']}, com clima "
        f"{clima['desc']}."
    )

    if nome_artista:

        nome_playlist = (
            f"Sintonia - {nome_artista}"
        )

        descricao = (
            f"Playlist do Sintonia com músicas "
            f"de {nome_artista}, baseada no humor "
            f"{humor} e no clima de {clima['cidade']}."
        )

    # --------------------------------------------------------
    # CRIA PLAYLIST
    # --------------------------------------------------------

    try:

        playlist = criar_playlist_spotify(
            spotify,
            nome_playlist,
            descricao,
            tracks_uris
        )

    except Exception as e:

        print()
        print("ERRO AO CRIAR PLAYLIST:")
        print(e)
        print()

        return render_template(
            "erro.html",
            mensagem=(
                "Não foi possível criar a playlist "
                "no Spotify."
            )
        )

    # --------------------------------------------------------
    # INFORMAÇÕES DAS MÚSICAS
    # --------------------------------------------------------

    musicas_resultado = []

    for faixa in musicas:

        artistas_faixa = ", ".join(
            artista_faixa.get(
                "name",
                ""
            )
            for artista_faixa in faixa.get(
                "artists",
                []
            )
        )

        musicas_resultado.append({
            "nome": faixa.get(
                "name",
                "Música"
            ),
            "artista": artistas_faixa,
            "uri": faixa.get(
                "uri"
            )
        })

    # --------------------------------------------------------
    # DEBUG NO TERMINAL
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("PLAYLIST GERADA")
    print("=" * 60)
    print("Nome:", nome_playlist)
    print("Cidade:", clima["cidade"])
    print("Temperatura:", clima["temp"])
    print("Clima:", clima["desc"])
    print("Humor:", humor)

    if nome_artista:
        print("Artista:", nome_artista)

    print()
    print("Músicas:")

    for faixa in musicas_resultado:
        print(
            f"- {faixa['nome']} — {faixa['artista']}"
        )

    print("=" * 60)
    print()

    return render_template(
        "resultado.html",
        playlist=playlist,
        musicas=musicas_resultado,
        clima=clima,
        humor=humor,
        artista=nome_artista
    )


# ============================================================
# ÁREA ROOT / MASTER
# ============================================================

@app.route("/root", methods=["GET", "POST"])
def root_login():

    if session.get("root_logado"):
        return redirect(
            url_for("root_painel")
        )

    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        senha = request.form.get(
            "senha",
            ""
        )

        if (
            usuario == ROOT_USUARIO
            and senha == ROOT_SENHA
        ):

            session["root_logado"] = True

            return redirect(
                url_for("root_painel")
            )

        return render_template(
            "root_login.html",
            erro="Usuário ou senha incorretos."
        )

    return render_template(
        "root_login.html"
    )


@app.route("/root/painel")
def root_painel():

    if not session.get("root_logado"):

        return redirect(
            url_for("root_login")
        )

    conn = conectar_banco()

    usuarios = conn.execute(
        """
        SELECT
            id,
            nome,
            usuario,
            spotify_id,
            data_cadastro
        FROM usuarios
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "root_panel.html",
        usuarios=usuarios
    )


@app.route("/root/exportar")
def root_exportar():

    if not session.get("root_logado"):

        return redirect(
            url_for("root_login")
        )

    conn = conectar_banco()
    cursor = conn.cursor()

    tabelas = cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        """
    ).fetchall()

    banco = {}

    for tabela in tabelas:

        nome_tabela = tabela["name"]

        linhas = cursor.execute(
            f'SELECT * FROM "{nome_tabela}"'
        ).fetchall()

        banco[nome_tabela] = [
            dict(linha)
            for linha in linhas
        ]

    conn.close()

    arquivo = "sintonia_database.json"

    with open(
        arquivo,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            banco,
            f,
            ensure_ascii=False,
            indent=4,
            default=str
        )

    return send_file(
        arquivo,
        as_attachment=True,
        download_name="sintonia_database.json",
        mimetype="application/json"
    )


@app.route("/root/logout")
def root_logout():

    session.pop(
        "root_logado",
        None
    )

    return redirect(
        url_for("root_login")
    )


# ============================================================
# TRATAMENTO DE ERROS
# ============================================================

@app.errorhandler(404)
def pagina_nao_encontrada(error):

    return render_template(
        "erro.html",
        mensagem="Página não encontrada."
    ), 404


@app.errorhandler(500)
def erro_servidor(error):

    print()
    print("ERRO 500:")
    print(error)
    print()

    return render_template(
        "erro.html",
        mensagem=(
            "Ocorreu um erro interno no Sintonia."
        )
    ), 500


# ============================================================
# INICIALIZAÇÃO
# ============================================================

if __name__ == "__main__":

    verificar_configuracoes()

    criar_banco()

    print()
    print("=" * 60)
    print("SINTONIA")
    print("=" * 60)
    print("Servidor: http://127.0.0.1:8888")
    print("Root:     http://127.0.0.1:8888/root")
    print("Callback: http://127.0.0.1:8888/callback")
    print("=" * 60)
    print()

    app.run(
        host="127.0.0.1",
        port=8888,
        debug=True
    )
import os
import requests
import spotipy
import webbrowser
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

load_dotenv(override=True)

SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID", "2afb6b4ba69e4aeaa32b965e9c3e51cc").strip()
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET", "f5a27ecd48e048e7969194bc35c8c8d5").strip()
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback").strip()
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "f190d8a0735419d985475ff1c8262eb2").strip()
CITY_NAME = "Sao Paulo"


def obter_clima():
    if not WEATHER_API_KEY:
        return "Ensolarado"
    url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY_NAME}&appid={WEATHER_API_KEY}&units=metric&lang=pt_br"
    try:
        res = requests.get(url).json()
        if res.get("cod") == 200:
            return res["weather"][0]["description"].capitalize()
    except Exception:
        pass
    return "Ensolarado"


def main():
    print("=" * 45)
    print("   CRIADOR DE PLAYLISTS INTELIGENTE (CLI)")
    print("=" * 45 + "\n")

    clima = obter_clima()
    print(f"📍 Clima atual em {CITY_NAME}: {clima}\n")

    humores = ["Feliz", "Triste", "Energético", "Calmo", "Romântico", "Nostálgico"]
    print("Escolha seu humor:")
    for i, h in enumerate(humores, 1):
        print(f" {i}. {h}")

    opcao = input("\nDigite o número correspondente (1-6): ").strip()
    idx = int(opcao) - 1 if opcao.isdigit() and 1 <= int(opcao) <= 6 else 0
    humor_escolhido = humores[idx]

    artista = input("Digite o nome de um artista (opcional, ou pressione ENTER): ").strip()

    termo_busca = f"{humor_escolhido} {clima}"
    if artista:
        termo_busca = f"{artista} {humor_escolhido}"

    print(f"\n🔍 Buscando músicas no Spotify...")

    try:
        scope = "playlist-modify-public playlist-modify-private"
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            redirect_uri=SPOTIPY_REDIRECT_URI,
            scope=scope
        ))

        user_id = sp.current_user()["id"]

        # Busca ajustada para limit=10
        resultados = sp.search(q=termo_busca, type="track", limit=10)
        tracks = resultados.get("tracks", {}).get("items", [])

        if not tracks:
            print("\n❌ Nenhuma música encontrada para esses parâmetros.")
            return

        track_uris = [track["uri"] for track in tracks]

        nome_playlist = f"Vibe: {humor_escolhido} ({clima})"
        if artista:
            nome_playlist = f"{artista} - {nome_playlist}"

        descricao = f"Playlist gerada automaticamente para clima '{clima}' e humor '{humor_escolhido}'."
        nova_playlist = sp.user_playlist_create(
            user=user_id,
            name=nome_playlist,
            public=True,
            description=descricao
        )

        sp.playlist_add_items(playlist_id=nova_playlist["id"], items=track_uris)

        print(f"\n✨ Playlist '{nome_playlist}' criada com sucesso na sua conta ({len(track_uris)} músicas)!")
        print("🚀 Redirecionando para o Spotify...")
        webbrowser.open(nova_playlist["external_urls"]["spotify"])

    except Exception as e:
        print(f"\nErro ao processar no Spotify: {e}")


if __name__ == "__main__":
    main()
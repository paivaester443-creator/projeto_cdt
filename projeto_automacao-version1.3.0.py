import os
import requests
import spotipy
import webbrowser
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

load_dotenv(override=True)

# Credenciais com fallback automático
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID", "2afb6b4ba69e4aeaa32b965e9c3e51cc").strip()
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET", "f5a27ecd48e048e7969194bc35c8c8d5").strip()
WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "f190d8a0735419d985475ff1c8262eb2").strip()
CITY_NAME = "Sao Paulo"


def obter_clima():
    if not WEATHER_API_KEY:
        return "Desconhecido"
    url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY_NAME}&appid={WEATHER_API_KEY}&units=metric&lang=pt_br"
    try:
        res = requests.get(url).json()
        if res.get("cod") == 200:
            return res["weather"][0]["description"].capitalize()
    except Exception:
        pass
    return "Ensolarado"


def main():
    print("=" * 40)
    print("   ASSISTENTE MUSICAL INTELIGENTE (CLI)")
    print("=" * 40 + "\n")

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

    termo = f"{humor_escolhido} {clima}"
    if artista:
        termo = f"{artista} {termo}"

    print(f"\n🔍 Buscando playlist para: '{termo}'...")

    try:
        auth_manager = SpotifyClientCredentials(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)

        resultados = sp.search(q=termo, type="playlist", limit=1)
        items = resultados.get("playlists", {}).get("items", [])

        if items:
            playlist = items[0]
            playlist_url = playlist["external_urls"]["spotify"]
            
            print(f"\n🎵 Playlist Encontrada: {playlist['name']}")
            print("🚀 Redirecionando para o Spotify no navegador...")
            webbrowser.open(playlist_url)
        else:
            print("\n❌ Nenhuma playlist encontrada para estes parâmetros.")
    except Exception as e:
        print(f"\nErro ao buscar no Spotify: {e}")


if __name__ == "__main__":
    main()
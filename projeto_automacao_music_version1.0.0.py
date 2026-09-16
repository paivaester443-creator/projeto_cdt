import os
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import customtkinter as ctk

# Configuração visual do tema Spotify
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

# Carrega chaves do .env
load_dotenv(override=True)

WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
CITY_NAME = "Sao Paulo"


class MusicAssistantGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Spotify Intelligent Assistant")
        self.geometry("480x580")
        self.resizable(False, False)

        self.sp = None
        self.inicializar_spotify()
        self.criar_interface()

    def inicializar_spotify(self):
        scope = "user-modify-playback-state user-read-playback-state playlist-modify-public playlist-modify-private"
        try:
            auth = SpotifyOAuth(
                client_id=SPOTIPY_CLIENT_ID,
                client_secret=SPOTIPY_CLIENT_SECRET,
                redirect_uri=SPOTIPY_REDIRECT_URI,
                scope=scope
            )
            self.sp = spotipy.Spotify(auth_manager=auth)
        except Exception as e:
            print(f"Erro ao conectar no Spotify: {e}")

    def obter_clima(self):
        if not WEATHER_API_KEY:
            return "Chave ausente", "--"
        url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY_NAME}&appid={WEATHER_API_KEY}&units=metric&lang=pt_br"
        try:
            res = requests.get(url).json()
            if res.get("cod") == 200:
                desc = res["weather"][0]["description"].capitalize()
                temp = f"{int(res['main']['temp'])}°C"
                return desc, temp
        except Exception:
            pass
        return "Indisponível", "--"

    def criar_interface(self):
        # Frame Principal
        container = ctk.CTkFrame(self, corner_radius=15, fg_color="#121212")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Cabeçalho
        logo = ctk.CTkLabel(container, text="🎵 Music Assistant", font=ctk.CTkFont(size=24, weight="bold"), text_color="#1DB954")
        logo.pack(pady=(20, 15))

        # Card de Clima
        clima_desc, clima_temp = self.obter_clima()
        card_clima = ctk.CTkFrame(container, fg_color="#181818", corner_radius=10)
        card_clima.pack(fill="x", padx=20, pady=10)

        lbl_clima_title = ctk.CTkLabel(card_clima, text=f"📍 {CITY_NAME}", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_clima_title.pack(anchor="w", padx=15, pady=(10, 2))
        
        lbl_clima_info = ctk.CTkLabel(card_clima, text=f"{clima_desc} | {clima_temp}", font=ctk.CTkFont(size=12), text_color="#B3B3B3")
        lbl_clima_info.pack(anchor="w", padx=15, pady=(0, 10))

        # Seleção de Humor
        lbl_humor = ctk.CTkLabel(container, text="Selecione seu Humor:", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_humor.pack(anchor="w", padx=25, pady=(15, 5))

        self.combo_humor = ctk.CTkOptionMenu(
            container, 
            values=["Feliz", "Triste", "Energético", "Calmo", "Romântico", "Nostálgico"],
            fg_color="#282828", button_color="#1DB954", button_hover_color="#1ed760"
        )
        self.combo_humor.pack(fill="x", padx=20, pady=5)

        # Campo para Artista
        lbl_artista = ctk.CTkLabel(container, text="Artista Específico (Opcional):", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_artista.pack(anchor="w", padx=25, pady=(15, 5))

        self.entry_artista = ctk.CTkEntry(container, placeholder_text="Ex: Coldplay, Anitta...", fg_color="#282828", border_width=0)
        self.entry_artista.pack(fill="x", padx=20, pady=5)

        # Botão Gerar Playlist
        btn_gerar = ctk.CTkButton(
            container, text="✨ Gerar Playlist no Spotify", font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#1DB954", hover_color="#1ed760", text_color="#000000", height=40,
            command=self.gerar_playlist
        )
        btn_gerar.pack(fill="x", padx=20, pady=(25, 10))

        # Status
        self.lbl_status = ctk.CTkLabel(container, text="Status: Pronto", font=ctk.CTkFont(size=12, slant="italic"), text_color="#B3B3B3")
        self.lbl_status.pack(pady=10)

    def gerar_playlist(self):
        humor = self.combo_humor.get()
        artista = self.entry_artista.get().strip()
        clima_desc, _ = self.obter_clima()

        termo = f"{humor} {clima_desc}"
        if artista:
            termo = f"{artista} {termo}"

        self.lbl_status.configure(text=f"Buscando no Spotify: '{termo}'...")

        if not self.sp:
            self.lbl_status.configure(text="Erro: Spotify não autenticado.")
            return

        try:
            resultados = self.sp.search(q=termo, type="playlist", limit=1)
            items = resultados.get("playlists", {}).get("items", [])

            if items:
                playlist = items[0]
                playlist_nome = playlist["name"]
                playlist_uri = playlist["uri"]

                devices = self.sp.devices()
                if devices.get("devices"):
                    self.sp.start_playback(context_uri=playlist_uri)
                    self.lbl_status.configure(text=f"▶ Tocando agora: {playlist_nome}")
                else:
                    self.lbl_status.configure(text=f"Encontrada: {playlist_nome} (Abra o app do Spotify)")
            else:
                self.lbl_status.configure(text="Nenhuma playlist encontrada para esse filtro.")
        except Exception as e:
            self.lbl_status.configure(text=f"Erro ao tocar playlist: {e}")


if __name__ == "__main__":
    app = MusicAssistantGUI()
    app.mainloop()
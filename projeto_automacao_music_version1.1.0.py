import os
import time
import cv2
import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import mediapipe as mp
import customtkinter as ctk
from PIL import Image, ImageTk

# Configuração visual do tema Spotify
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

load_dotenv(override=True)

WEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")
CITY_NAME = "Sao Paulo"

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils


class SpotifyAssistantGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Spotify Intelligent Assistant")
        self.geometry("1100x680")
        self.resizable(False, False)

        # Estados
        self.sp = None
        self.cap = None
        self.camera_ativa = False
        self.last_action_time = 0
        self.cooldown = 2.0

        # Conectar ao Spotify
        self.inicializar_spotify()

        # Layout
        self.criar_interface()

        # MediaPipe
        self.hands = mp_hands.Hands(min_detection_confidence=0.7, min_tracking_confidence=0.7)

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
            print(f"Erro Spotify: {e}")

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
        # Grid Principal (Painel Esquerdo + Painel Direito)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- PAINEL ESQUERDO (Controles) ---
        self.sidebar = ctk.CTkFrame(self, width=340, corner_radius=15, fg_color="#121212")
        self.sidebar.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")

        # Logo / Título
        self.logo = ctk.CTkLabel(self.sidebar, text="🎵 Music Assistant", font=ctk.CTkFont(size=22, weight="bold"), text_color="#1DB954")
        self.logo.pack(padx=20, pady=(20, 15), anchor="w")

        # Card de Clima
        clima_desc, clima_temp = self.obter_clima()
        self.card_clima = ctk.CTkFrame(self.sidebar, fg_color="#181818", corner_radius=10)
        self.card_clima.pack(fill="x", padx=15, pady=10)

        self.lbl_clima_title = ctk.CTkLabel(self.card_clima, text=f"📍 {CITY_NAME}", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_clima_title.pack(anchor="w", padx=12, pady=(8, 2))
        
        self.lbl_clima_info = ctk.CTkLabel(self.card_clima, text=f"{clima_desc} | {clima_temp}", font=ctk.CTkFont(size=12), text_color="#B3B3B3")
        self.lbl_clima_info.pack(anchor="w", padx=12, pady=(0, 8))

        # Seleção de Humor
        self.lbl_humor = ctk.CTkLabel(self.sidebar, text="Escolha seu Humor:", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_humor.pack(anchor="w", padx=20, pady=(15, 5))

        self.combo_humor = ctk.CTkOptionMenu(
            self.sidebar, 
            values=["Feliz", "Triste", "Energético", "Calmo", "Romântico", "Nostálgico"],
            fg_color="#282828", button_color="#1DB954", button_hover_color="#1ed760"
        )
        self.combo_humor.pack(fill="x", padx=15, pady=5)

        # Campo do Artista (Opcional)
        self.lbl_artista = ctk.CTkLabel(self.sidebar, text="Artista Específico (Opcional):", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_artista.pack(anchor="w", padx=20, pady=(15, 5))

        self.entry_artista = ctk.CTkEntry(self.sidebar, placeholder_text="Ex: Coldplay, Anitta...", fg_color="#282828", border_width=0)
        self.entry_artista.pack(fill="x", padx=15, pady=5)

        # Botão Gerar Playlist
        self.btn_gerar = ctk.CTkButton(
            self.sidebar, text="✨ Gerar Playlist", font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#1DB954", hover_color="#1ed760", text_color="#000000",
            command=self.gerar_playlist
        )
        self.btn_gerar.pack(fill="x", padx=15, pady=(25, 10))

        # Botão Ligar/Desligar Câmera
        self.btn_camera = ctk.CTkButton(
            self.sidebar, text="📷 Ligar Controle por Gestos", font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#282828", hover_color="#333333",
            command=self.toggle_camera
        )
        self.btn_camera.pack(fill="x", padx=15, pady=5)

        # Label de Status
        self.lbl_status = ctk.CTkLabel(self.sidebar, text="Status: Aguardando ação...", font=ctk.CTkFont(size=11, italic=True), text_color="#B3B3B3")
        self.lbl_status.pack(side="bottom", pady=15)

        # --- PAINEL DIREITO (Webcam + Display) ---
        self.main_panel = ctk.CTkFrame(self, corner_radius=15, fg_color="#000000")
        self.main_panel.grid(row=0, column=1, padx=(0, 15), pady=15, sticky="nsew")

        self.video_label = ctk.CTkLabel(self.main_panel, text="Câmera Desligada\nClique em 'Ligar Controle por Gestos'", font=ctk.CTkFont(size=16), text_color="#555555")
        self.video_label.pack(expand=True, fill="both", padx=10, pady=10)

    def gerar_playlist(self):
        humor = self.combo_humor.get()
        artista = self.entry_artista.get().strip()
        clima_desc, _ = self.obter_clima()

        termo = f"{humor} {clima_desc}"
        if artista:
            termo = f"{artista} {termo}"

        self.lbl_status.configure(text=f"Buscando: {termo}...")

        if not self.sp:
            self.lbl_status.configure(text="Erro: Spotify não conectado.")
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
                    self.lbl_status.configure(text=f"▶ Tocando: {playlist_nome}")
                else:
                    self.lbl_status.configure(text=f"Playlist achada! Abra o app do Spotify.")
            else:
                self.lbl_status.configure(text="Nenhuma playlist encontrada.")
        except Exception as e:
            self.lbl_status.configure(text=f"Erro no Spotify: {e}")

    def toggle_camera(self):
        if self.camera_ativa:
            self.camera_ativa = False
            if self.cap:
                self.cap.release()
            self.video_label.configure(image="", text="Câmera Desligada\nClique em 'Ligar Controle por Gestos'")
            self.btn_camera.configure(text="📷 Ligar Controle por Gestos", fg_color="#282828")
            self.lbl_status.configure(text="Câmera desligada.")
        else:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.lbl_status.configure(text="Erro ao abrir webcam.")
                return
            self.camera_ativa = True
            self.btn_camera.configure(text="🛑 Desligar Câmera", fg_color="#E74C3C")
            self.lbl_status.configure(text="Detectando gestos...")
            self.atualizar_video()

    def processar_gestos(self, hand_landmarks):
        agora = time.time()
        if agora - self.last_action_time < self.cooldown:
            return

        ind_tip = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
        ind_mcp = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_MCP]

        # Mão aberta (Play/Pause)
        if ind_tip.y < ind_mcp.y and self.sp:
            try:
                playback = self.sp.current_playback()
                if playback and playback.get("is_playing"):
                    self.sp.pause_playback()
                    self.lbl_status.configure(text="⏸ Gesto: Pausar Música")
                else:
                    self.sp.start_playback()
                    self.lbl_status.configure(text="▶ Gesto: Dar Play")
                self.last_action_time = agora
            except Exception:
                pass

    def atualizar_video(self):
        if not self.camera_ativa:
            return

        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb)

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(rgb, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                    self.processar_gestos(hand_landmarks)

            # Converter para Pillow e exibir no CustomTkinter
            img = Image.fromarray(rgb)
            img_ctk = ctk.CTkImage(light_image=img, dark_image=img, size=(680, 510))
            self.video_label.configure(image=img_ctk, text="")

        self.after(15, self.atualizar_video)


if __name__ == "__main__":
    app = SpotifyAssistantGUI()
    app.mainloop()
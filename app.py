import hashlib
import json
import os
import tempfile
import urllib.request

import cv2
import numpy as np
import paho.mqtt.publish as publish
import streamlit as st
import onnxruntime as ort
from PIL import Image

st.set_page_config(page_title="Osito-gotchi", page_icon="🐻", layout="centered")

BROKER = "broker.mqttdashboard.com"
PORT = 1883
TOPIC = "gestos/control/eafit/Luna"

# Emociones del modelo -> expresiones que entiende el ESP32
EMOCIONES = {"Happiness": "Happy", "Sadness": "Sad", "Neutral": "Neutral"}

# ══════════════════════════════════════════════════
#  SPRITES PIXEL ART (16x16)  '#' = pixel encendido
# ══════════════════════════════════════════════════
NEUTRAL = [
    "..###......###..",
    "..###......###..",
    "..############..",
    "..##.######.##..",
    "..##.######.##..",
    "..#####..#####..",
    "..############..",
    "..####....####..",
    "..############..",
    "...##########...",
    "..############..",
    "..####....####..",
    "...###....###...",
    "...##########...",
    "...###....###...",
    "...###....###...",
]
HAPPY = [
    "..###......###..",
    "..###......###..",
    "..############..",
    "..##.######.##..",
    "..#.#.####.#.#..",
    "..#####..#####..",
    "#.############.#",
    "#.###......###.#",
    "#.####....####.#",
    ".#.##########.#.",
    ".##############.",
    "..####....####..",
    "...###....###...",
    "...##########...",
    "...###....###...",
    "...###....###...",
]
SAD = [
    "................",
    "..###......###..",
    "..###......###..",
    "..############..",
    "..###.####.###..",
    "..##.######.##..",
    "..#####..#####..",
    "..############..",
    "..#####..#####..",
    "..###.####.###..",
    "...##########...",
    "..############..",
    "..####....####..",
    "..############..",
    ".####......####.",
    ".####......####.",
]
TUMBLEWEED = [
    "..####..",
    ".#....#.",
    "#.#..#.#",
    "#..##..#",
    "#..##..#",
    "#.#..#.#",
    ".#....#.",
    "..####..",
]

for _s in (NEUTRAL, HAPPY, SAD):
    assert len(_s) == 16 and all(len(r) == 16 for r in _s)


def sprite_path(rows):
    d = []
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c == "#":
                d.append(f"M{x} {y}h1v1h-1z")
    return "".join(d)


# ══════════════════════════════════════════════════
#  ESTILO TAMAGOTCHI
# ══════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

.stApp {
  background-color: #ffe9f2;
  background-image: radial-gradient(#ffc2d9 2px, transparent 2px);
  background-size: 22px 22px;
}
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 460px; padding-top: 1.5rem; }

/* ── Huevito ── */
.tama-wrap { display:flex; flex-direction:column; align-items:center; margin:6px 0 22px; }
.tama-ring {
  width:48px; height:48px; border:9px solid #ff8fb8; border-radius:50%;
  margin-bottom:-24px; box-shadow: inset 0 0 0 2px rgba(255,255,255,.45);
}
.tama-shell {
  position:relative; width:320px; max-width:100%; min-height:420px;
  border-radius:50% 50% 50% 50% / 56% 56% 44% 44%;
  background: radial-gradient(circle at 30% 20%, #ffd9e8 0%, #ff8fb8 45%, #e85a96 100%);
  box-shadow:
    inset -12px -16px 26px rgba(0,0,0,.18),
    inset 10px 12px 22px rgba(255,255,255,.5),
    0 14px 0 #c93d7a,
    0 26px 30px rgba(0,0,0,.28);
  display:flex; flex-direction:column; align-items:center;
  padding:46px 0 26px; box-sizing:border-box;
}
.tama-brand {
  font-family:'Press Start 2P','Courier New',monospace; font-size:10px;
  letter-spacing:2px; color:#fff; text-shadow:2px 2px 0 #c93d7a; margin-bottom:10px;
}
.tama-bezel {
  width:224px; background:#5b4bb8; border-radius:22px; padding:12px;
  box-shadow: inset 0 4px 8px rgba(0,0,0,.45), 0 3px 0 rgba(255,255,255,.35);
}
.tama-lcd {
  background:#c5d4a0; border-radius:8px; padding:8px 8px 10px;
  box-shadow: inset 0 3px 8px rgba(0,0,0,.35);
  color:#2b3a1e; font-family:'Press Start 2P','Courier New',monospace;
}
.lcd-top { display:flex; justify-content:space-between; font-size:9px; margin-bottom:4px; }
.lcd-top .hearts { letter-spacing:2px; }
.lcd-scene { width:100%; height:auto; display:block; image-rendering:pixelated; }
.lcd-text { text-align:center; font-size:10px; margin-top:6px; letter-spacing:1px; }

.tama-buttons { display:flex; gap:20px; margin-top:22px; align-items:flex-start; }
.tama-buttons span {
  width:36px; height:36px; border-radius:50%;
  background: radial-gradient(circle at 35% 30%, #fff6b8, #ffd43b 60%, #d9a900);
  box-shadow: 0 5px 0 #b58900, 0 8px 8px rgba(0,0,0,.3);
}
.tama-buttons span:nth-child(2) { margin-top:12px; }

/* ── Animaciones del osito ── */
@keyframes hop { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-4px)} }
@keyframes sob { 0%,100%{transform:translateY(0)} 50%{transform:translateY(1px)} }
@keyframes breathe { 0%,100%{transform:translateY(0)} 50%{transform:translateY(.6px)} }
@keyframes roll { from{transform:translateX(26px)} to{transform:translateX(-10px)} }
@keyframes spin { to{transform:rotate(-360deg)} }
@keyframes tear { 0%{transform:translateY(0);opacity:1} 100%{transform:translateY(7px);opacity:0} }
@keyframes blink { 0%,49%{opacity:1} 50%,100%{opacity:0} }
.hop { animation:hop .7s ease-in-out infinite; }
.sob { animation:sob 1.6s ease-in-out infinite; }
.breathe { animation:breathe 2s ease-in-out infinite; }
.tw-move { animation:roll 5s linear infinite; }
.tw-spin { transform-box:fill-box; transform-origin:center; animation:spin 1.2s linear infinite; }
.tear { animation:tear 1.4s linear infinite; }
.tear.t2 { animation-delay:.7s; }
.spk { animation:blink 1s infinite; }
.spk.s2 { animation-delay:.5s; }

/* ── Tarjeta de estadísticas ── */
.stats {
  background:#fff0f6; border:4px solid #ff8fb8; border-radius:20px;
  padding:12px 14px; margin-top:16px; box-shadow:0 6px 0 #c93d7a;
  font-family:'Press Start 2P','Courier New',monospace; color:#7a1f4d;
}
.stats .row { display:flex; align-items:center; gap:8px; margin:8px 0; font-size:9px; }
.stats .name { width:92px; }
.stats .bar { flex:1; height:12px; background:#ffd6e6; border-radius:6px; overflow:hidden; border:2px solid #ff8fb8; }
.stats .bar i { display:block; height:100%; background:#e85a96; }
.stats .pct { width:42px; text-align:right; }
.msg {
  text-align:center; margin-top:14px; font-size:9px; color:#7a1f4d;
  font-family:'Press Start 2P','Courier New',monospace;
}

/* ── Cámara ── */
div[data-testid="stCameraInput"] {
  background:#fff0f6; border:4px solid #ff8fb8; border-radius:24px;
  padding:12px; box-shadow:0 6px 0 #c93d7a;
}
div[data-testid="stCameraInput"] label p {
  font-family:'Press Start 2P','Courier New',monospace;
  font-size:10px; color:#c93d7a; line-height:1.6;
}
div[data-testid="stCameraInput"] video,
div[data-testid="stCameraInput"] img { border-radius:14px; }
div[data-testid="stCameraInput"] button {
  border-radius:999px; background:#ffd43b; color:#5b3a00;
  border:3px solid #d9a900; font-weight:700;
}
div[data-testid="stCameraInput"] button:hover { background:#ffe066; color:#5b3a00; border-color:#d9a900; }
</style>
"""

LCD_INFO = {
    "idle":    ("HOLA!",     2, "breathe"),
    "noface":  ("NO TE VEO", 2, "breathe"),
    "neutral": ("NEUTRAL",   2, "breathe"),
    "happy":   ("FELIZ",     3, "hop"),
    "sad":     ("TRISTE",    1, "sob"),
}


def render_device(estado):
    texto, corazones, anim = LCD_INFO[estado]
    sprite = {"happy": HAPPY, "sad": SAD}.get(estado, NEUTRAL)

    extras = ""
    if estado == "neutral":
        extras += (
            '<g transform="translate(0,13)"><g class="tw-move"><g class="tw-spin">'
            f'<path d="{sprite_path(TUMBLEWEED)}"/></g></g></g>'
        )
    if estado == "happy":
        spark = "M1 0h1v3h-1zM0 1h3v1h-3z"
        extras += (
            f'<g class="spk" transform="translate(1,3)"><path d="{spark}"/></g>'
            f'<g class="spk s2" transform="translate(20,5)"><path d="{spark}"/></g>'
            f'<g class="spk s2" transform="translate(19,0)"><path d="{spark}"/></g>'
        )
    if estado == "sad":
        extras += (
            '<rect class="tear" x="5" y="10" width="1" height="2"/>'
            '<rect class="tear t2" x="18" y="10" width="1" height="2"/>'
        )

    svg = (
        '<svg class="lcd-scene" viewBox="0 0 24 24" fill="currentColor" '
        'shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg">'
        f'<g transform="translate(4,5)"><g class="{anim}"><path d="{sprite_path(sprite)}"/></g></g>'
        f"{extras}"
        '<rect x="0" y="21" width="24" height="1"/>'
        "</svg>"
    )
    hearts = "♥" * corazones + "♡" * (3 - corazones)

    return (
        '<div class="tama-wrap"><div class="tama-ring"></div><div class="tama-shell">'
        '<div class="tama-brand">osito-gotchi</div>'
        '<div class="tama-bezel"><div class="tama-lcd">'
        f'<div class="lcd-top"><span>MOOD</span><span class="hearts">{hearts}</span></div>'
        f"{svg}"
        f'<div class="lcd-text">{texto}</div>'
        "</div></div>"
        '<div class="tama-buttons"><span></span><span></span><span></span></div>'
        "</div></div>"
    )


def render_stats(scores):
    nombres = {"Happy": "😄 FELIZ", "Sad": "😢 TRISTE", "Neutral": "😐 NEUTRAL"}
    filas = ""
    for clave, etiqueta in nombres.items():
        p = float(scores[clave])
        filas += (
            f'<div class="row"><span class="name">{etiqueta}</span>'
            f'<div class="bar"><i style="width:{p * 100:.0f}%"></i></div>'
            f'<span class="pct">{p:.0%}</span></div>'
        )
    return f'<div class="stats">{filas}</div>'


# ══════════════════════════════════════════════════
#  MODELO + MQTT
# ══════════════════════════════════════════════════
def ruta_cascada():
    """Encuentra (o descarga) el archivo del detector de caras de OpenCV."""
    nombre = "haarcascade_frontalface_default.xml"
    candidatos = []
    try:
        candidatos.append(cv2.data.haarcascades + nombre)
    except AttributeError:
        pass
    candidatos.append(os.path.join(os.path.dirname(cv2.__file__), "data", nombre))
    for c in candidatos:
        if os.path.exists(c):
            return c

    destino = os.path.join(tempfile.gettempdir(), nombre)
    if not os.path.exists(destino):
        url = (
            "https://raw.githubusercontent.com/opencv/opencv/4.x/"
            "data/haarcascades/" + nombre
        )
        urllib.request.urlretrieve(url, destino)
    return destino


MODELO_URL = (
    "https://github.com/HSE-asavchenko/face-emotion-recognition/blob/main/"
    "models/affectnet_emotions/onnx/enet_b0_8_best_afew.onnx?raw=true"
)
CLASES = ["Anger", "Contempt", "Disgust", "Fear",
          "Happiness", "Neutral", "Sadness", "Surprise"]


class Reconocedor:
    """Reconocedor de emociones (modelo ONNX EfficientNet-B0, 224x224)."""

    def __init__(self):
        ruta = os.path.join(tempfile.gettempdir(), "enet_b0_8_best_afew.onnx")
        if not os.path.exists(ruta) or os.path.getsize(ruta) < 1_000_000:
            urllib.request.urlretrieve(MODELO_URL, ruta)
        self.sesion = ort.InferenceSession(ruta, providers=["CPUExecutionProvider"])

    def predecir(self, rostro_rgb):
        x = cv2.resize(rostro_rgb, (224, 224)).astype("float32") / 255.0
        x[..., 0] = (x[..., 0] - 0.485) / 0.229
        x[..., 1] = (x[..., 1] - 0.456) / 0.224
        x[..., 2] = (x[..., 2] - 0.406) / 0.225
        x = x.transpose(2, 0, 1)[np.newaxis, ...].astype("float32")
        logits = self.sesion.run(None, {"input": x})[0][0]
        e = np.exp(logits - logits.max())
        probs = e / e.sum()
        return dict(zip(CLASES, probs))


@st.cache_resource
def cargar_modelos():
    modelo = Reconocedor()
    detector = cv2.CascadeClassifier(ruta_cascada())
    if detector.empty():
        raise RuntimeError("No se pudo cargar el detector de rostros")
    return modelo, detector


def analizar(foto, modelo, detector):
    img = np.array(Image.open(foto).convert("RGB"))
    gris = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    rostros = detector.detectMultiScale(gris, 1.1, 5, minSize=(80, 80))
    if len(rostros) == 0:
        return None

    x, y, w, h = max(rostros, key=lambda r: r[2] * r[3])
    rostro = img[y:y + h, x:x + w]

    puntajes = modelo.predecir(rostro)

    ganadora = max(EMOCIONES, key=lambda e: puntajes[e])
    return {
        "expresion": EMOCIONES[ganadora],
        "scores": {EMOCIONES[e]: float(puntajes[e]) for e in EMOCIONES},
    }


def enviar(expresion):
    payload = json.dumps({"expression": expresion})
    publish.single(TOPIC, payload, hostname=BROKER, port=PORT)


# ══════════════════════════════════════════════════
#  APP
# ══════════════════════════════════════════════════
st.markdown(CSS, unsafe_allow_html=True)

ss = st.session_state
ss.setdefault("estado", "idle")
ss.setdefault("scores", None)
ss.setdefault("hash", None)
ss.setdefault("msg", "")

shell = st.empty()
shell.markdown(render_device(ss.estado), unsafe_allow_html=True)

foto = st.camera_input("📷 ¡Ponle una carita a tu osito!")

if foto is not None:
    h = hashlib.md5(foto.getvalue()).hexdigest()
    if ss.hash != h:           # solo procesa fotos nuevas
        ss.hash = h
        try:
            with st.spinner("El osito está mirando tu cara..."):
                modelo, detector = cargar_modelos()
                resultado = analizar(foto, modelo, detector)
        except Exception as e:
            resultado = "error"
            ss.estado, ss.scores = "idle", None
            ss.msg = f"Error: {type(e).__name__}: {e}"

        if resultado is None:
            ss.estado, ss.scores = "noface", None
            ss.msg = "Acércate y mejora la luz"
        elif resultado != "error":
            ss.estado = resultado["expresion"].lower()
            ss.scores = resultado["scores"]
            try:
                enviar(resultado["expresion"])
                ss.msg = f"📡 Enviado al ESP32: {resultado['expresion']}"
            except Exception as e:
                ss.msg = f"Error al publicar: {e}"
        shell.markdown(render_device(ss.estado), unsafe_allow_html=True)

if ss.scores:
    st.markdown(render_stats(ss.scores), unsafe_allow_html=True)
if ss.msg:
    st.markdown(f'<div class="msg">{ss.msg}</div>', unsafe_allow_html=True)

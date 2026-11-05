import json
import streamlit as st
import paho.mqtt.publish as publish

BROKER = "broker.mqttdashboard.com"
PORT = 1883
TOPIC = "gestos/control/eafit/Luna"

def enviar(expresion):
    payload = json.dumps({"expression": expresion})
    try:
        publish.single(TOPIC, payload, hostname=BROKER, port=PORT)
        st.success(f"Enviado: {payload}")
    except Exception as e:
        st.error(f"Error al publicar: {e}")

st.title("🐻 Control del osito por gestos")
st.caption(f"Broker: {BROKER} | Tópico: {TOPIC}")

col1, col2, col3 = st.columns(3)

if col1.button("😄 Happy", use_container_width=True):
    enviar("Happy")
if col2.button("😢 Sad", use_container_width=True):
    enviar("Sad")
if col3.button("😐 Neutral", use_container_width=True):
    enviar("Neutral")

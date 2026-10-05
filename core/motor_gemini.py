import os
import re
import json
import time
import random
import streamlit as st
from google import genai
from core.database_redis import obtener_secreto

FRASES_SIMPSON = [
    "¡A la grande le puse cuca! Estamos en ello....",
    "¿Dónde está mi submarino amarillo?",
    "¡No está aquí! ¡No está aquí! ¡No está aquí! ... Bueno, si esta Aqui..",
    "A buscar tesoros... o a morir en el intento",
    "Ya merito llega...",
    "¡Pronto... muy pronto!",
    "Mi aparato cerebral está pensando...",
    "Cargando... por favor, inserte disquete 3 de 4",
    "Homero no poder pensar ahora, está trabajando",
    "Estoy procesando la información... A ver, espérame tantito"
]

MODELOS_DEFAULT = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.8-flash",
    "gemini-3-flash-preview"
]

def obtener_cliente_gemini():
    """Inicializa y retorna el cliente oficial de Google GenAI."""
    api_key = obtener_secreto("GEMINI_API_KEY", "") or st.session_state.get("gemini_api_key_manual", "")
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        st.error(f"Error inicializando cliente Gemini: {e}")
        return None

def obtener_frase_spinner():
    """Retorna una frase aleatoria de Los Simpson."""
    return random.choice(FRASES_SIMPSON)

def consultar_gemini(client, system_prompt, contexto_datos, user_query, modelos=None):
    """
    Envía la consulta a Gemini con fallback multimodelo y extrae el bloque de gráfico si existe.
    Retorna: (texto_limpio, chart_data, error_str)
    """
    if client is None:
        return None, None, "No hay cliente Gemini configurado."

    if modelos is None:
        modelos = MODELOS_DEFAULT

    prompt_completo = (
        system_prompt.strip()
        + "\n\nDATOS CALCULADOS DE FORMA MATEMÁTICA EXACTA:\n"
        + contexto_datos.strip()
        + "\n\nCONSULTA EXACTA DEL USUARIO:\n"
        + user_query.strip()
    )

    answer = None
    ultimo_error = None

    for mod in modelos:
        for intento in range(3):
            try:
                response = client.models.generate_content(
                    model=mod,
                    contents=prompt_completo,
                )
                if response and response.text:
                    answer = response.text
                    break
            except Exception as err:
                ultimo_error = err
                time.sleep(2.0)
        if answer:
            break

    if not answer:
        return None, None, str(ultimo_error)

    # Detección y extracción de bloque de gráfico <chart_json>
    chart_data = None
    match = re.search(r"<chart_json>\s*(\{.*?\})\s*</chart_json>", answer, re.DOTALL)
    if match:
        try:
            chart_data = json.loads(match.group(1))
            answer_clean = re.sub(r"<chart_json>.*?</chart_json>", "", answer, flags=re.DOTALL).strip()
        except Exception:
            answer_clean = answer
    else:
        answer_clean = answer

    return answer_clean, chart_data, None

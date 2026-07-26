# Módulo para generación de medios con IA (Imagen y Video)

import time
from typing import Optional

import requests
import streamlit as st


# NOTA DE SEGURIDAD (auditoría)
# `st.cache_data` es una caché GLOBAL del proceso, compartida entre sesiones y
# usuarios. Con `api_key` en la firma, la clave entraba en el hash de la caché
# y un usuario podía recibir el resultado generado con la clave de otro.
# El prefijo "_" excluye el argumento del hash (convención de Streamlit).
@st.cache_data(show_spinner=False, ttl=3600)
def generate_facade_image_fal(prompt: str, _api_key: str) -> str | None:
    """
    Llama a la API de Fal.ai (modelo Flux) para generar un render fotorrealista.
    """
    if not _api_key:
        return None
        
    url = "https://queue.fal.run/fal-ai/flux/schnell"
    headers = {
        "Authorization": f"Key {_api_key}",
        "Content-Type": "application/json"
    }
    
    # Optimizamos el prompt arquitectónico
    enhanced_prompt = f"Fotorrealismo, render arquitectónico, diseño exterior. {prompt}. Luz natural, día soleado, alta resolución, 8k, estilo moderno."
    
    payload = {
        "prompt": enhanced_prompt,
        "image_size": "landscape_16_9",
        "num_inference_steps": 4,
        "sync_mode": True # Para esperar a que devuelva la imagen sin necesidad de polling
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            images = data.get("images", [])
            if images and len(images) > 0:
                return images[0].get("url")
        else:
            print(f"Error Fal.ai: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Excepción Fal.ai: {e}")
        
    return None

@st.cache_data(show_spinner=False, ttl=3600)
def generate_video_luma(image_url: str, prompt: str, _api_key: str) -> str | None:
    """
    Llama a la API de Luma Dream Machine para generar un video cinematográfico 
    a partir de una imagen.
    """
    if not _api_key or not image_url:
        return None
        
    url = "https://api.lumalabs.ai/dream-machine/v1/generations"
    headers = {
        "Authorization": f"Bearer {_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": f"Slow cinematic drone shot panning around the modern house, sunny day, architectural showcase. {prompt}",
        "keyframes": {
            "frame0": {
                "type": "image",
                "url": image_url
            }
        }
    }
    
    try:
        # 1. Iniciar la generación
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code not in [200, 201]:
            print(f"Error Luma iniciar: {response.status_code} - {response.text}")
            return None
            
        data = response.json()
        generation_id = data.get("id")
        if not generation_id:
            return None
            
        # 2. Polling (Consultar el estado cada 5 segundos hasta que termine)
        # Nota: Luma puede tardar 1-2 minutos en procesar el video
        status_url = f"{url}/{generation_id}"
        max_attempts = 40 # Máximo ~3 minutos
        
        for _ in range(max_attempts):
            time.sleep(5)
            status_response = requests.get(status_url, headers=headers, timeout=15)
            if status_response.status_code == 200:
                status_data = status_response.json()
                state = status_data.get("state")
                
                if state == "completed":
                    assets = status_data.get("assets", {})
                    video_url = assets.get("video")
                    return video_url
                elif state == "failed":
                    print(f"Error Luma: La generación falló. {status_data.get('failure_reason')}")
                    return None
            else:
                print(f"Error consultando Luma: {status_response.status_code}")
                
        print("Luma timeout: El video tardó demasiado en generarse.")
        return None
        
    except Exception as e:
        print(f"Excepción Luma: {e}")
        return None

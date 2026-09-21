# Para desplegar en Render (o cualquier host que use Docker) -- Streamlit
# Community Cloud no necesita esto (lee requirements.txt/packages.txt
# solo), pero Render no permite apt-get en su entorno nativo de Python,
# así que aquí sí hace falta instalar Tesseract/poppler a mano (los usa
# inbody_ocr.py/estudios_parser.py para leer PDFs de InBody y estudios
# de laboratorio).
#
# Un solo Dockerfile sirve para las dos apps (dashboard_pacientes.py y
# conectar_garmin_web.py) -- cada servicio de Render elige cuál correr
# con su propio "Docker Command" (ver render.yaml), no hace falta un
# Dockerfile por app.

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Valor por default para pruebas locales (docker run sin más) -- en
# Render, cada servicio sobreescribe esto con su propio Docker Command
# (ver render.yaml).
CMD ["streamlit", "run", "dashboard_pacientes.py", "--server.port=8501", "--server.address=0.0.0.0"]

FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3-tk \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir customtkinter

COPY . . 

CMD ["python3", "iot_client.py"]
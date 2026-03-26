FROM python:3.9-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY . . 
EXPOSE 9998/udp
CMD ["python3", "iot_broker.py"]
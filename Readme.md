# 🌿 Smart Greenhouse Monitoring System

> **Projeto da disciplina TEC502 - Concorrência e Conectividade (UEFS)** \> Implementação de uma infraestrutura IoT robusta para monitoramento e controle autônomo de estufas inteligentes, utilizando uma arquitetura baseada no protocolo MQTT sobre TCP/IP.


## 📑 Sumário

  - [Sobre o Projeto](https://www.google.com/search?q=%23-sobre-o-projeto)
  - [Arquitetura e Componentes](https://www.google.com/search?q=%23-arquitetura-e-componentes)
  - [Estrutura de Diretórios](https://www.google.com/search?q=%23-estrutura-de-diret%C3%B3rios)
  - [Pacotes e Dependências](https://www.google.com/search?q=%23-pacotes-e-depend%C3%AAncias)
  - [Dockerization](https://www.google.com/search?q=%23-dockerization)
  - [Como Executar](https://www.google.com/search?q=%23-como-executar)
  - [Como Usar](https://www.google.com/search?q=%23-como-usar)


## 📖 Sobre o Projeto

O **Smart Greenhouse** é um sistema distribuído projetado para resolver problemas de monitoramento de microclima e automação agrícola. O núcleo do projeto é um **Broker MQTT customizado** que permite o desacoplamento total entre sensores e atuadores, garantindo escalabilidade e resiliência através de comunicação baseada em eventos.


## 🏗 Arquitetura e Componentes

O sistema é dividido em três pilares fundamentais, todos gerenciados via **Docker**:

1.  **🖥️ Broker (Serviço de Integração):** O "cérebro" do sistema que gerencia conexões e roteia mensagens.
2.  **📟 Dispositivos de Borda (Edge):** Simuladores de sensores (Temp, Umidade, Luz, Gás) e atuadores (Irrigação, Cortina).
3.  **📊 Dashboard (Aplicação Cliente):** Interface gráfica (IHM) para monitoramento e envio de comandos.


## 📂 Estrutura de Diretórios

O projeto está organizado de forma modular para facilitar a manutenção e a conteinerização individual:

```text
P01_iot_greenhouse/
├── broker/                 # Código fonte do Broker MQTT
│   ├── iot_broker.py       # Script principal do servidor
│   ├── aux.py              # Funções auxiliares de codificação
│   └── Dockerfile          # Configuração da imagem do Broker
├── client/                 # Aplicação Dashboard (IHM)
│   ├── iot_client.py       # Interface gráfica e lógica de rede
│   └── Dockerfile          # Configuração da imagem do Cliente
├── client_sensors/         # Simuladores de sensores
│   ├── humidity_sensor/
│   ├── temperature_sensor/
│   ├── gas_sensor/
│   └── light_sensor/       # Cada sensor possui seu script e Dockerfile
├── client_actuators/       # Simuladores de atuadores
│   ├── act_irrigation/
│   └── act_curtain/        # Cada atuador possui seu script e Dockerfile
├── assets/                 # Imagens e recursos do README
└── docker-compose.yml      # Arquivo de orquestração global
```



## 📦 Pacotes e Dependências

Para garantir a leveza e a portabilidade, o projeto utiliza exclusivamente bibliotecas nativas do **Python 3.12**, eliminando a necessidade de gerenciadores de pacotes externos em ambientes restritos:

  - `socket`: Comunicação TCP de baixo nível.
  - `threading`: Gerenciamento de múltiplas conexões simultâneas (concorrência).
  - `json`: Formatação e parsing de mensagens de telemetria.
  - `tkinter`: Utilizada no Dashboard para a interface gráfica (requer `python3-tk` no Linux).
  - `os`, `time`, `random`: Utilitários de sistema, tempo e simulação de dados.



## 🐳 Dockerization

Cada componente possui um **Dockerfile** otimizado baseado em `python:3.12-slim`. A configuração padrão segue este modelo:

```dockerfile
# Imagem base leve
FROM python:3.12-slim

# Variáveis de ambiente para logs em tempo real
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

# Exposição da porta (no caso do Broker)
EXPOSE 9998

# Comando de execução
CMD ["python", "script_principal.py"]
```

O arquivo `docker-compose.yml` orquestra o ecossistema, definindo variáveis de ambiente como `BROKER_IP` para que os sensores encontrem o serviço de integração automaticamente.


## 🚀 Como Executar

### 1\. Via Docker (Recomendado para Avaliação)

Certifique-se de ter o Docker e Docker Compose instalados e execute:

```bash
docker-compose up --build
```

Isso compilará todas as imagens e iniciará o broker, 4 sensores, 2 atuadores e o dashboard simultaneamente.

### 2\. Execução Manual

Se preferir executar localmente:

1.  Inicie o broker: `python broker/iot_broker.py`
2.  Inicie o dashboard: `python client/iot_client.py`
3.  Inicie os sensores/atuadores desejados.


## 🕹️ Como Usar

1.  **Handshake Inicial:** Ao iniciar, o Broker aguarda conexões. O Dashboard e os sensores realizam o `CONNECT` automaticamente.
2.  **Monitoramento:** Verifique os logs do Docker ou a interface do Dashboard para ver os valores de Humidade e Temperatura variando em tempo real.
3.  **Comandos:** No Dashboard, clique nos botões de controle para enviar comandos (ex: "Abrir Cortina"). O comando será encapsulado em um pacote `PUBLISH` e enviado ao atuador via Broker.
4.  **Teste de Falhas:** Interrompa um container de sensor (`docker stop <nome>`). O Broker detectará a falha via `Keep-Alive` e disparará o `Last Will` (LWT) para o Dashboard.

-----

### 👥 Desenvolvedor

  - **Yasmin Cordeiro de Souza Meira**
  - Disciplina: **TEC502 - Concorrência e Conectividade** (UEFS)


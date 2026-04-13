

# 🌿 Smart Greenhouse Monitoring System

> **Projeto da disciplina TEC502 - Concorrência e Conectividade (UEFS)** \> Implementação de uma infraestrutura IoT robusta para monitoramento e controle autônomo de estufas inteligentes, utilizando uma arquitetura baseada no protocolo MQTT sobre TCP/IP.





## 📑 Sumário

  - [Sobre o Projeto](https://www.google.com/search?q=%23-sobre-o-projeto)
  - [Arquitetura e Componentes](https://www.google.com/search?q=%23-arquitetura-e-componentes)
  - [Protocolo e Comunicação](https://www.google.com/search?q=%23-protocolo-e-comunica%C3%A7%C3%A3o)
  - [Como Executar](https://www.google.com/search?q=%23-como-executar)
  - [Funcionalidades de Concorrência e Conectividade](https://www.google.com/search?q=%23-funcionalidades-de-concorr%C3%AAncia-e-conectividade)



## 📖 Sobre o Projeto

O **Smart Greenhouse** é um sistema distribuído projetado para resolver problemas de monitoramento de microclima e automação agrícola. O núcleo do projeto é um **Broker MQTT customizado** que permite o desacoplamento total entre sensores e atuadores, garantindo escalabilidade e resiliência através de comunicação baseada em eventos.


## 🏗 Arquitetura e Componentes

O sistema é dividido em três pilares fundamentais, todos gerenciados via **Docker**:

### 1\. 🖥️ Broker (Serviço de Integração)

Localizado no diretório `/broker`.

  - **Papel:** Gerenciar conexões, processar o *handshake*, validar mensagens e realizar o roteamento dinâmico via tópicos.
  - **Tecnologia:** Python Nativo (Sockets e Threading).

### 2\. 📟 Dispositivos de Borda (Edge)

Simuladores de hardware localizados em `/client_sensors` e `/client_actuators`.

  - **Sensores:** Publicam telemetria (Temperatura, Umidade, Luminosidade e Gás) periodicamente.
  - **Atuadores:** Assinam tópicos de comando e executam ações (Irritação e Cortina).

### 3\. 📊 Dashboard (Aplicação Cliente)

Localizado em `/client`.

  - **Papel:** Interface gráfica (IHM) para monitoramento em tempo real e envio de comandos críticos.
  - **Tecnologia:** Python com biblioteca `Tkinter`.


## 📡 Protocolo e Comunicação

O sistema utiliza uma Unidade de Dados de Protocolo (PDU) binária otimizada:

  - **Encapsulamento:** Cabeçalhos binários seguidos de Payloads estruturados em **JSON**.
  - **Handshake:** Fluxo rigoroso de `CONNECT` e `CONNACK`.
  - **QoS:** Suporte resiliente aos níveis 0, 1 e 2 (com degradação graciosa).





## 🚀 Como Executar

A solução está totalmente "dockerizada" para facilitar a avaliação.

### Pré-requisitos

  - Docker instalado.
  - Docker Compose instalado.

### Passo a Passo

1.  Clone este repositório.
2.  No terminal, dentro da pasta raiz, execute:
    ```bash
    docker-compose up --build
    ```
3.  O Broker será iniciado na porta `9998` e os containers dos sensores e atuadores se conectarão automaticamente.


## ⚙️ Funcionalidades de Concorrência e Conectividade

Como requisito da disciplina **TEC502**, o projeto implementa conceitos avançados:

  * **Multithreading:** O Broker aloca uma thread independente para cada cliente, permitindo o processamento paralelo de dados de múltiplos sensores.
  * **Controle de Concorrência (Mutex):** Uso de `threading.Lock()` para garantir a atomicidade ao acessar as tabelas de roteamento globais.
  * **Keep-Alive:** Mecanismo de vigilância que detecta inatividade de sockets e limpa recursos do sistema.
  * **Last Will and Testament (LWT):** Mensagem de "testamento" disparada automaticamente pelo Broker caso um sensor sofra uma queda abrupta de energia/conexão.
  * **Resiliência TCP:** Tratamento de exceções como *Broken Pipe* e *Connection Reset* para evitar o crash do serviço de integração.

-----

### 👥 Autor

  - **Yasmin Cordeiro de Souza Meira** - [GitHub](https://www.google.com/search?q=https://github.com/SeuUsuarioAqui)
  - Projeto desenvolvido para a Universidade Estadual de Feira de Santana (UEFS).


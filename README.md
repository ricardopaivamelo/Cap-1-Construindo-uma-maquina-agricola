# Cap-1-Construindo-uma-maquina-agricola

## Visão Geral do Projeto

O FarmTech é um sistema de monitoramento agrícola que integra hardware (Arduino/ESP32) com software (Dashboard em Python) para coletar, visualizar e agir sobre dados cruciais para a agricultura. O objetivo é otimizar a irrigação e o manejo de nutrientes, utilizando leituras de sensores em tempo real e dados meteorológicos para tomadas de decisão inteligentes.

Este repositório contém a implementação do sistema de irrigação inteligente da FarmTech Solutions, que é baseado em dados de sensores. Ele inclui o código-fonte para o Dashboard em Python, que atua como a interface principal para o usuário, permitindo o monitoramento de sensores, o histórico de leituras, o controle da bomba de irrigação e a integração com dados meteorológicos externos.


## 🌟 Funcionalidades Principais

### Entrega 1: Sistema de Sensores e Controle com ESP32 (Hardware)

Esta entrega foca na implementação do sistema de sensores e controle utilizando um microcontrolador ESP32.

### Entrega 2: Armazenamento de Dados em Banco SQL com Python

Esta entrega consiste na implementação de um sistema para armazenar os dados coletados pelos sensores em um banco de dados SQL. O sistema é responsável por:

-   Receber dados simulados do monitor serial do ESP32.
    
-   Armazenar os dados em um banco de dados SQLite.
    
-   Implementar operações CRUD (Create, Read, Update, Delete).
    
-   Relacionar a estrutura do banco com o MER da Fase 2.
    

#### Estrutura do Banco de Dados

O banco de dados foi implementado utilizando SQLite e possui as seguintes tabelas principais:

-   **Tabela `AreaPlantio`**
    
    -   **Propósito:** Armazena informações sobre as áreas de plantio monitoradas.
        
    -   **Campos principais:** `ID_AreaPlantio` (PK), `NomeArea`, `TamanhoArea` (opcional), `LocalizacaoDescricao` (opcional).
        
-   **Tabela `Sensor`**
    
    -   **Propósito:** Registra os sensores instalados no sistema.
        
    -   **Campos principais:** `ID_Sensor` (PK), `TipoSensor` (Umidade, pH, Fosforo, Potassio), `ID_AreaPlantio` (FK), `DataInstalacao`, `StatusSensor` (Ativo, Inativo, Manutenção).
        
-   **Tabela `LeituraSensor`**
    
    -   **Propósito:** Armazena as leituras realizadas pelos sensores.
        
    -   **Campos principais:** `ID_Leitura` (PK), `ID_Sensor` (FK), `DataHoraLeitura`, `ValorLeitura`, `UnidadeMedida` (%, pH, bool).
        
-   **Tabela `AjusteRecurso`**
    
    -   **Propósito:** Registra os acionamentos da bomba de irrigação.
        
    -   **Campos principais:** `ID_Ajuste` (PK), `ID_AreaPlantio` (FK), `TipoAjuste` (Irrigacao, Nutriente), `DataHoraAjuste`, `QuantidadeAplicada`, `StatusBomba` (ligada/desligada), `ID_LeituraReferencia` (FK).
        

#### Relacionamento com o MER da Fase 2

A implementação atual mantém fidelidade ao MER desenvolvido na Fase 2, implementando os relacionamentos principais:

-   **AreaPlantio (1) : (N) Sensor**: Uma área pode ter vários sensores.
    
-   **Sensor (1) : (N) LeituraSensor**: Um sensor pode ter várias leituras.
    
-   **AreaPlantio (1) : (N) AjusteRecurso**: Uma área pode receber vários ajustes.
    
-   **LeituraSensor (1) : (N) AjusteRecurso**: Uma leitura pode gerar um ou mais ajustes.
    

As tabelas `Cultura` e `PlantioCultura` do MER original não foram implementadas nesta fase do projeto, pois o foco está na coleta e processamento dos dados dos sensores.

### 📊 Exemplo de Dados Armazenados (LeituraSensor)

Os dados abaixo foram gerados por sensores físicos (ou simulados) e representam registros reais do sistema armazenados no banco SQLite:

| DataHoraLeitura       | Sensor    | Valor | Unidade   |
|-----------------------|-----------|-------|-----------|
| 2025-05-20 08:30:00   | Umidade   | 35.7  | %         |
| 2025-05-20 08:30:00   | pH        | 6.5   | pH        |
| 2025-05-20 08:30:00   | Fósforo   | 1     | presente  |
| 2025-05-20 08:30:00   | Potássio  | 0     | presente  |

#### Operações CRUD Implementadas

O sistema implementa as seguintes operações CRUD:

-   **Create (Criação)**
    
    -   `inserir_leitura_sensor`: Registra uma nova leitura de sensor no banco.
        
    -   `registrar_acionamento_bomba`: Registra um acionamento da bomba de irrigação.
        
-   **Read (Leitura)**
    
    -   `obter_ultima_leitura_sensor`: Obtém a leitura mais recente de um sensor específico.
        
    -   `obter_leituras_por_periodo`: Obtém leituras em um intervalo de tempo.
        
    -   `obter_historico_bomba`: Obtém o histórico de acionamento da bomba.
        
-   **Update (Atualização)**
    
    -   `atualizar_status_sensor`: Atualiza o status de um sensor.
        
    -   `corrigir_leitura_sensor`: Corrige o valor de uma leitura (caso de erro).
        
-   **Delete (Exclusão)**
    
    -   `excluir_leitura`: Remove uma leitura específica do banco.
        
    -   `limpar_leituras_antigas`: Remove leituras anteriores a uma data específica.
        

### Projetos "Ir Além" (Em Desenvolvimento)

#### Ir Além 1: Dashboard em Python

Um dashboard para visualização dos dados coletados, utilizando bibliotecas como Streamlit ou Dash.

As funcionalidades principais do Dashboard incluem:

-   **Conexão Serial com Arduino:** Estabelece comunicação bidirecional com o microcontrolador Arduino para recebimento de dados de sensores e envio de comandos de controle.
    
-   **Monitoramento de Sensores em Tempo Real:** Exibe leituras atuais de Umidade do Solo, pH do Solo, Fósforo e Potássio.
    
-   **Lógica de Irrigação Inteligente:** Aciona a bomba automaticamente com base na umidade do solo e na presença de nutrientes.
    
-   **Banco de Dados SQLite:** Armazena todas as leituras de sensores e ações de controle de irrigação em um banco de dados local para análise histórica.
    
-   **Visualização de Histórico:** Apresenta um histórico tabular das leituras de sensores e ajustes de recursos.
    
-   **Gerenciamento de Dados:** Permite visualização e gestão de áreas de plantio e sensores cadastrados, com opções para adicionar, editar e excluir, recriar o banco de dados e exportar dados para CSV.
    
-   **Controle Manual da Bomba:** Permite ao usuário ligar ou desligar a bomba de irrigação manualmente através da interface.
    
-   **Simulador de Leituras:** Ferramenta integrada para testar a lógica do dashboard sem a necessidade de um hardware Arduino conectado, gerando dados aleatórios.
    
-   **Logging:** Registra eventos e erros em um arquivo `farmtech.log` para depuração e auditoria.
    

#### Ir Além 2: Integração com API Meteorológica

Integração com API pública de dados meteorológicos para ajustar a irrigação com base na previsão do tempo.

-   **Dados Meteorológicos (API Pública):** Integração com a **OpenWeatherMap API** para buscar Temperatura do Ar, Umidade do Ar e Previsão de Chuva (simplificada para os próximos 3 horas).
    
-   **Otimização:** Desliga a bomba se houver previsão de chuva, evitando desperdício de água e excesso de irrigação.
    

## ⚙️ Requisitos do Sistema

### Hardware

-   Placa Arduino compatível (Ex: ESP32, ESP8266, Arduino UNO)
    
-   Sensores: Umidade do solo, pH (ou LDR para simulação), Módulo de relé (para bomba), DHT22 (umidade e temperatura)
    
-   Bomba d'água (opcional, para testes reais)
    
-   Cabo USB para conexão entre Arduino e computador
    

### Software

-   **Python 3.x**
    
-   **Bibliotecas Python:**
    -   `pyserial`: Para comunicação serial com o Arduino.
        
    -   `requests`: Para integração com APIs web (OpenWeatherMap).
        
    -   `tkinter`: (Inclusa na instalação padrão do Python) Para a interface gráfica.
        
    -   `sqlite3`: (Inclusa na instalação padrão do Python) Para o banco de dados.
        
-   **IDE Arduino** para carregar o código no microcontrolador.
    
-   **Navegador de Banco de Dados SQLite** (opcional, mas recomendado para depuração, ex: [DB Browser for SQLite](https://sqlitebrowser.org/)).
    

## 🚀 Como Configurar e Executar

### 1. Preparação do Arduino

1.  **Carregue o Código Arduino:**
    -   Abra o arquivo `#include Arduino.h.txt` na IDE do Arduino.
        
    -   Conecte seu Arduino ao computador.
        
    -   Selecione a placa e a porta serial corretas em `Ferramentas > Placa` e `Ferramentas > Porta`.
        
    -   Clique em `Carregar` para transferir o código para o Arduino.
        
    -   Certifique-se de que o baud rate configurado (`Serial.begin(115200);`) corresponde ao do código Python.
        

### 2. Configuração do Dashboard Python

1.  **Clone ou Baixe o Repositório:** Obtenha o arquivo `farmtech_app_v2.py` (ou como você o nomeou).
    
2.  **Instale as Dependências Python:** Abra seu terminal ou prompt de comando e execute:
    
    Bash
    
    ```
    pip install pyserial requests
    
    ```
    
3.  **Obtenha sua API Key do OpenWeatherMap:**
    -   Vá para [https://openweathermap.org/api](https://openweathermap.org/api) e crie uma conta gratuita.
        
    -   Na seção "API keys" do seu perfil, copie sua chave da API.
        
4.  **Configure o Código Python:**
    -   Abra o arquivo Python (`farmtech_app_v2.py`) em um editor de texto.
        
    -   Localize as linhas de configuração da API e **substitua `'SUA_CHAVE_AQUI'` pela sua chave real**:
        
        Python
        
        ```
        OPENWEATHER_API_KEY = 'SUA_CHAVE_AQUI'
        CITY_NAME = 'Uberaba' # Altere para a sua cidade
        COUNTRY_CODE = 'br'   # Altere para o código do seu país (ISO 3166)
        UNITS = 'metric'      # 'metric' para Celsius, 'imperial' para Fahrenheit
        
        ```
        
    -   Você pode ajustar `CITY_NAME` e `COUNTRY_CODE` conforme sua localização.
        
5.  **Execute o Dashboard:** Navegue até o diretório onde o arquivo Python está salvo e execute:
    
    Bash
    
    ```
    python farmtech_app_v2.py
    
    ```
    

### 3. Operação do Dashboard

1.  **Conexão Serial:**
    -   Na interface, clique em "Atualizar" para listar as portas seriais disponíveis.
        
    -   Selecione a porta correspondente ao seu Arduino no menu suspenso.
        
    -   Clique em "Conectar". O status na parte inferior da janela deve mudar para "Conectado...".
        
2.  **Visualização de Dados:**
    -   Os valores de Umidade do Solo, pH, Fósforo e Potássio serão atualizados em tempo real no painel "Leituras Atuais".
        
    -   Os dados meteorológicos (Temperatura, Umidade do Ar, Previsão Chuva) serão atualizados periodicamente no painel "Dados Meteorológicos".
        
3.  **Histórico e Banco de Dados:**
    -   O painel "Histórico de Dados" exibirá as últimas leituras registradas.
        
    -   Use os botões na seção "Controle" para "Ver Leituras", "Ver Ajustes", "Ver Áreas", "Ver Sensores" e gerenciar o banco de dados.
        
4.  **Controle da Bomba:**
    -   A bomba será acionada automaticamente com base na lógica de irrigação inteligente.
        
    -   Você pode ligar/desligar manualmente usando os botões "Ligar Bomba" e "Desligar Bomba".
        

## 🐛 Depuração e Resolução de Problemas

-   **`farmtech.log`:** Este arquivo, localizado na mesma pasta do script Python, registra informações importantes e erros. Consulte-o para diagnosticar problemas de conexão serial, API ou banco de dados.
    
-   **API Key:** Se os dados meteorológicos não aparecerem, verifique se sua `OPENWEATHER_API_KEY` está correta e ativa. Novas chaves podem levar um tempo para serem ativadas.
    
-   **Banco de Dados Vazio:** Se as tabelas de histórico e leituras estiverem vazias, certifique-se de que o Arduino está enviando dados (ou o simulador está sendo usado) e que o programa Python está conectado e processando-os. O botão "Recriar Banco" apaga todos os dados existentes.
    
-   **Conectividade:** Verifique sua conexão com a internet se houver erros ao buscar dados meteorológicos.
    
## Conclusão

O sistema FarmTech representa um avanço significativo na agricultura inteligente, integrando hardware e software para otimizar a irrigação e o manejo de nutrientes de forma eficiente e sustentável. A arquitetura modular do projeto, dividida em entregas claras e com projetos "Ir Além" em desenvolvimento, demonstra um planejamento robusto para futuras expansões e aprimoramentos.

A implementação da Entrega 2, focada no armazenamento de dados em banco SQL com Python, é um pilar fundamental, garantindo a persistência e a integridade das informações coletadas pelos sensores. As operações CRUD detalhadas e a fidelidade ao MER da Fase 2 asseguram que os dados estejam bem estruturados e acessíveis para análises históricas e tomadas de decisão.

Os projetos "Ir Além", como o Dashboard em Python e a integração com APIs meteorológicas, elevam o FarmTech a um novo patamar, proporcionando uma interface intuitiva para visualização de dados em tempo real e uma lógica de irrigação preditiva que considera as condições climáticas. Isso não apenas otimiza o uso da água e dos nutrientes, mas também contribui para uma agricultura mais resiliente e produtiva.

Em suma, o FarmTech é uma solução completa e escalável, pronta para auxiliar agricultores na transição para práticas agrícolas mais inteligentes, baseadas em dados e ambientalmente conscientes. O projeto demonstra o potencial da tecnologia para transformar o setor agrícola, promovendo a eficiência e a sustentabilidade.

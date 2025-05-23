import sqlite3
import os
import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import serial
import serial.tools.list_ports
import threading
import time
import logging
import csv
import random
import requests 

# --- Configurações da API OpenWeatherMap ---
OPENWEATHER_API_KEY = 'c0bd680839dbd485cf3c3a16a93dbfa3'
CITY_NAME = 'Uberaba'
COUNTRY_CODE = 'br'
UNITS = 'metric' 

# Configuração de logging para debug
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='farmtech.log'
)
logger = logging.getLogger('FarmTech')

# Funções do banco de dados
def criar_banco_dados():
    """Função para criar o banco de dados e suas tabelas."""
    # Verificar se o banco já existe
    if os.path.exists('farmtech_db.sqlite'):
        os.remove('farmtech_db.sqlite')  # Remove o banco existente para criar do zero
        logger.info("Banco de dados existente removido.")
    
    # Criar nova conexão
    conn = sqlite3.connect('farmtech_db.sqlite')
    cursor = conn.cursor()
    
    logger.info("Criando tabelas...")
    
    # Tabela AreaPlantio
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS AreaPlantio (
        ID_AreaPlantio INTEGER PRIMARY KEY,
        NomeArea TEXT NOT NULL
    )
    ''')
    
    # Tabela Sensor
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Sensor (
        ID_Sensor INTEGER PRIMARY KEY,
        TipoSensor TEXT NOT NULL,
        ID_AreaPlantio INTEGER,
        StatusSensor TEXT DEFAULT 'Ativo',
        FOREIGN KEY (ID_AreaPlantio) REFERENCES AreaPlantio(ID_AreaPlantio)
    )
    ''')
    
    # Tabela LeituraSensor
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS LeituraSensor (
        ID_Leitura INTEGER PRIMARY KEY,
        ID_Sensor INTEGER,
        DataHoraLeitura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ValorLeitura REAL NOT NULL,
        UnidadeMedida TEXT,
        FOREIGN KEY (ID_Sensor) REFERENCES Sensor(ID_Sensor)
    )
    ''')
    
    # Tabela AjusteRecurso
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS AjusteRecurso (
        ID_Ajuste INTEGER PRIMARY KEY,
        ID_AreaPlantio INTEGER,
        TipoAjuste TEXT DEFAULT 'Irrigacao',
        DataHoraAjuste TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        StatusBomba BOOLEAN,
        ID_LeituraReferencia INTEGER,
        FOREIGN KEY (ID_AreaPlantio) REFERENCES AreaPlantio(ID_AreaPlantio),
        FOREIGN KEY (ID_LeituraReferencia) REFERENCES LeituraSensor(ID_Leitura)
    )
    ''')
    
    logger.info("Tabelas criadas com sucesso!")
    
    # Inserir dados de teste
    logger.info("Inserindo dados iniciais para teste...")
    
    # Inserir área de plantio padrão
    cursor.execute("INSERT INTO AreaPlantio (ID_AreaPlantio, NomeArea) VALUES (1, 'Área Teste')")
    
    # Inserir sensores padrão
    sensores = [
        (1, 'Umidade', 1),
        (2, 'pH', 1),
        (3, 'Fosforo', 1),
        (4, 'Potassio', 1)
    ]
    
    cursor.executemany("INSERT INTO Sensor (ID_Sensor, TipoSensor, ID_AreaPlantio) VALUES (?, ?, ?)", sensores)
    
    conn.commit()
    logger.info("Dados iniciais inseridos com sucesso!")
    
    conn.close()
    logger.info("Banco de dados criado com sucesso!")
    return True

def inserir_leitura_sensor(id_sensor, valor, unidade):
    """Função para inserir uma nova leitura de sensor no banco de dados."""
    try:
        conn = sqlite3.connect('farmtech_db.sqlite')
        cursor = conn.cursor()
        
        # Inserir leitura
        data_hora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO LeituraSensor (ID_Sensor, DataHoraLeitura, ValorLeitura, UnidadeMedida) 
            VALUES (?, ?, ?, ?)
        """, (id_sensor, data_hora, valor, unidade))
        
        # Obter o ID da leitura inserida
        leitura_id = cursor.lastrowid
        
        # Se for sensor de umidade (ID=1) e valor abaixo do limite, acionar bomba
        # A lógica de acionamento inteligente agora está em atualizar_dados_sensores
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erro ao inserir leitura: {str(e)}")
        return False

# Classe para lidar com a comunicação serial
class ArduinoSerial:
    def __init__(self, callback_status=None, callback_data=None):
        self.serial = None
        self.running = False
        self.porta = None
        self.baudrate = 115200
        self.thread = None
        self.callback_status = callback_status
        self.callback_data = callback_data
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.retry_interval = 2  
        self.last_data_time = None
        self.watchdog_thread = None
        self.error_count = 0
    
    def listar_portas(self):
        """Lista as portas seriais disponíveis."""
        portas = [port.device for port in serial.tools.list_ports.comports()]
        logger.info(f"Portas disponíveis: {portas}")
        return portas
    
    def conectar(self, porta, baudrate=115200):
        """Conecta à porta serial especificada."""
        try:
            self.porta = porta
            self.baudrate = baudrate
            self.serial = serial.Serial(porta, baudrate, timeout=1)
            self.running = True
            self.reconnect_attempts = 0
            self.error_count = 0
            self.last_data_time = datetime.datetime.now()
            
            # Iniciar thread para leitura contínua
            self.thread = threading.Thread(target=self.ler_continuamente)
            self.thread.daemon = True
            self.thread.start()
            
            # Iniciar watchdog para monitorar a conexão
            self.watchdog_thread = threading.Thread(target=self.watchdog_monitor)
            self.watchdog_thread.daemon = True
            self.watchdog_thread.start()
            
            if self.callback_status:
                self.callback_status(f"Conectado à porta {porta} com sucesso")
            logger.info(f"Conectado à porta {porta} com sucesso")
            return True
        except Exception as e:
            if self.callback_status:
                self.callback_status(f"Erro ao conectar: {str(e)}")
            logger.error(f"Erro ao conectar à porta {porta}: {str(e)}")
            return False
    
    def desconectar(self):
        """Desconecta da porta serial."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        
        if self.serial and self.serial.is_open:
            self.serial.close()
            if self.callback_status:
                self.callback_status("Desconectado")
            logger.info("Desconectado da porta serial")
            return True
        return False
    
    def watchdog_monitor(self):
        """Thread que monitora se a conexão está funcionando corretamente."""
        while self.running:
            try:
                # Se não recebeu dados nos últimos 10 segundos, tenta reconectar
                time_since_last = (datetime.datetime.now() - self.last_data_time).total_seconds()
                if time_since_last > 10:
                    logger.warning(f"Watchdog: sem dados há {time_since_last} segundos")
                    if self.callback_status:
                        self.callback_status(f"Alerta: sem dados há {time_since_last} segundos")
                    
                # Se o problema persistir por muito tempo, tenta reconectar
                if time_since_last > 30:
                    logger.warning("Watchdog: tentando reconectar devido à inatividade")
                    self.tentar_reconectar()
            except Exception as e:
                logger.error(f"Erro no watchdog: {str(e)}")
            
            time.sleep(5)  # Verifica a cada 5 segundos
    
    def tentar_reconectar(self):
        """Tenta reconectar à porta serial após uma falha."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(f"Número máximo de tentativas de reconexão atingido ({self.max_reconnect_attempts})")
            if self.callback_status:
                self.callback_status(f"Falha ao reconectar após {self.max_reconnect_attempts} tentativas")
            return False
        
        self.reconnect_attempts += 1
        logger.info(f"Tentativa de reconexão {self.reconnect_attempts}/{self.max_reconnect_attempts}")
        
        if self.callback_status:
            self.callback_status(f"Tentando reconectar ({self.reconnect_attempts}/{self.max_reconnect_attempts})...")
        
        # Fechar conexão antiga
        if self.serial and self.serial.is_open:
            try:
                self.serial.close()
            except:
                pass
        
        # Esperar um pouco antes de tentar novamente
        time.sleep(self.retry_interval)
        
        # Tentar abrir nova conexão
        try:
            self.serial = serial.Serial(self.porta, self.baudrate, timeout=1)
            logger.info(f"Reconectado com sucesso à porta {self.porta}")
            if self.callback_status:
                self.callback_status(f"Reconectado com sucesso à porta {self.porta}")
            self.last_data_time = datetime.datetime.now()
            self.reconnect_attempts = 0
            return True
        except Exception as e:
            logger.error(f"Falha na tentativa de reconexão: {str(e)}")
            if self.callback_status:
                self.callback_status(f"Falha na tentativa de reconexão: {str(e)}")
            return False
    
    def ler_continuamente(self):
        """Função executada em thread para ler dados continuamente."""
        while self.running:
            try:
                if self.serial and self.serial.is_open:
                    linha = self.serial.readline().decode('utf-8').strip()
                    if linha:
                        # Atualiza o timestamp do último dado recebido
                        self.last_data_time = datetime.datetime.now()
                        self.error_count = 0  # Reseta contador de erros
                        
                        # Processar os dados recebidos (formato: P,K,pH,humidity)
                        self.processar_dados(linha)
                time.sleep(0.1)  # Pequena pausa para não sobrecarregar
            except serial.SerialException as e:
                # Erro na comunicação serial - pode ser uma desconexão
                self.error_count += 1
                logger.error(f"Erro serial na leitura: {str(e)}")
                if self.callback_status:
                    self.callback_status(f"Erro na leitura: {str(e)}")
                
                if self.error_count > 3:  # Após vários erros, tenta reconectar
                    self.tentar_reconectar()
                    
                time.sleep(1)  # Pausa maior em caso de erro
            except UnicodeDecodeError as e:
                # Erro de decodificação - dados corrompidos
                logger.warning(f"Erro de decodificação: {str(e)}")
                time.sleep(0.1)
            except Exception as e:
                # Outros erros
                logger.error(f"Erro na leitura: {str(e)}")
                if self.callback_status:
                    self.callback_status(f"Erro na leitura: {str(e)}")
                time.sleep(1)  # Pausa maior em caso de erro
    
    def processar_dados(self, linha):
        """Processa os dados recebidos do Arduino."""
        try:
            dados = linha.split(',')
            if len(dados) == 4:
                try:
                    has_p = bool(int(dados[0]))
                    has_k = bool(int(dados[1]))
                    ph_value = float(dados[2])
                    humidity_solo = float(dados[3]) # Renomeado para evitar conflito com umidade do ar
                    
                    # Verificar dados inválidos
                    if ph_value < 0 or ph_value > 14 or humidity_solo < 0 or humidity_solo > 100:
                        logger.warning(f"Dados inválidos recebidos: {linha}")
                        return
                    
                    # Inserir no banco de dados
                    # Umidade do solo (sensor ID=1)
                    inserir_leitura_sensor(1, humidity_solo, '%')
                    
                    # pH (sensor ID=2)
                    inserir_leitura_sensor(2, ph_value, 'pH')
                    
                    # Fósforo (sensor ID=3) - Convertido para valor numérico (0 ou 1)
                    inserir_leitura_sensor(3, 1 if has_p else 0, 'presente')
                    
                    # Potássio (sensor ID=4) - Convertido para valor numérico (0 ou 1)
                    inserir_leitura_sensor(4, 1 if has_k else 0, 'presente')
                    
                    logger.info(f"Dados recebidos e salvos: Umidade_Solo={humidity_solo}%, pH={ph_value}, P={has_p}, K={has_k}")
                    if self.callback_status:
                        self.callback_status(f"Dados recebidos e salvos: Umidade_Solo={humidity_solo}%, pH={ph_value}, P={has_p}, K={has_k}")
                    
                    # Atualizar interface (passando dados do sensor e não a umidade do ar da API)
                    if self.callback_data:
                        self.callback_data(has_p, has_k, ph_value, humidity_solo)
                        
                except ValueError as e:
                    # Erro na conversão dos dados
                    logger.warning(f"Erro ao converter dados: {str(e)}, linha: {linha}")
            else:
                # Formato de dados inesperado
                logger.warning(f"Formato de dados inesperado: {linha}")
        except Exception as e:
            logger.error(f"Erro ao processar dados: {str(e)}")
            if self.callback_status:
                self.callback_status(f"Erro ao processar dados: {str(e)}")
    
    def enviar_comando(self, comando):
        """Envia um comando para o Arduino."""
        try:
            if self.serial and self.serial.is_open:
                self.serial.write(f"{comando}\n".encode('utf-8'))
                logger.info(f"Comando enviado: {comando}")
                if self.callback_status:
                    self.callback_status(f"Comando enviado: {comando}")
                return True
            else:
                logger.warning("Tentativa de enviar comando com porta fechada")
                return False
        except Exception as e:
            logger.error(f"Erro ao enviar comando: {str(e)}")
            return False

# Classe para a interface gráfica
class FarmTechApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FarmTech - Sistema de Monitoramento")
        self.root.geometry("1200x700") 
        
        
        try:
            self.root.iconbitmap("farmtech_icon.ico")
        except:
            pass  
        
        # Instanciar comunicação serial
        self.arduino = ArduinoSerial(
            callback_status=self.atualizar_status,
            callback_data=self.atualizar_dados_sensores
        )
        
        # Variáveis para armazenar dados atuais do sensor
        self.umidade_solo_var = tk.StringVar(value="-- %") 
        self.ph_var = tk.StringVar(value="--")
        self.fosforo_var = tk.StringVar(value="Não")
        self.potassio_var = tk.StringVar(value="Não")
        self.status_var = tk.StringVar(value="Não conectado")
        self.bomba_status_var = tk.StringVar(value="Desligada")

        # Variáveis para armazenar dados da API meteorológica
        self.temp_api_var = tk.StringVar(value="-- °C")
        self.humid_api_var = tk.StringVar(value="-- %")
        self.rain_forecast_var = tk.StringVar(value="--")
        
        # Últimos dados meteorológicos obtidos da API
        self.current_api_temp = None
        self.current_api_humidity = None
        self.current_api_rain_forecast = None
        
        # Histórico de dados para gráficos
        self.historico_umidade_solo = [] 
        self.historico_ph = []
        self.timestamps = []
        
        # Criar componentes da interface
        self.create_widgets()
        
        # Verificar se o banco de dados existe
        if not os.path.exists('farmtech_db.sqlite'):
            messagebox.showinfo("Informação", "Banco de dados não encontrado. Criando novo banco...")
            criar_banco_dados()
        
        # Configurar periodicidade de atualização da interface e dados da API
        self.root.after(1000, self.atualizar_interface)
        # Buscar dados meteorológicos a cada 5 minutos (300000 ms)
        self.root.after(1000, self.fetch_weather_data_threaded) # Primeira chamada logo no início

    def create_widgets(self):
        # Frame principal com divisão em painéis
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # ===== Painel de controle (esquerda) =====
        control_frame = ttk.LabelFrame(main_frame, text="Controle")
        control_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5, expand=False)
        
        # Controles de conexão serial
        ttk.Label(control_frame, text="Conexão Serial").grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        self.porta_combo = ttk.Combobox(control_frame, width=15)
        self.porta_combo.grid(row=1, column=0, padx=5, pady=5)
        self.atualizar_portas()
        
        ttk.Button(control_frame, text="Atualizar", command=self.atualizar_portas).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Button(control_frame, text="Conectar", command=self.conectar_arduino).grid(row=2, column=0, padx=5, pady=5)
        ttk.Button(control_frame, text="Desconectar", command=self.desconectar_arduino).grid(row=2, column=1, padx=5, pady=5)
        
        # Controles do banco de dados
        ttk.Separator(control_frame, orient='horizontal').grid(row=3, column=0, columnspan=2, sticky='ew', padx=5, pady=10)
        
        ttk.Label(control_frame, text="Banco de Dados").grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        ttk.Button(control_frame, text="Ver Áreas", command=self.mostrar_areas).grid(row=5, column=0, padx=5, pady=5, sticky='ew')
        ttk.Button(control_frame, text="Ver Sensores", command=self.mostrar_sensores).grid(row=5, column=1, padx=5, pady=5, sticky='ew')
        
        ttk.Button(control_frame, text="Ver Leituras", command=self.mostrar_leituras).grid(row=6, column=0, padx=5, pady=5, sticky='ew')
        ttk.Button(control_frame, text="Ver Ajustes", command=self.mostrar_ajustes).grid(row=6, column=1, padx=5, pady=5, sticky='ew')
        
        ttk.Button(control_frame, text="Recriar Banco", command=self.recriar_banco).grid(row=7, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        
        # Botão para exportar dados
        ttk.Separator(control_frame, orient='horizontal').grid(row=8, column=0, columnspan=2, sticky='ew', padx=5, pady=10)
        ttk.Button(control_frame, text="Exportar Dados", command=self.exportar_dados).grid(row=9, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        
        # Botão para limpar dados 
        ttk.Button(control_frame, text="Limpar Histórico", command=self.limpar_historico).grid(row=10, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        
        # Simulador de leitura para testes sem Arduino
        ttk.Separator(control_frame, orient='horizontal').grid(row=11, column=0, columnspan=2, sticky='ew', padx=5, pady=10)
        ttk.Label(control_frame, text="Simulador").grid(row=12, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Button(control_frame, text="Simular Leitura", command=self.simular_leitura).grid(row=13, column=0, columnspan=2, padx=5, pady=5, sticky='ew')
        
        # Controle manual da bomba
        ttk.Separator(control_frame, orient='horizontal').grid(row=14, column=0, columnspan=2, sticky='ew', padx=5, pady=10)
        ttk.Label(control_frame, text="Controle Manual").grid(row=15, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        ttk.Button(control_frame, text="Ligar Bomba", command=lambda: self.controlar_bomba(True)).grid(row=16, column=0, padx=5, pady=5, sticky='ew')
        ttk.Button(control_frame, text="Desligar Bomba", command=lambda: self.controlar_bomba(False)).grid(row=16, column=1, padx=5, pady=5, sticky='ew')
        
        # ===== Dashboard principal (direita) =====
        dashboard_frame = ttk.Frame(main_frame)
        dashboard_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Painel de leituras atuais
        readings_frame = ttk.LabelFrame(dashboard_frame, text="Leituras Atuais")
        readings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Grid de leituras de sensores
        ttk.Label(readings_frame, text="Umidade Solo:").grid(row=0, column=0, padx=15, pady=5, sticky=tk.W)
        ttk.Label(readings_frame, textvariable=self.umidade_solo_var, font=('Arial', 12, 'bold')).grid(row=0, column=1, padx=15, pady=5, sticky=tk.W)
        
        ttk.Label(readings_frame, text="pH:").grid(row=0, column=2, padx=15, pady=5, sticky=tk.W)
        ttk.Label(readings_frame, textvariable=self.ph_var, font=('Arial', 12, 'bold')).grid(row=0, column=3, padx=15, pady=5, sticky=tk.W)
        
        ttk.Label(readings_frame, text="Fósforo:").grid(row=1, column=0, padx=15, pady=5, sticky=tk.W)
        ttk.Label(readings_frame, textvariable=self.fosforo_var, font=('Arial', 12, 'bold')).grid(row=1, column=1, padx=15, pady=5, sticky=tk.W)
        
        ttk.Label(readings_frame, text="Potássio:").grid(row=1, column=2, padx=15, pady=5, sticky=tk.W)
        ttk.Label(readings_frame, textvariable=self.potassio_var, font=('Arial', 12, 'bold')).grid(row=1, column=3, padx=15, pady=5, sticky=tk.W)
        
        ttk.Label(readings_frame, text="Status Bomba:").grid(row=2, column=0, padx=15, pady=5, sticky=tk.W)
        self.bomba_label = ttk.Label(readings_frame, textvariable=self.bomba_status_var, font=('Arial', 12, 'bold'))
        self.bomba_label.grid(row=2, column=1, padx=15, pady=5, sticky=tk.W)

        # Painel de dados meteorológicos
        weather_frame = ttk.LabelFrame(dashboard_frame, text=f"Dados Meteorológicos - {CITY_NAME}")
        weather_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(weather_frame, text="Temperatura:").grid(row=0, column=0, padx=15, pady=5, sticky=tk.W)
        ttk.Label(weather_frame, textvariable=self.temp_api_var, font=('Arial', 12, 'bold')).grid(row=0, column=1, padx=15, pady=5, sticky=tk.W)

        ttk.Label(weather_frame, text="Umidade Ar:").grid(row=0, column=2, padx=15, pady=5, sticky=tk.W)
        ttk.Label(weather_frame, textvariable=self.humid_api_var, font=('Arial', 12, 'bold')).grid(row=0, column=3, padx=15, pady=5, sticky=tk.W)
        
        ttk.Label(weather_frame, text="Previsão Chuva (próx. 3h):").grid(row=1, column=0, padx=15, pady=5, sticky=tk.W)
        ttk.Label(weather_frame, textvariable=self.rain_forecast_var, font=('Arial', 12, 'bold')).grid(row=1, column=1, columnspan=3, padx=15, pady=5, sticky=tk.W)
        
        # Tabela para exibição de dados
        table_frame = ttk.LabelFrame(dashboard_frame, text="Histórico de Dados")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview para histórico
        self.tree = ttk.Treeview(table_frame)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        # Configuração padrão da tabela
        self.tree["columns"] = ("timestamp", "sensor", "valor", "unidade")
        self.tree.column("#0", width=0, stretch=tk.NO)
        self.tree.column("timestamp", anchor=tk.W, width=150)
        self.tree.column("sensor", anchor=tk.W, width=100)
        self.tree.column("valor", anchor=tk.E, width=80)
        self.tree.column("unidade", anchor=tk.W, width=80)
        
        self.tree.heading("#0", text="", anchor=tk.CENTER)
        self.tree.heading("timestamp", text="Data/Hora", anchor=tk.CENTER)
        self.tree.heading("sensor", text="Sensor", anchor=tk.CENTER)
        self.tree.heading("valor", text="Valor", anchor=tk.CENTER)
        self.tree.heading("unidade", text="Unidade", anchor=tk.CENTER)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # Barra de status
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Carregar últimas leituras
        self.carregar_ultimas_leituras()

    def atualizar_interface(self):
        """Atualiza a interface periodicamente."""
        # Verificar status da conexão
        if self.arduino.serial and self.arduino.serial.is_open:
            if (datetime.datetime.now() - self.arduino.last_data_time).total_seconds() > 10:
                self.status_bar.configure(background="yellow")
            else:
                self.status_bar.configure(background="lightgreen")
        else:
            self.status_bar.configure(background="lightgray")
        
        # Reagendar a próxima atualização
        self.root.after(1000, self.atualizar_interface)

    def atualizar_portas(self):
        """Atualiza a lista de portas seriais disponíveis."""
        portas = self.arduino.listar_portas()
        self.porta_combo['values'] = portas
        if portas:
            self.porta_combo.current(0)
        self.status_var.set(f"Portas disponíveis: {len(portas)}")
    
    def conectar_arduino(self):
        """Conecta ao Arduino na porta selecionada."""
        porta = self.porta_combo.get()
        if porta:
            if self.arduino.conectar(porta):
                self.status_var.set(f"Conectado à porta {porta}")
            else:
                messagebox.showerror("Erro", f"Não foi possível conectar à porta {porta}")
    
    def desconectar_arduino(self):
        """Desconecta do Arduino."""
        if self.arduino.desconectar():
            self.status_var.set("Desconectado")
        else:
            messagebox.showerror("Erro", "Não foi possível desconectar")
    
    def atualizar_status(self, mensagem):
        """Callback para atualizar a barra de status."""
        self.status_var.set(mensagem)
    
    def atualizar_dados_sensores(self, fosforo, potassio, ph, umidade_solo):
        """Callback para atualizar os dados dos sensores na interface e aplicar lógica de irrigação."""
        
        # Atualizar as variáveis de display dos sensores
        self.umidade_solo_var.set(f"{umidade_solo:.1f} %")
        self.ph_var.set(f"{ph:.2f}")
        self.fosforo_var.set("Sim" if fosforo else "Não")
        self.potassio_var.set("Sim" if potassio else "Não")
        
        # Adicionar ao histórico (limitando a 100 pontos para performance)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.timestamps.append(timestamp)
        self.historico_umidade_solo.append(umidade_solo)
        self.historico_ph.append(ph)
        
        # Limitar o tamanho do histórico para evitar uso excessivo de memória
        if len(self.timestamps) > 100:
            self.timestamps.pop(0)
            self.historico_umidade_solo.pop(0)
            self.historico_ph.pop(0)
        
        # Adicionar as leituras ao TreeView (histórico)
        self.adicionar_leitura_tabela("Umidade Solo", umidade_solo, "%")
        self.adicionar_leitura_tabela("pH", ph, "pH")
        self.adicionar_leitura_tabela("Fósforo", "Presente" if fosforo else "Ausente", "")
        self.adicionar_leitura_tabela("Potássio", "Presente" if potassio else "Ausente", "")
        
        # --- Lógica de Irrigação Aprimorada com Dados Meteorológicos ---
        # Umidade do solo baixa E (tem fósforo OU potássio)
        need_irrigation_based_on_soil = (umidade_solo < 40.0) and (fosforo or potassio)
        
        # Previsão de chuva nos próximos 30 minutos (ajuste conforme a API)
        # O OpenWeatherMap API One Call por padrão fornece previsão de chuva
        # nos próximos 1h e 3h. "Rain" no current_weather não significa chuva atual,
        # mas a quantidade de chuva nas últimas 1h. Para previsão, é preciso consultar o endpoint /forecast
        # Para simplificar aqui, vamos considerar "chuvoso" como indicativo para não irrigar.
        # Você pode refinar isso consultando o /forecast API do OpenWeatherMap.
        will_rain = (self.current_api_rain_forecast == "Chuva prevista")
        
        if need_irrigation_based_on_soil and not will_rain:
            self.bomba_status_var.set("Ligada")
            self.bomba_label.configure(foreground="green")
            # Enviar comando para ligar bomba se o Arduino estiver conectado
            if self.arduino.serial and self.arduino.serial.is_open:
                self.arduino.enviar_comando("PUMP_ON")
        else:
            self.bomba_status_var.set("Desligada")
            self.bomba_label.configure(foreground="red")
            # Enviar comando para desligar bomba se necessário
            if self.arduino.serial and self.arduino.serial.is_open:
                self.arduino.enviar_comando("PUMP_OFF")
            if will_rain:
                self.status_var.set("Bomba desligada: Chuva prevista.")
            elif not need_irrigation_based_on_soil:
                self.status_var.set("Bomba desligada: Umidade do solo ok ou nutrientes ausentes.")
    
    def adicionar_leitura_tabela(self, tipo_sensor, valor, unidade):
        """Adiciona uma nova leitura na tabela de histórico."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Limitar quantidade de linhas na tabela (máx 100)
        if len(self.tree.get_children()) >= 100:
            self.tree.delete(self.tree.get_children()[0])
        
        # Inserir nova leitura no topo
        self.tree.insert('', 0, values=(timestamp, tipo_sensor, valor, unidade))
    
    def carregar_ultimas_leituras(self):
        """Carrega as últimas leituras do banco de dados para exibir na interface."""
        try:
            conn = sqlite3.connect('farmtech_db.sqlite')
            cursor = conn.cursor()
            
            # Limpa a tabela atual
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Consulta para obter as últimas 50 leituras
            cursor.execute("""
                SELECT ls.DataHoraLeitura, s.TipoSensor, ls.ValorLeitura, ls.UnidadeMedida
                FROM LeituraSensor ls
                JOIN Sensor s ON ls.ID_Sensor = s.ID_Sensor
                ORDER BY ls.DataHoraLeitura DESC
                LIMIT 50
            """)
            
            # Preencher a tabela com os dados
            for row in cursor.fetchall():
                self.tree.insert('', 'end', values=row)
            
            # Consulta para verificar o status atual da bomba
            cursor.execute("""
                SELECT StatusBomba FROM AjusteRecurso
                ORDER BY DataHoraAjuste DESC
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            if result:
                status_bomba = result[0]
                self.bomba_status_var.set("Ligada" if status_bomba else "Desligada")
                self.bomba_label.configure(foreground="green" if status_bomba else "red")
            
            conn.close()
            self.status_var.set("Últimas leituras carregadas com sucesso")
        except Exception as e:
            logger.error(f"Erro ao carregar últimas leituras: {str(e)}")
            self.status_var.set(f"Erro ao carregar leituras: {str(e)}")
    
    def mostrar_areas(self):
        """Mostra as áreas de plantio cadastradas."""
        try:
            # Criar uma nova janela
            janela = tk.Toplevel(self.root)
            janela.title("Áreas de Plantio")
            janela.geometry("400x300")
            
            # Criar tabela
            tree = ttk.Treeview(janela)
            tree["columns"] = ("id", "nome")
            tree.column("#0", width=0, stretch=tk.NO)
            tree.column("id", anchor=tk.CENTER, width=80)
            tree.column("nome", anchor=tk.W, width=300)
            
            tree.heading("#0", text="", anchor=tk.CENTER)
            tree.heading("id", text="ID", anchor=tk.CENTER)
            tree.heading("nome", text="Nome da Área", anchor=tk.CENTER)
            
            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Consultar dados
            conn = sqlite3.connect('farmtech_db.sqlite')
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM AreaPlantio")
            
            # Preencher a tabela
            for i, row in enumerate(cursor.fetchall()):
                tree.insert(parent='', index='end', iid=i, text='', values=(row[0], row[1]))
            
            conn.close()
            
            # Botões para gerenciar áreas
            frame_botoes = ttk.Frame(janela)
            frame_botoes.pack(pady=10)
            
            ttk.Button(frame_botoes, text="Adicionar", command=lambda: self.adicionar_area(tree)).pack(side=tk.LEFT, padx=5)
            ttk.Button(frame_botoes, text="Editar", command=lambda: self.editar_area(tree)).pack(side=tk.LEFT, padx=5)
            ttk.Button(frame_botoes, text="Excluir", command=lambda: self.excluir_area(tree)).pack(side=tk.LEFT, padx=5)
            ttk.Button(frame_botoes, text="Fechar", command=janela.destroy).pack(side=tk.LEFT, padx=5)
        except Exception as e:
            logger.error(f"Erro ao mostrar áreas: {str(e)}")
            messagebox.showerror("Erro", f"Erro ao mostrar áreas: {str(e)}")

    def adicionar_area(self, tree):
        """Adiciona uma nova área de plantio."""
        nome = simpledialog.askstring("Nova Área", "Nome da área de plantio:")
        if nome:
            try:
                conn = sqlite3.connect('farmtech_db.sqlite')
                cursor = conn.cursor()
                cursor.execute("INSERT INTO AreaPlantio (NomeArea) VALUES (?)", (nome,))
                conn.commit()
                # Obter o ID da área inserida
                area_id = cursor.lastrowid
                # Atualizar a tabela
                tree.insert('', 'end', values=(area_id, nome))
                conn.close()
                self.status_var.set(f"Área '{nome}' adicionada com sucesso")
            except Exception as e:
                logger.error(f"Erro ao adicionar área: {str(e)}")
                messagebox.showerror("Erro", f"Erro ao adicionar área: {str(e)}")

    def editar_area(self, tree):
        """Edita uma área de plantio existente."""
        selecionado = tree.selection()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione uma área para editar.")
            return
        
        # Obter dados da seleção
        valores = tree.item(selecionado[0], 'values')
        area_id = valores[0]
        nome_atual = valores[1]
        
        # Solicitar novo nome
        novo_nome = simpledialog.askstring("Editar Área", "Novo nome da área:", initialvalue=nome_atual)
        if novo_nome:
            try:
                conn = sqlite3.connect('farmtech_db.sqlite')
                cursor = conn.cursor()
                cursor.execute("UPDATE AreaPlantio SET NomeArea = ? WHERE ID_AreaPlantio = ?", (novo_nome, area_id))
                conn.commit()
                conn.close()
                # Atualizar a tabela
                tree.item(selecionado[0], values=(area_id, novo_nome))
                self.status_var.set(f"Área '{nome_atual}' editada para '{novo_nome}'")
            except Exception as e:
                logger.error(f"Erro ao editar área: {str(e)}")
                messagebox.showerror("Erro", f"Erro ao editar área: {str(e)}")

    def excluir_area(self, tree):
        """Exclui uma área de plantio."""
        selecionado = tree.selection()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione uma área para excluir.")
            return
        
        # Obter dados da seleção
        valores = tree.item(selecionado[0], 'values')
        area_id = valores[0]
        nome = valores[1]
        
        # Confirmar exclusão
        if messagebox.askyesno("Excluir Área", f"Deseja realmente excluir a área '{nome}'?"):
            try:
                conn = sqlite3.connect('farmtech_db.sqlite')
                cursor = conn.cursor()
                cursor.execute("DELETE FROM AreaPlantio WHERE ID_AreaPlantio = ?", (area_id,))
                conn.commit()
                conn.close()
                # Remover da tabela
                tree.delete(selecionado[0])
                self.status_var.set(f"Área '{nome}' excluída com sucesso")
            except Exception as e:
                logger.error(f"Erro ao excluir área: {str(e)}")
                messagebox.showerror("Erro", f"Erro ao excluir área: {str(e)}")

    def mostrar_sensores(self):
        """Mostra os sensores cadastrados."""
        try:
            # Criar uma nova janela
            janela = tk.Toplevel(self.root)
            janela.title("Sensores")
            janela.geometry("600x300")
            
            # Criar tabela
            tree = ttk.Treeview(janela)
            tree["columns"] = ("id", "tipo", "area", "status")
            tree.column("#0", width=0, stretch=tk.NO)
            tree.column("id", anchor=tk.CENTER, width=80)
            tree.column("tipo", anchor=tk.W, width=150)
            tree.column("area", anchor=tk.CENTER, width=80)
            tree.column("status", anchor=tk.CENTER, width=100)
            
            tree.heading("#0", text="", anchor=tk.CENTER)
            tree.heading("id", text="ID", anchor=tk.CENTER)
            tree.heading("tipo", text="Tipo de Sensor", anchor=tk.CENTER)
            tree.heading("area", text="Área ID", anchor=tk.CENTER)
            tree.heading("status", text="Status", anchor=tk.CENTER)
            
            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Consultar dados
            conn = sqlite3.connect('farmtech_db.sqlite')
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM Sensor")
            
            # Preencher a tabela
            for i, row in enumerate(cursor.fetchall()):
                tree.insert(parent='', index='end', iid=i, text='', values=(row[0], row[1], row[2], row[3]))
            
            conn.close()
            
            # Botões para gerenciar sensores
            frame_botoes = ttk.Frame(janela)
            frame_botoes.pack(pady=10)
            
            ttk.Button(frame_botoes, text="Adicionar", command=lambda: self.adicionar_sensor(tree)).pack(side=tk.LEFT, padx=5)
            ttk.Button(frame_botoes, text="Editar", command=lambda: self.editar_sensor(tree)).pack(side=tk.LEFT, padx=5)
            ttk.Button(frame_botoes, text="Excluir", command=lambda: self.excluir_sensor(tree)).pack(side=tk.LEFT, padx=5)
            ttk.Button(frame_botoes, text="Fechar", command=janela.destroy).pack(side=tk.LEFT, padx=5)
        except Exception as e:
            logger.error(f"Erro ao mostrar sensores: {str(e)}")
            messagebox.showerror("Erro", f"Erro ao mostrar sensores: {str(e)}")

    def adicionar_sensor(self, tree):
        """Adiciona um novo sensor."""
        # Criar uma janela de diálogo customizada
        dialog = tk.Toplevel(self.root)
        dialog.title("Novo Sensor")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()

        # Variáveis
        tipo_var = tk.StringVar()
        area_var = tk.StringVar()
        status_var = tk.StringVar(value="Ativo")

        # Frame para os campos
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # Campos de entrada
        ttk.Label(frame, text="Tipo de Sensor:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=tipo_var).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(frame, text="Área ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        # Obter áreas disponíveis
        conn = sqlite3.connect('farmtech_db.sqlite')
        cursor = conn.cursor()
        cursor.execute("SELECT ID_AreaPlantio, NomeArea FROM AreaPlantio")
        areas = cursor.fetchall()
        conn.close()
        area_combo = ttk.Combobox(frame, textvariable=area_var)
        area_combo['values'] = [f"{a[0]} - {a[1]}" for a in areas]
        area_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(frame, text="Status:").grid(row=2, column=0, sticky=tk.W, pady=5)
        status_combo = ttk.Combobox(frame, textvariable=status_var)
        status_combo['values'] = ["Ativo", "Inativo", "Manutenção"]
        status_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)

        # Botões
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)

        def salvar():
            tipo = tipo_var.get()
            area_full = area_var.get()
            status = status_var.get()
            if not tipo or not area_full:
                messagebox.showwarning("Aviso", "Preencha todos os campos.")
                return
            
            # Extrair ID da área
            area_id = area_full.split(" - ")[0]

            try:
                conn = sqlite3.connect('farmtech_db.sqlite')
                cursor = conn.cursor()
                cursor.execute("INSERT INTO Sensor (TipoSensor, ID_AreaPlantio, StatusSensor) VALUES (?, ?, ?)", (tipo, area_id, status))
                conn.commit()
                # Obter o ID do sensor inserido
                sensor_id = cursor.lastrowid
                # Atualizar a tabela
                tree.insert('', 'end', values=(sensor_id, tipo, area_id, status))
                conn.close()
                dialog.destroy()
                self.status_var.set(f"Sensor '{tipo}' adicionado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao adicionar sensor: {str(e)}")
                messagebox.showerror("Erro", f"Erro ao adicionar sensor: {str(e)}")

        ttk.Button(btn_frame, text="Salvar", command=salvar).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def editar_sensor(self, tree):
        """Edita um sensor existente."""
        selecionado = tree.selection()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione um sensor para editar.")
            return
        
        # Obter dados da seleção
        valores = tree.item(selecionado[0], 'values')
        sensor_id = valores[0]
        tipo_atual = valores[1]
        area_atual = valores[2]
        status_atual = valores[3]

        # Criar uma janela de diálogo customizada
        dialog = tk.Toplevel(self.root)
        dialog.title("Editar Sensor")
        dialog.geometry("300x200")
        dialog.transient(self.root)
        dialog.grab_set()

        # Variáveis
        tipo_var = tk.StringVar(value=tipo_atual)
        area_var = tk.StringVar()
        status_var = tk.StringVar(value=status_atual)

        # Frame para os campos
        frame = ttk.Frame(dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # Campos de entrada
        ttk.Label(frame, text="Tipo de Sensor:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=tipo_var).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(frame, text="Área ID:").grid(row=1, column=0, sticky=tk.W, pady=5)
        # Obter áreas disponíveis
        conn = sqlite3.connect('farmtech_db.sqlite')
        cursor = conn.cursor()
        cursor.execute("SELECT ID_AreaPlantio, NomeArea FROM AreaPlantio")
        areas = cursor.fetchall()
        conn.close()
        area_combo = ttk.Combobox(frame, textvariable=area_var)
        area_combo['values'] = [f"{a[0]} - {a[1]}" for a in areas]
        # Tentar pré-selecionar a área atual
        for a in areas:
            if str(a[0]) == str(area_atual):
                area_var.set(f"{a[0]} - {a[1]}")
                break
        area_combo.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(frame, text="Status:").grid(row=2, column=0, sticky=tk.W, pady=5)
        status_combo = ttk.Combobox(frame, textvariable=status_var)
        status_combo['values'] = ["Ativo", "Inativo", "Manutenção"]
        status_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)

        # Botões
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)

        def salvar_edicao():
            tipo = tipo_var.get()
            area_full = area_var.get()
            status = status_var.get()
            if not tipo or not area_full:
                messagebox.showwarning("Aviso", "Preencha todos os campos.")
                return
            
            area_id = area_full.split(" - ")[0]

            try:
                conn = sqlite3.connect('farmtech_db.sqlite')
                cursor = conn.cursor()
                cursor.execute("UPDATE Sensor SET TipoSensor = ?, ID_AreaPlantio = ?, StatusSensor = ? WHERE ID_Sensor = ?", 
                               (tipo, area_id, status, sensor_id))
                conn.commit()
                conn.close()
                # Atualizar a tabela
                tree.item(selecionado[0], values=(sensor_id, tipo, area_id, status))
                dialog.destroy()
                self.status_var.set(f"Sensor '{tipo_atual}' editado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao editar sensor: {str(e)}")
                messagebox.showerror("Erro", f"Erro ao editar sensor: {str(e)}")

        ttk.Button(btn_frame, text="Salvar", command=salvar_edicao).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def excluir_sensor(self, tree):
        """Exclui um sensor."""
        selecionado = tree.selection()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione um sensor para excluir.")
            return
        
        # Obter dados da seleção
        valores = tree.item(selecionado[0], 'values')
        sensor_id = valores[0]
        tipo = valores[1]

        # Confirmar exclusão
        if messagebox.askyesno("Excluir Sensor", f"Deseja realmente excluir o sensor '{tipo}' (ID: {sensor_id})?"):
            try:
                conn = sqlite3.connect('farmtech_db.sqlite')
                cursor = conn.cursor()
                # Remover leituras e ajustes relacionados primeiro para evitar erros de FK
                cursor.execute("DELETE FROM LeituraSensor WHERE ID_Sensor = ?", (sensor_id,))
                cursor.execute("""
                    DELETE FROM AjusteRecurso WHERE ID_LeituraReferencia IN (
                        SELECT ID_Leitura FROM LeituraSensor WHERE ID_Sensor = ?
                    )
                """, (sensor_id,))
                cursor.execute("DELETE FROM Sensor WHERE ID_Sensor = ?", (sensor_id,))
                conn.commit()
                conn.close()
                # Remover da tabela
                tree.delete(selecionado[0])
                self.status_var.set(f"Sensor '{tipo}' excluído com sucesso")
            except Exception as e:
                logger.error(f"Erro ao excluir sensor: {str(e)}")
                messagebox.showerror("Erro", f"Erro ao excluir sensor: {str(e)}")

    def mostrar_leituras(self):
        """Mostra as leituras de sensores cadastradas."""
        try:
            janela = tk.Toplevel(self.root)
            janela.title("Leituras de Sensores")
            janela.geometry("800x400")

            tree = ttk.Treeview(janela)
            tree["columns"] = ("id_leitura", "sensor", "data_hora", "valor", "unidade")
            tree.column("#0", width=0, stretch=tk.NO)
            tree.column("id_leitura", anchor=tk.CENTER, width=80)
            tree.column("sensor", anchor=tk.W, width=120)
            tree.column("data_hora", anchor=tk.CENTER, width=150)
            tree.column("valor", anchor=tk.E, width=100)
            tree.column("unidade", anchor=tk.W, width=80)

            tree.heading("#0", text="", anchor=tk.CENTER)
            tree.heading("id_leitura", text="ID Leitura", anchor=tk.CENTER)
            tree.heading("sensor", text="Sensor", anchor=tk.CENTER)
            tree.heading("data_hora", text="Data/Hora", anchor=tk.CENTER)
            tree.heading("valor", text="Valor", anchor=tk.CENTER)
            tree.heading("unidade", text="Unidade", anchor=tk.CENTER)
            
            # Scrollbar
            scrollbar = ttk.Scrollbar(janela, orient="vertical", command=tree.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            conn = sqlite3.connect('farmtech_db.sqlite')
            cursor = conn.cursor()
            logger.info("Executando consulta para mostrar leituras...")
            cursor.execute("""
                SELECT ls.ID_Leitura, s.TipoSensor, ls.DataHoraLeitura, ls.ValorLeitura, ls.UnidadeMedida
                FROM LeituraSensor ls
                JOIN Sensor s ON ls.ID_Sensor = s.ID_Sensor
                ORDER BY ls.DataHoraLeitura DESC
                LIMIT 200
            """)
            rows = cursor.fetchall()
            logger.info(f"Consulta para leituras retornou {len(rows)} linhas.")
            if len(rows) > 0:
                logger.info(f"Primeiras 5 linhas: {rows[:5]}")

            for i, row in enumerate(rows):
                # Formatar a data/hora
                tree.insert(parent='', index='end', iid=i, text='', values=(row[0], row[1], row[2], row[3], row[4]))
            
            conn.close()

            ttk.Button(janela, text="Fechar", command=janela.destroy).pack(pady=5)
        except Exception as e:
            logger.error(f"Erro ao mostrar leituras: {str(e)}")
            messagebox.showerror("Erro", f"Erro ao mostrar leituras: {str(e)}")

    def mostrar_ajustes(self):
        """Mostra os ajustes de recursos cadastrados."""
        try:
            janela = tk.Toplevel(self.root)
            janela.title("Ajustes de Recursos")
            janela.geometry("800x400")

            tree = ttk.Treeview(janela)
            tree["columns"] = ("id_ajuste", "area", "tipo", "data_hora", "status_bomba", "leitura_referencia")
            tree.column("#0", width=0, stretch=tk.NO)
            tree.column("id_ajuste", anchor=tk.CENTER, width=80)
            tree.column("area", anchor=tk.W, width=100)
            tree.column("tipo", anchor=tk.W, width=100)
            tree.column("data_hora", anchor=tk.CENTER, width=150)
            tree.column("status_bomba", anchor=tk.CENTER, width=100)
            tree.column("leitura_referencia", anchor=tk.CENTER, width=100)

            tree.heading("#0", text="", anchor=tk.CENTER)
            tree.heading("id_ajuste", text="ID Ajuste", anchor=tk.CENTER)
            tree.heading("area", text="Área", anchor=tk.CENTER)
            tree.heading("tipo", text="Tipo Ajuste", anchor=tk.CENTER)
            tree.heading("data_hora", text="Data/Hora", anchor=tk.CENTER)
            tree.heading("status_bomba", text="Status Bomba", anchor=tk.CENTER)
            tree.heading("leitura_referencia", text="Leitura ID", anchor=tk.CENTER)
            
            # Scrollbar
            scrollbar = ttk.Scrollbar(janela, orient="vertical", command=tree.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            conn = sqlite3.connect('farmtech_db.sqlite')
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ar.ID_Ajuste, ap.NomeArea, ar.TipoAjuste, ar.DataHoraAjuste, ar.StatusBomba, ar.ID_LeituraReferencia
                FROM AjusteRecurso ar
                JOIN AreaPlantio ap ON ar.ID_AreaPlantio = ap.ID_AreaPlantio
                ORDER BY ar.DataHoraAjuste DESC
                LIMIT 100
            """)

            for i, row in enumerate(cursor.fetchall()):
                status_bomba_str = "Ligada" if row[4] else "Desligada"
                tree.insert(parent='', index='end', iid=i, text='', values=(row[0], row[1], row[2], row[3], status_bomba_str, row[5]))
            
            conn.close()

            ttk.Button(janela, text="Fechar", command=janela.destroy).pack(pady=5)
        except Exception as e:
            logger.error(f"Erro ao mostrar ajustes: {str(e)}")
            messagebox.showerror("Erro", f"Erro ao mostrar ajustes: {str(e)}")

    def recriar_banco(self):
        """Recria o banco de dados do zero."""
        if messagebox.askyesno("Confirmar Recriação", "Isso apagará todos os dados existentes. Deseja continuar?"):
            try:
                criar_banco_dados()
                self.carregar_ultimas_leituras()
                messagebox.showinfo("Sucesso", "Banco de dados recriado com sucesso!")
                self.status_var.set("Banco de dados recriado.")
            except Exception as e:
                logger.error(f"Erro ao recriar banco de dados: {str(e)}")
                messagebox.showerror("Erro", f"Erro ao recriar banco de dados: {str(e)}")

    def exportar_dados(self):
        """Exporta todos os dados do banco de dados para arquivos CSV."""
        filepath = filedialog.askdirectory(title="Selecionar Pasta para Exportar Dados")
        if not filepath:
            return

        try:
            conn = sqlite3.connect('farmtech_db.sqlite')
            cursor = conn.cursor()

            tables = ["AreaPlantio", "Sensor", "LeituraSensor", "AjusteRecurso"]

            for table_name in tables:
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                column_names = [description[0] for description in cursor.description]

                csv_filepath = os.path.join(filepath, f"{table_name}.csv")
                with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    csv_writer = csv.writer(csvfile)
                    csv_writer.writerow(column_names)
                    csv_writer.writerows(rows)
                logger.info(f"Dados da tabela {table_name} exportados para {csv_filepath}")
            
            conn.close()
            messagebox.showinfo("Exportação Concluída", f"Todos os dados foram exportados para '{filepath}'")
            self.status_var.set(f"Dados exportados para '{filepath}'")
        except Exception as e:
            logger.error(f"Erro ao exportar dados: {str(e)}")
            messagebox.showerror("Erro", f"Erro ao exportar dados: {str(e)}")

    def limpar_historico(self):
        """Limpa as últimas 100 leituras e ajustes do banco de dados e da interface."""
        if messagebox.askyesno("Confirmar Limpeza", "Deseja realmente limpar as últimas 100 leituras e ajustes do banco de dados?"):
            try:
                conn = sqlite3.connect('farmtech_db.sqlite')
                cursor = conn.cursor()

                # Deletar as leituras e ajustes mais antigas (mantendo as mais recentes)
                cursor.execute("DELETE FROM LeituraSensor WHERE ID_Leitura NOT IN (SELECT ID_Leitura FROM LeituraSensor ORDER BY DataHoraLeitura DESC LIMIT 100)")
                cursor.execute("DELETE FROM AjusteRecurso WHERE ID_Ajuste NOT IN (SELECT ID_Ajuste FROM AjusteRecurso ORDER BY DataHoraAjuste DESC LIMIT 100)")
                
                conn.commit()
                conn.close()
                self.carregar_ultimas_leituras() # Recarrega a tabela após a limpeza
                messagebox.showinfo("Sucesso", "Histórico de leituras e ajustes limpo com sucesso!")
                self.status_var.set("Histórico limpo.")
            except Exception as e:
                logger.error(f"Erro ao limpar histórico: {str(e)}")
                messagebox.showerror("Erro", f"Erro ao limpar histórico: {str(e)}")


    def simular_leitura(self):
        """Simula a recepção de dados de um sensor para testes."""
        # Gerar valores aleatórios para simulação
        sim_has_p = random.choice([True, False])
        sim_has_k = random.choice([True, False])
        sim_ph_value = round(random.uniform(5.0, 8.0), 2)
        sim_umidade_solo = round(random.uniform(20.0, 90.0), 1)

        self.atualizar_dados_sensores(sim_has_p, sim_has_k, sim_ph_value, sim_umidade_solo)
        self.status_var.set("Leitura simulada gerada.")

    def controlar_bomba(self, ligar):
        """Controla a bomba manualmente, enviando comando para o Arduino."""
        comando = "PUMP_ON" if ligar else "PUMP_OFF"
        if self.arduino.enviar_comando(comando):
            self.bomba_status_var.set("Ligada" if ligar else "Desligada")
            self.bomba_label.configure(foreground="green" if ligar else "red")
            self.status_var.set(f"Comando '{comando}' enviado para a bomba.")
            # Registrar o ajuste manual no banco de dados
            try:
                conn = sqlite3.connect('farmtech_db.sqlite')
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO AjusteRecurso (ID_AreaPlantio, TipoAjuste, StatusBomba, ID_LeituraReferencia)
                    VALUES (?, ?, ?, ?)
                """, (1, 'Controle Manual', ligar, None)) # ID_LeituraReferencia é None para ajuste manual
                conn.commit()
                conn.close()
                logger.info(f"Ajuste manual de bomba registrado: {'Ligada' if ligar else 'Desligada'}")
            except Exception as e:
                logger.error(f"Erro ao registrar ajuste manual da bomba: {str(e)}")
        else:
            messagebox.showerror("Erro", "Não foi possível enviar o comando para a bomba. Verifique a conexão.")
            self.status_var.set("Erro ao controlar bomba.")

    def fetch_weather_data(self):
        """Busca dados meteorológicos da API do OpenWeatherMap."""
        try:
            # Endpoint para dados meteorológicos atuais
            # URL da API do OpenWeatherMap para o clima atual
            url = f"http://api.openweathermap.org/data/2.5/weather?q={CITY_NAME},{COUNTRY_CODE}&appid={OPENWEATHER_API_KEY}&units={UNITS}&lang=pt_br"
            
            response = requests.get(url)
            response.raise_for_status() # Lança um erro para status de resposta ruins (4xx ou 5xx)
            weather_data = response.json()
            
            # Extrair dados de interesse
            temperature = weather_data['main']['temp']
            humidity = weather_data['main']['humidity']
            
            # Verificar previsão de chuva nas próximas horas (simplificado para o clima atual)
            # Para uma previsão mais precisa, seria necessário usar o endpoint 'forecast' ou 'onecall'
            weather_description = weather_data['weather'][0]['description'].lower()
            
            rain_forecast = "Sem previsão"
            if "chuva" in weather_description or "garoa" in weather_description or "temporal" in weather_description:
                rain_forecast = "Chuva prevista"
            
            self.current_api_temp = temperature
            self.current_api_humidity = humidity
            self.current_api_rain_forecast = rain_forecast

            # Atualizar as variáveis Tkinter
            self.temp_api_var.set(f"{temperature:.1f} °C")
            self.humid_api_var.set(f"{humidity:.1f} %")
            self.rain_forecast_var.set(rain_forecast)
            
            logger.info(f"Dados meteorológicos atualizados: Temp={temperature}°C, Humid_Ar={humidity}%, Chuva={rain_forecast}")
            self.status_var.set(f"Dados meteorológicos atualizados: {temperature}°C, {humidity}%")

        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar dados meteorológicos (HTTP): {str(e)}")
            self.status_var.set(f"Erro API: {e}")
            self.temp_api_var.set("-- °C")
            self.humid_api_var.set("-- %")
            self.rain_forecast_var.set("--")
        except KeyError as e:
            logger.error(f"Erro ao parsear dados meteorológicos (chave ausente): {str(e)}")
            self.status_var.set(f"Erro API: dados incompletos")
            self.temp_api_var.set("-- °C")
            self.humid_api_var.set("-- %")
            self.rain_forecast_var.set("--")
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar dados meteorológicos: {str(e)}")
            self.status_var.set(f"Erro inesperado API: {e}")
            self.temp_api_var.set("-- °C")
            self.humid_api_var.set("-- %")
            self.rain_forecast_var.set("--")
        
        # Agendar a próxima busca de dados meteorológicos para 5 minutos
        self.root.after(300000, self.fetch_weather_data_threaded)

    def fetch_weather_data_threaded(self):
        """Executa fetch_weather_data em uma thread separada para não travar a GUI."""
        thread = threading.Thread(target=self.fetch_weather_data)
        thread.daemon = True # Define a thread como daemon para que ela termine quando o programa principal terminar
        thread.start()

if __name__ == "__main__":
    root = tk.Tk()
    app = FarmTechApp(root)
    root.mainloop()
    
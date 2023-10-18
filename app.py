from flask import Flask, render_template, jsonify, request
import serial
import time
import threading
from flask_socketio import SocketIO, emit
import os
from scipy import signal

app = Flask(__name__)
socketio = SocketIO(app)

# Configuração da porta serial
ser = serial.Serial('/dev/cu.ESP32', 115200) 

# Variáveis para armazenar os dados da porta serial
data_buffer = []
time_buffer = []

# Variáveis para armazenar o valor dos parâmetro
th = 0.0
ta = 0.0
i = 0.0
tempoPos = 4.0


# Parâmetros do filtro Butterworth
fs = 1000
f_low = 10
f_high = 350
order = 3

# Cria o filtro Butterworth de banda passante
b, a = signal.butter(order, [f_low / (0.5 * fs), f_high / (0.5 * fs)], btype='bandpass')

# Frequência a ser eliminada pelo filtro notch
f_notch = 60  # Frequência em Hz
Q = 30  # Largura de banda do filtro

# Cria o filtro notch
b_notch, a_notch = signal.iirnotch(f_notch, Q, fs)

# Inicializa o buffer para a função filtfilt
zi = signal.lfilter_zi(b, a)
zi_notch = signal.lfilter_zi(b_notch, a_notch)

# Função para ler dados da porta serial
def read_serial_data():
    global zi_notch, zi
    start = 0
    while True:
        try:
            while int.from_bytes(ser.read(), "big") != 204:
                pass
            b1 = int.from_bytes(ser.read(), "big")
            b2 = int.from_bytes(ser.read(), "big")
            current_time_millis = int(round(time.time() * 1000))
            dado = b1 * 256 + b2
            # Aplica o filtro notch em 60Hz
            dado_filtrado_notch, zi_notch = signal.lfilter(b_notch, a_notch, [dado], zi=zi_notch)
            # Aplica o filtro passa-banda
            dado_filtrado, zi = signal.lfilter(b, a, dado_filtrado_notch, zi=zi)
            dado_certo = (abs(dado_filtrado[0])*3.3)/4095
            data_buffer.append(dado_certo)
            time_buffer.append(current_time_millis - current_time_millis + start)
            start = start + (1/1000)
        except ValueError:
            pass  # Lida com dados inválidos, se necessário


# Função para atualizar os parâmetros via POST
@app.route('/update_params', methods=['POST'])
def update_parameters():
    global th, ta, i, tempoPos
    data = request.form
    th = float(data['threshold'])
    ta = float(data['tempo_ativacao'])
    i = float(data['intensidade'])
    tempoPos = float(data['tempoPos'])

    # Enviar os novos parâmetros para o ESP32
    ser.write(bytes([int(th), int(ta), int(i), int(tempoPos)]))

    return jsonify({'success': True})

    
# Iniciar a leitura da porta serial em uma thread separada
serial_thread = threading.Thread(target=read_serial_data)
serial_thread.daemon = True
serial_thread.start()

# Rota para a página inicial
@app.route('/')
def index():
    return render_template('index.html', threshold=th, tempo_ativacao=ta, intensidade=i, tempoPos=tempoPos)


# Rota para fornecer dados para o gráfico em formato JSON
@app.route('/data')
def get_data():
    return jsonify({'time': time_buffer, 'data': data_buffer})

# Rota para a página que mostra o gráfico ao vivo
@app.route('/chart')
def chart():
    return render_template('chart.html')

if __name__ == '__main__':
    socketio.run(app, debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
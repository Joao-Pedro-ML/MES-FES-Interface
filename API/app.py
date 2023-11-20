import io
from flask import Flask, render_template, jsonify, request, make_response
import serial
import threading
from flask_socketio import SocketIO, emit
import os
from scipy import signal
import csv

app = Flask(__name__)
socketio = SocketIO(app)

# Configuração da porta serial
ser = serial.Serial('/dev/cu.ESP32', 115200) 

# Variáveis para armazenar os dados da porta serial
data_buffer = []
time_buffer = []
dados = [] # lista dos dados brutos para salvar no arquivo csv

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

fes = 0

coleta_ativa = False


# Função para ler dados da porta serial
def read_serial_data():
    global zi_notch, zi, fes
    start = 0
    while True:
        try:
            while int.from_bytes(ser.read(), "big") != 204:
                pass
            b1 = int.from_bytes(ser.read(), "big")
            b2 = int.from_bytes(ser.read(), "big")
            dado = b1 * 256 + b2
            dados.append(dado)
            if dado == 70:
                print('FES Ativada')
                fes = 1
            # Aplica o filtro notch em 60Hz
            dado_conv = (dado*3.3)/4095
            dado_filtrado_notch, zi_notch = signal.lfilter(b_notch, a_notch, [dado_conv], zi=zi_notch)
            # Aplica o filtro passa-banda
            dado_filtrado, zi = signal.lfilter(b, a, dado_filtrado_notch, zi=zi)
            start = start + (1/1000)
            data_buffer.append(abs(dado_filtrado[0]))
            time_buffer.append(start)
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

@app.route('/FES')
def FES():
    if fes == 1:
        return jsonify({'FES': 'ativada'})
    elif fes == 0:
        return jsonify({'FES': 'desligada'})
    
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

@socketio.on('update_params')
def stop_collection(data):
    command = data['command']
    ser.write(bytes([command]))
    print('Comando para parar coleta enviado ao ESP32')
    
# Função para iniciar a coleta no servidor
@socketio.on('iniciar_coleta')
def start_collection(data):
    global coleta_ativa
    command = data['command']
    ser.write(bytes([command]))
    print('Comando para iniciar coleta enviado ao ESP32')
    coleta_ativa = True  # Ative a coleta


@app.route('/download_csv', methods=['GET'])
def download_csv():
    response = make_response(generate_csv())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=dados.csv'

    return response

def generate_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['tempo', 'dado']) 

    for i in range(len(dados)):
        writer.writerow([time_buffer[i], dados[i]])

    return output.getvalue()

# Iniciar a leitura da porta serial em uma thread separada
serial_thread = threading.Thread(target=read_serial_data)
serial_thread.daemon = True
serial_thread.start()

if __name__ == '__main__':
    socketio.run(app, debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
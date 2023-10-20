    #include <Arduino.h>
    #include "BluetoothSerial.h"
    
    hw_timer_t *timer_coleta = NULL;
    hw_timer_t *timer_params = NULL;
    
    const int emgPin = 34;     // Pino de entrada do sinal EMG (vp)
    const int sampleRate = 1;  // Taxa de amostragem em milissegundos (1 ms)
    uint16_t emgValue = 0;
    bool coleta = false;
    bool params = false;
    BluetoothSerial SerialBT;
    
    // Parametros
    float th = 0;  // Threshold (inclinação)
    float ta = 0;  // Tempo de ativação (T_on)
    float in = 0;  // Intensidade (t_on)
    float tempo = 0;
    float Tfreq = 25000;
    
    // PARAMETROS A FAZER
    int tam = 0;               // tamanho de janela, linguagem não aceita tamanho variável
    float T_rise = 937.5;      // T_rise
    float T_decrease = 937.5;  // T_decrease
    float th_apm_max = 3.0;    // th_amplitude_max - DONE
    float th_amp_min = 0.0;    // th_amplitude_min - DONE
    int T_pos = 0;             // T_pos (tempo morto) - DONE
    int tilt = 12;             // Tilt sensor
    
    uint16_t amostras_1[100];
    uint16_t amostras_2[100];
    uint16_t amostras[200];
    
    void IRAM_ATTR onColeta() {
      coleta = true;
    }
    
    uint16_t is_fes = 70;
    
    const int LED_BUILTIN = 2;  // Pino do LED embutido
    
    void setup() {
      Serial.begin(115200);
      SerialBT.begin("ESP32");
      pinMode(emgPin, INPUT);
    
      timer_coleta = timerBegin(0, 80, true);
      timerAttachInterrupt(timer_coleta, &onColeta, true);
      timerAlarmWrite(timer_coleta, 500, true);
      timerAlarmEnable(timer_coleta);
    
      Serial.println("Sistema ligado...");
    
      // FES to H bridge
      pinMode(32, OUTPUT);
      pinMode(33, OUTPUT);
    
      // LED FES
      pinMode(LED_BUILTIN, OUTPUT);
      digitalWrite(LED_BUILTIN, HIGH);
      delay(500);
      digitalWrite(LED_BUILTIN, LOW);
      delay(500);
      digitalWrite(LED_BUILTIN, HIGH);
    }
    
    
    
    void FES() {
      Serial.println("FES Rising");
      digitalWrite(LED_BUILTIN, HIGH);  // Liga o LED embutido
      delay(50);
      digitalWrite(LED_BUILTIN, LOW);
      delay(50);
      digitalWrite(LED_BUILTIN, HIGH);
      SerialBT.write(0xCC);  //byte inicial
      SerialBT.write((is_fes >> 8));
      SerialBT.write((is_fes)&0xFF);
      for (Tfreq = 50000; Tfreq >= 25000; Tfreq = Tfreq - T_rise) {  //Rise 20Hz to 40Hz
        digitalWrite(32, HIGH);
        digitalWrite(33, LOW);
        delayMicroseconds(in);
        digitalWrite(32, LOW);
        delayMicroseconds(10);  //interpulse 10us off time
        digitalWrite(33, HIGH);
        delayMicroseconds(in);
        digitalWrite(33, LOW);
        delayMicroseconds(Tfreq - (2 * in));
      }
      Serial.println("FES Activated");
      digitalWrite(LED_BUILTIN, HIGH);  // Liga o LED embutido
      delay(50);
      digitalWrite(LED_BUILTIN, LOW);
      delay(50);
      digitalWrite(LED_BUILTIN, HIGH);
      while (tempo < ta) {
        digitalWrite(32, HIGH);
        digitalWrite(33, LOW);
        delayMicroseconds(in);
        digitalWrite(32, LOW);
        delayMicroseconds(10);
        digitalWrite(33, HIGH);
        delayMicroseconds(in);
        digitalWrite(33, LOW);
        delayMicroseconds(Tfreq - (2 * in));
      }
      Serial.println("FES Decreasing");
      digitalWrite(LED_BUILTIN, HIGH);  // Liga o LED embutido
      delay(50);
      digitalWrite(LED_BUILTIN, LOW);
      delay(50);
      digitalWrite(LED_BUILTIN, HIGH);
      for (float Tfreq = 25000; Tfreq >= 50000; Tfreq = Tfreq + T_decrease) {  //Decrease 40Hz to 20Hz
        digitalWrite(32, HIGH);
        digitalWrite(33, LOW);
        delayMicroseconds(in);
        digitalWrite(32, LOW);
        delayMicroseconds(10);  //interpulse 10us off time
        digitalWrite(33, HIGH);
        delayMicroseconds(in);
        digitalWrite(33, LOW);
        delayMicroseconds(Tfreq - 2 * in);
      }
    
      unsigned long millisAtual = millis();  //tempo atual em milissegundos
      while (millisAtual - tempo < T_pos) {
        tempo = millisAtual;
        Serial.println("Pausa pós FES");
        digitalWrite(LED_BUILTIN, LOW);
      }
      digitalWrite(LED_BUILTIN, HIGH);
    }
    
    
    
    void loop() {
    
      if (SerialBT.available() >= 1) {
        uint8_t command = SerialBT.read();
        if (command == 0xFF) {
          // Recebeu o comando de interrupção, interrompa a coleta de dados
          coleta = false;
          digitalWrite(LED_BUILTIN, LOW);
          // Espere até receber o comando 'iniciar coleta'
          while (SerialBT.available() < 1) {
            delay(100); // Aguarde 100 ms
          }
          // Reinicie a coleta apenas se o comando for 'iniciar coleta'
          if (SerialBT.read() == 0x01) {
            coleta = true;
            digitalWrite(LED_BUILTIN, HIGH);
            // Se você quiser reenviar os parâmetros no início da coleta, faça isso aqui
            // Exemplo: enviarParâmetrosBluetooth();
          }
        } else if (command == 0x02) {
          // Recebeu o comando de ligar a FES, ligue a FES
          Serial.println("Comando de ligar FES recebido!");
          FES();
        }
      }
    
      if (coleta == true) {
        int index = 0;
        //digitalWrite(LED_BUILTIN, HIGH);
        timerWrite(timer_coleta, 0);
        emgValue = analogRead(emgPin);
        SerialBT.write(0xCC);  //byte inicial
        SerialBT.write((emgValue >> 8));
        SerialBT.write((emgValue)&0xFF);
        amostras[index] = emgValue;
        coleta = false;
        index++;
        tilt = digitalRead(12);
        if (index == 200) {
          index = 0;
        }
      }
    
      if (SerialBT.available() >= 4) {
        th = SerialBT.read();
        ta = SerialBT.read();
        in = SerialBT.read();
        T_pos = SerialBT.read();
      }
    
      for (int i = 0; i < (200 / 2); i++) {
        amostras_1[i] = amostras[i];
      }
    
      for (int i = (200 / 2); i < 200; i++) {
        amostras_2[i - (200 / 2)] = amostras[i];
      }
    
      float somaQuadrados1 = 0.0;
      for (int i = 0; i < 100; i++) {
        somaQuadrados1 += pow(amostras_1[i], 2);
      }
      float rms1 = sqrt(somaQuadrados1 / 100);
    
      float somaQuadrados2 = 0.0;
      for (int i = 0; i < 100; i++) {
        somaQuadrados2 += pow(amostras_2[i], 2);
      }
      float rms2 = sqrt(somaQuadrados2 / 100);
    
      if (rms2 > (1 + th) * rms1 && rms2 > th_amp_min && rms2 < th_apm_max) {
        Serial.println("Rotina FES");
        FES();
      }
    }
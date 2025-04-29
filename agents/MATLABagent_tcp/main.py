import socket
import json
import threading
import time
import re
import subprocess
import os
import signal
from datetime import datetime
import argparse

class MatlabSimulationClient:
    """Client per interfacciarsi con simulazioni MATLAB tramite SimulationRunner"""
    
    def __init__(self, host='localhost', port=12345, matlab_script=None, log_file=None):
        """
        Inizializza il client
        
        Args:
            host (str): Host su cui ascoltare
            port (int): Porta su cui ascoltare
            matlab_script (str): Script MATLAB da eseguire (opzionale)
            log_file (str): File di log (opzionale)
        """
        self.host = host
        self.port = port
        self.matlab_script = matlab_script
        self.server_socket = None
        self.client_socket = None
        self.matlab_process = None
        self.running = False
        self.connected = False
        self.buffer = ""
        
        # Dati di simulazione
        self.simulation_data = {
            'time': [],
            'position_x': [],
            'position_y': [],
            'velocity_x': [],
            'velocity_y': [],
            'step_count': 0,
            'state': None,
            'params': None
        }
        
        # Setup del log
        self.log_file = log_file or f"matlab_sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
    def _log(self, message):
        """Registra messaggi nel log"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        log_message = f"[{timestamp}] {message}"
        print(log_message)
        
            
    def start_server(self):
        """Avvia il server socket per ascoltare connessioni da MATLAB"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self._log(f"Server in ascolto su {self.host}:{self.port}")
            self.running = True
            
            # Thread per accettare connessioni
            self.accept_thread = threading.Thread(target=self._accept_connections)
            self.accept_thread.daemon = True
            self.accept_thread.start()
            
            return True
        except Exception as e:
            self._log(f"Errore nell'avvio del server: {str(e)}")
            return False
    
    def _accept_connections(self):
        """Thread per accettare connessioni da MATLAB"""
        self.server_socket.settimeout(1.0)  # Timeout per poter terminare il thread
        
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                self._log(f"Connessione accettata da {addr}")
                
                # Avvia un thread per gestire la connessione
                self.client_socket = client_socket
                self.connected = True
                
                receive_thread = threading.Thread(target=self._receive_data)
                receive_thread.daemon = True
                receive_thread.start()
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self._log(f"Errore nell'accettare connessioni: {str(e)}")
                break
    
    def _receive_data(self):
        """Thread per ricevere dati da MATLAB"""
        self.client_socket.settimeout(1.0)

        while self.running and self.connected:
            try:
                data = self.client_socket.recv(4096)

                if not data:
                    self._log("Connessione chiusa da MATLAB")
                    self.connected = False
                    break

                # Log dei dati ricevuti prima della decodifica
                self._log(f"Messaggio ricevuto: {data}")

                # Aggiungi i dati ricevuti al buffer
                self.buffer += data.decode('utf-8')

                # Se c'è un terminatore nel buffer, processa il messaggio
                if '#END#' in self.buffer:
                    message, self.buffer = self.buffer.split('#END#', 1)
                    self._handle_message(json.loads(message))

            except socket.timeout:
                continue
            except Exception as e:
                if self.running and self.connected:
                    self._log(f"Errore nella ricezione dati: {str(e)}")
                break

    
    def _process_buffer(self):
        """Elabora il buffer per estrarre messaggi JSON completi"""
        # Cerca messaggi delimitati da #END#
        messages = re.split(r'#END#', self.buffer)
        
        # Se abbiamo almeno un messaggio completo
        if len(messages) > 1:
            # Tutti i messaggi completi tranne l'ultimo (che potrebbe essere incompleto)
            complete_messages = messages[:-1]
            
            # Conserva l'eventuale parte incompleta nel buffer
            self.buffer = messages[-1]
            
            # Processa tutti i messaggi completi
            for msg in complete_messages:
                if msg.strip():  # Skip empty messages
                    try:
                        self._handle_message(json.loads(msg))
                    except json.JSONDecodeError:
                        self._log(f"Errore nel parsing JSON: {msg}")
    
    def _handle_message(self, message):
        """Gestisce i messaggi ricevuti da MATLAB"""
        if 'event' not in message:
            return
        
        event = message.get('event')
        data = message.get('data', {})
        timestamp = message.get('timestamp')
        
        self._log(f"Ricevuto evento: {event}")
        
        if event == 'connection_established':
            self._log("Connessione con MATLAB stabilita")
        
        elif event == 'simulation_initialized':
            self._log("Simulazione inizializzata")
            # Salva i parametri e lo stato iniziale
            self.simulation_data['state'] = data.get('state', {})
            self.simulation_data['params'] = data.get('params', {})
            
            # Inizializza i dati per la memorizzazione
            if 'state' in data and 'position' in data['state']:
                pos = data['state']['position']
                vel = data['state']['velocity']
                
                self.simulation_data['position_x'] = [pos[0]]
                self.simulation_data['position_y'] = [pos[1]]
                self.simulation_data['velocity_x'] = [vel[0]]
                self.simulation_data['velocity_y'] = [vel[1]]
                self.simulation_data['time'] = [0.0]
        
        elif event == 'state_updated':
            # Aggiorna lo stato corrente
            self.simulation_data['state'] = data.get('state', {})
            self.simulation_data['step_count'] = data.get('stepCount', 0)
            
            # Aggiorna i dati per il monitoraggio
            if 'state' in data:
                state = data['state']
                if 'position' in state and 'velocity' in state and 'time' in state:
                    pos = state['position']
                    vel = state['velocity']
                    
                    self.simulation_data['position_x'].append(pos[0])
                    self.simulation_data['position_y'].append(pos[1])
                    self.simulation_data['velocity_x'].append(vel[0])
                    self.simulation_data['velocity_y'].append(vel[1])
                    self.simulation_data['time'].append(state['time'])
                    
                    # Stampa i dati correnti (invece di visualizzarli graficamente)
                    self._log(f"Dati attuali - Posizione: [{pos[0]:.2f}, {pos[1]:.2f}], "
                             f"Velocità: [{vel[0]:.2f}, {vel[1]:.2f}], "
                             f"Tempo: {state['time']:.2f}s")
        
        elif event == 'step_completed':
            # Informazioni sul passo completato
            step_number = data.get('stepNumber', 0)
            elapsed_time = data.get('elapsedTime', 0)
            step_duration = data.get('stepDuration', 0)
            
            if step_number % 10 == 0:  # Log ogni 10 passi per evitare spam
                self._log(f"Passo {step_number} completato (tempo: {elapsed_time:.2f}s, durata: {step_duration:.4f}s)")
        
        elif event == 'simulation_terminated':
            self._log("Simulazione terminata")
            self._log(f"Passi totali: {data.get('stepCount', 0)}")
            self._log(f"Tempo totale: {data.get('elapsedTime', 0):.2f} secondi")
            
        elif event == 'connection_closing':
            self._log("MATLAB sta chiudendo la connessione")
            self.connected = False
    
    def send_command(self, command, params=None):
        """Invia un comando a MATLAB"""
        if not self.connected or not self.client_socket:
            self._log(f"Impossibile inviare comando '{command}': non connesso a MATLAB")
            return False
        
        cmd = {
            'command': command
        }
        
        if params:
            cmd['params'] = params
        
        try:
            self.client_socket.send((json.dumps(cmd) + "\n").encode('utf-8'))
            self._log(f"Comando inviato: {command}")
            return True
        except Exception as e:
            self._log(f"Errore nell'invio del comando: {str(e)}")
            return False
    
    def start_matlab_simulation(self):
        """Avvia lo script MATLAB se specificato"""
        if not self.matlab_script:
            self._log("Nessuno script MATLAB specificato")
            return False
        
        try:
            # Comando per avviare MATLAB in modalità non interattiva
            # Nota: potrebbe richiedere modifiche in base al sistema operativo
            if os.name == 'nt':  # Windows
                cmd = f'matlab -nosplash -nodesktop -r "try; {self.matlab_script}; catch e; disp(getReport(e)); end; exit"'
            else:  # Linux/Mac
                cmd = f'matlab -nosplash -nodesktop -r "try; {self.matlab_script}; catch e; disp(getReport(e)); end; exit"'
            
            self._log(f"Avvio MATLAB con comando: {cmd}")
            self.matlab_process = subprocess.Popen(cmd, shell=True)
            return True
        except Exception as e:
            self._log(f"Errore nell'avvio di MATLAB: {str(e)}")
            return False
    
    def stop(self):
        """Ferma il client e la simulazione"""
        self._log("Arresto del client...")
        
        # Ferma la simulazione se attiva
        if self.connected and self.client_socket:
            try:
                self.send_command('stop')
                time.sleep(0.5)  # Attendi che il comando venga processato
            except:
                pass
        
        # Ferma il processo MATLAB se attivo
        if self.matlab_process:
            self._log("Terminazione del processo MATLAB...")
            try:
                if os.name == 'nt':  # Windows
                    self.matlab_process.terminate()
                else:  # Linux/Mac
                    os.killpg(os.getpgid(self.matlab_process.pid), signal.SIGTERM)
            except:
                pass
        
        # Chiudi la connessione socket
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        self._log("Client arrestato")


class SimulationController:
    """Controller principale per la simulazione"""
    
    def __init__(self, args):
        """
        Inizializza il controller
        
        Args:
            args: Argomenti della riga di comando
        """
        self.args = args
        self.client = MatlabSimulationClient(
            host=args.host,
            port=args.port,
            matlab_script=args.script,
            log_file=args.log
        )
        
    def run(self):
        """Esegue la simulazione"""
        try:
            # Avvia il server socket
            if not self.client.start_server():
                print("Impossibile avviare il server. Uscita.")
                return False
            
            # Se è stato specificato uno script MATLAB, avvialo
            if self.args.script:
                if not self.client.start_matlab_simulation():
                    print("Avvio della simulazione MATLAB fallito. Continuazione in attesa di connessione.")
            else:
                print(f"In attesa di connessione MATLAB sulla porta {self.args.port}...")
                print("Eseguire lo script MATLAB con i parametri appropriati per connettersi.")
            
            # Modalità headless - attendi indefinitamente con gestione comandi da console
            print("Modalità di monitoraggio dati. Comandi disponibili:")
            print("  pause - Mette in pausa la simulazione")
            print("  resume - Riprende la simulazione")
            print("  stop - Termina la simulazione")
            print("  exit - Chiude il client")
            print("Premi Ctrl+C per terminare.")
            
            # Thread per l'input da console
            input_thread = threading.Thread(target=self._console_input_handler)
            input_thread.daemon = True
            input_thread.start()
            
            # Loop principale
            while self.client.running:
                time.sleep(1)
            
            return True
        
        except KeyboardInterrupt:
            print("\nInterruzione da tastiera. Arresto in corso...")
            return False
        
        finally:
            self.client.stop()
    
    def _console_input_handler(self):
        """Gestisce l'input da console per i comandi"""
        while self.client.running:
            try:
                cmd = input()
                if cmd.lower() == 'pause':
                    self.client.send_command('pause')
                elif cmd.lower() == 'resume':
                    self.client.send_command('resume')
                elif cmd.lower() == 'stop':
                    self.client.send_command('stop')
                elif cmd.lower() == 'exit':
                    self.client.running = False
                    break
                else:
                    print(f"Comando non riconosciuto: {cmd}")
            except EOFError:
                break  # Gestisce la chiusura dell'input (es. quando lo script viene terminato)


def main():
    """Funzione principale"""
    # Parsing degli argomenti
    parser = argparse.ArgumentParser(description='Client Python per simulazioni MATLAB')
    parser.add_argument('--host', default='localhost', help='Host su cui ascoltare (default: localhost)')
    parser.add_argument('--port', type=int, default=12345, help='Porta su cui ascoltare (default: 12345)')
    parser.add_argument('--script', help='Script MATLAB da eseguire (opzionale)')
    parser.add_argument('--log', help='File di log (opzionale)')
    parser.add_argument('--no-gui', action='store_true', help='Esegui in modalità headless senza GUI')
    
    args = parser.parse_args()
    
    # Forza la modalità headless (no GUI)
    args.no_gui = True
    
    # Avvia il controller
    controller = SimulationController(args)
    controller.run()


if __name__ == '__main__':
    main()
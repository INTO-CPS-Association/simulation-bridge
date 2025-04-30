# Funzioni per la Simulazione di Particelle

## 1. setupParticleSimulation - Funzione di Inizializzazione

La funzione `setupParticleSimulation` viene chiamata una sola volta all'inizio della simulazione per impostare lo stato iniziale. Deve restituire uno stato iniziale che rappresenta la situazione iniziale delle particelle o degli agenti nella simulazione.

### Parametri

- **params**: Un struct che contiene i parametri necessari per inizializzare la simulazione, come:
  - Numero di agenti
  - Velocità iniziale
  - Limite di velocità
  - Tempo massimo, ecc.

### Restituisce

- **simulationState**: Un struct che contiene le informazioni iniziali per ogni agente (ad esempio, posizione, velocità) e altre variabili pertinenti per la simulazione.

### Esempio di Codice

```matlab
function simulationState = setupParticleSimulation(params)
        % Inizializza lo stato della simulazione
        numAgents = params.numAgents;  % Numero di agenti
        speedLimit = params.speedLimit;  % Velocità massima
        initialPositions = rand(numAgents, 2) * 10;  % Posizioni iniziali casuali
        velocities = rand(numAgents, 2) * speedLimit;  % Velocità iniziali casuali, limitate

        % Stato iniziale
        simulationState = struct(...
                'positions', initialPositions, ...
                'velocities', velocities, ...
                'numAgents', numAgents ...
        );
end
```

---

## 2. stepParticleSimulation - Funzione di Passo della Simulazione

La funzione `stepParticleSimulation` viene chiamata a ogni passo della simulazione per aggiornare lo stato della simulazione. Modifica lo stato attuale in base alle leggi di movimento, come la velocità degli agenti, la posizione, le interazioni, ecc.

### Parametri

- **simulationState**: Un struct che contiene lo stato attuale della simulazione, inclusi la posizione e la velocità degli agenti.
- **params**: Un struct che contiene i parametri della simulazione, come:
  - Tempo tra i passi della simulazione (`timeStep`)
  - Limite di velocità, ecc.

### Restituisce

- **newState**: Un struct che rappresenta lo stato aggiornato della simulazione dopo il passo.
- **data**: Un struct che contiene i dati rilevanti del passo, come le nuove posizioni degli agenti e il tempo trascorso.

### Esempio di Codice

```matlab
function [newState, data] = stepParticleSimulation(simulationState, params)
        % Aggiorna la posizione degli agenti in base alla velocità
        timeStep = params.timeStep;  % Tempo tra i passi della simulazione
        positions = simulationState.positions;
        velocities = simulationState.velocities;

        % Calcola la nuova posizione
        newPositions = positions + velocities * timeStep;

        % Stato aggiornato
        newState = struct('positions', newPositions, 'velocities', velocities, 'numAgents', simulationState.numAgents);

        % Dati del passo
        data = struct('positions', newPositions, 'velocities', velocities, 'elapsedTime', toc);
end
```

---

## 3. checkParticleTermination - Funzione di Terminazione della Simulazione

La funzione `checkParticleTermination` viene chiamata dopo ogni passo della simulazione per verificare se la simulazione deve terminare. La condizione di terminazione può dipendere dal tempo trascorso o da altre variabili, come il raggiungimento di un obiettivo da parte degli agenti.

### Parametri

- **simulationState**: Un struct che contiene lo stato corrente della simulazione, incluse le posizioni degli agenti, le velocità e altri dati.
- **params**: Un struct che contiene i parametri della simulazione.
- **elapsedTime**: Il tempo trascorso dalla partenza della simulazione (in secondi).

### Restituisce

- **isTerminated**: Un valore booleano (`true`/`false`) che indica se la simulazione deve terminare. La simulazione termina se questo valore è `true`.

### Esempio di Codice

```matlab
function isTerminated = checkParticleTermination(simulationState, params, elapsedTime)
        % Controlla se la simulazione è terminata
        if elapsedTime >= params.maxTime
                isTerminated = true;  % La simulazione termina se il tempo massimo è stato raggiunto
        else
                isTerminated = false;  % Altrimenti continua
        end
end
```

# Functions for Particle Simulation

## 1. setupParticleSimulation - Initialization Function

The `setupParticleSimulation` function is called once at the beginning of the simulation to set up the initial state. It must return an initial state representing the starting situation of the particles or agents in the simulation.

### Parameters

- **params**: A struct containing the parameters needed to initialize the simulation, such as: - Number of agents - Initial speed - Speed limit - Maximum time, etc.

### Returns

- **simulationState**: A struct containing the initial information for each agent (e.g., position, velocity) and other relevant variables for the simulation.

### Code Example

```matlab
function simulationState = setupParticleSimulation(params)
                                % Initialize the simulation state
                                numAgents = params.numAgents;  % Number of agents
                                speedLimit = params.speedLimit;  % Maximum speed
                                initialPositions = rand(numAgents, 2) * 10;  % Random initial positions
                                velocities = rand(numAgents, 2) * speedLimit;  % Random initial velocities, limited

                                % Initial state
                                simulationState = struct(...
                                                                'positions', initialPositions, ...
                                                                'velocities', velocities, ...
                                                                'numAgents', numAgents ...
                                );
end
```

---

## 2. stepParticleSimulation - Simulation Step Function

The `stepParticleSimulation` function is called at each simulation step to update the simulation state. It modifies the current state based on motion laws, such as agent velocity, position, interactions, etc.

### Parameters

- **simulationState**: A struct containing the current state of the simulation, including agent positions and velocities.
- **params**: A struct containing the simulation parameters, such as: - Time between simulation steps (`timeStep`) - Speed limit, etc.

### Returns

- **newState**: A struct representing the updated simulation state after the step.
- **data**: A struct containing relevant data from the step, such as the new agent positions and elapsed time.

### Code Example

```matlab
function [newState, data] = stepParticleSimulation(simulationState, params)
                                % Update agent positions based on velocity
                                timeStep = params.timeStep;  % Time between simulation steps
                                positions = simulationState.positions;
                                velocities = simulationState.velocities;

                                % Compute new positions
                                newPositions = positions + velocities * timeStep;

                                % Updated state
                                newState = struct('positions', newPositions, 'velocities', velocities, 'numAgents', simulationState.numAgents);

                                % Step data
                                data = struct('positions', newPositions, 'velocities', velocities, 'elapsedTime', toc);
end
```

---

## 3. checkParticleTermination - Simulation Termination Function

The `checkParticleTermination` function is called after each simulation step to check if the simulation should terminate. The termination condition can depend on elapsed time or other variables, such as agents reaching a goal.

### Parameters

- **simulationState**: A struct containing the current state of the simulation, including agent positions, velocities, and other data.
- **params**: A struct containing the simulation parameters.
- **elapsedTime**: The time elapsed since the start of the simulation (in seconds).

### Returns

- **isTerminated**: A boolean value (`true`/`false`) indicating whether the simulation should terminate. The simulation ends if this value is `true`.

### Code Example

```matlab
function isTerminated = checkParticleTermination(simulationState, params, elapsedTime)
                                % Check if the simulation is terminated
                                if elapsedTime >= params.maxTime
                                                                isTerminated = true;  % The simulation ends if the maximum time is reached
                                else
                                                                isTerminated = false;  % Otherwise, it continues
                                end
end
```

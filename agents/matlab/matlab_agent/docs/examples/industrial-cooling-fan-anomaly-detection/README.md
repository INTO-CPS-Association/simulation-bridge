# Industrial Cooling Fan Anomaly Detection Algorithm

This example presents a pre-developed anomaly detection algorithm for an industrial cooling fan, based on Support Vector Machine (SVM) models.

> Reference example:
> https://it.mathworks.com/help/predmaint/ug/industrial-cooling-fan-anomaly-detection-with-docker-deployment.html#CoolingFanAnomalyDetectionExample-3

## Table of Contents

- [Industrial Cooling Fan Anomaly Detection Algorithm](#industrial-cooling-fan-anomaly-detection-algorithm)
  - [Table of Contents](#table-of-contents)
  - [Usage](#usage)
  - [Matlab Agent Integration](#matlab-agent-integration)
  - [Simulation Details](#simulation-details)
    - [Advantages of Simulation](#advantages-of-simulation)
    - [Algorithm Overview](#algorithm-overview)
    - [Results](#results)
    - [Technical Requirements](#technical-requirements)

## Usage

Before running the simulation, you need to configure the Matlab agent by setting the simulation folder path in the `config.yaml` file under the simulation section:

```yaml
simulation:
  path: <path_to_simulation_folder>
```

This path should point to the directory `industrial-cooling-fan-anomaly-detection` containing the simulation files

Once configured, you can initiate the simulation using the API as described below.
The simulation can be initiated via the API by submitting a YAML payload, a template of which is available in the file `api/simulation_anomaly_detection.yaml.example`

```yaml
simulation:
  request_id: abcdef12345 # Unique identifier for the request
  client_id: dt # Client identifier
  simulator: matlab # Specifies MATLAB as the simulation engine
  type: batch # simulation type
  file: simulation.m # Target simulation file
  inputs:
    input1: "placeholder" # Required input parameter (can be any value)
  outputs:
    o1: confMatrixOverall # Overall confusion matrix results
    o2: confMatrixAnomaly1 # Confusion matrix for first anomaly type
    o3: confMatrixAnomaly2 # Confusion matrix for second anomaly type
```

This payload structure configures the API to run the matlab agent with the necessary parameters and capture the three confusion matrix outputs for analysis.

Use the client `use_matlab_agent.py` with the CLI option `--api-payload` to specify the path to this YAML payload file and start the client.

## Matlab Agent Integration

The simulation has been adapted for MATLAB Agent compatibility by wrapping the core logic in a batch-constrained function:

```matlab
function [confMatrixOverall, confMatrixAnomaly1, confMatrixAnomaly2] = simulation(input1)
  % Wrapped simulation logic from CoolingFanAnomalyDetectionExample.m
  % Returns confusion matrices for overall and individual anomaly types
end
```

The integration process involved creating a new `simulation.m` file to preserve the original example code while making it compatible with the agent framework.

At least one input parameter must be provided when calling the function, even if it's just a placeholder value.

## Simulation Details

The algorithm is designed to detect three types of anomalies:

- **Load anomaly**: system overload conditions when demand exceeds design limits.
- **Fan anomaly**: mechanical faults within the motor or fan.
- **Power supply anomaly**: voltage drops affecting the system.

Using a Simulink model that integrates thermal, mechanical, and electrical components, synthetic data representing both normal and anomalous conditions are generated. Anomalies are introduced randomly during simulations to create a diverse and extensive dataset for training the model.

### Advantages of Simulation

- **Controlled generation of realistic and balanced data**, with accurately represented anomalies, eliminating the need for costly and difficult-to-obtain real-world data.
- **Ability to introduce multiple simultaneous anomalies** and observe how they manifest across various sensor signals (voltage, power, temperature).
- **Flexibility to repeat experiments under varying conditions and parameters**, accelerating the development and refinement of the model.
- **Support for effective feature engineering**, through time-window segmentation and specialized diagnostic tools.

### Algorithm Overview

The final algorithm consists of three independent SVM classifiers, each trained to recognize a single type of anomaly. These models collectively handle cases of simultaneous anomalies by combining their predictions.

Testing on validation datasets demonstrates strong detection performance across all anomaly types, confirming the effectiveness of the simulation-driven development approach.

### Results

Simulation enables the creation and validation of robust predictive maintenance algorithms in a controlled environment, significantly reducing the time and cost compared to using only real data.

### Technical Requirements

The following MATLAB toolboxes are required:

- **Instrument Control Toolbox**
- **Predictive Maintenance Toolbox**
- **Signal Processing Toolbox**
- **Simscape**
- **Simscape Electrical**
- **Simulink**
- **System Identification Toolbox**
- **Statistics and Machine Learning Toolbox**

# Matlab Simulation – Requirements & Constraints

## Batch Simulation

A batch simulation is executed by providing a complete set of input parameters at the start. The simulation then runs internally to completion without producing intermediate outputs. Once finished, it returns a final output containing the complete results of the simulation.

This mode is suitable for scenarios where real-time observation is not required and the focus is on analyzing the final state or aggregated outcomes of the simulation.

---

## Streaming Simulation

An Streaming simulation is designed to receive a predefined input configuration at startup and continuously produce real-time outputs during execution. These outputs reflect the internal state of the simulation at each step and are made available to external systems (e.g., The Simulation Bridge) without halting the simulation.

### 1. Function Definition

- The simulation must be contained within a **single MATLAB function**.
- All **simulation inputs** must be **formal parameters of the function**.
- The **order** of parameters in the YAML file must **exactly match** the order of the function arguments.

```matlab
function run_simulation(param1, param2, ..., paramN)
    % Core simulation logic
end
```

### 2. Input Binding

The function must have a clear and organized signature, without dependencies on global variables or dynamic inputs.

- Inputs must exclusively be formal parameters of the function.
- Inputs via `input()`, `eval()`, or other dynamic methods are not allowed.
- Each parameter must be clearly documented to ensure code readability and maintainability.

This structure ensures that the simulation is modular, predictable, and easily integrable with the Simulation Bridge.

YAML parameters are extracted by the Simulation Bridge and passed directly to the function. Each parameter in the YAML file corresponds to a nominal argument of the function. No intermediate manipulation: the binding is direct and automatic.

### 3. Output Handling

The simulation must save data to be shared with the Simulation Bridge in a `.mat` file at each iteration.

#### Constraints on `.mat` Files

- The `.mat` file name is flexible but must be constant and known to the Simulation Bridge.
- The content of the `.mat` file must be a structured MATLAB variable (typically a struct) containing the necessary data.
- The structure can be freely defined but must include all data required by the Bridge.

#### Robust Saving

To avoid partial reads, atomic saving is mandatory, for example:

```matlab
save('matfile/tmp_file.mat', 'simulation_data');
movefile('matfile/tmp_file.mat', 'matfile/simulation_data.mat');
```

This ensures that the Bridge always reads complete and valid files. The `.mat` file must be overwritten at each iteration with the updated state.

### Additional Notes

> No restrictions on the naming of the function or internal variables.
>
> Support for interactive inputs (`input()`, `uicontrol`, etc.) may be introduced in the future but is not currently handled.
>
> The structure is designed for automated simulations. Interactivity will be considered in later phases.

---

## Interactive Simulation

A Interactive simulation combines elements of both streaming and batch modes. It allows the user to send inputs dynamically during the simulation run, which can alter the ongoing scenario. At the same time, the simulation continuously sends real-time outputs reflecting its current state.

## Author

<div align="left" style="display: flex; align-items: center; gap: 15px;">
  <img src="../../../images/profile.jpg" width="60" style="border-radius: 50%; border: 2px solid #eee;"/>
  <div>
    <h3 style="margin: 0;">Marco Melloni</h3>
    <div style="margin-top: 5px;">
      <a href="https://www.linkedin.com/in/marco-melloni/">
        <img src="https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin"/>
      </a>
      <a href="https://github.com/marcomelloni" style="margin-left: 8px;">
        <img src="https://img.shields.io/badge/GitHub-Profile-black?style=flat-square&logo=github"/>
      </a>
    </div>
  </div>
</div>

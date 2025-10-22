# Simul8 Simulation – Guidelines and Best Practices

## Batch Simulation

A batch simulation is executed by providing a complete set of input parameters at the start. The simulation then runs internally to completion without producing intermediate outputs. Once finished, it returns a final output containing the complete results of the simulation.

This mode is suitable for scenarios where real-time observation is not required and the focus is on analyzing the final state or aggregated outcomes of the simulation.

### Batch Requirements
The inputs must be used via. Visual Logic defined within the simulation.

The the simulation file used must be configured for this type of invocation. 
- ``inputSheet``and `outputSheet` must be created manually in the simulation.
- A "On Simulation Open" visual logic block must be created, which contains: `File to Sheet    "input.csv" ,  inputSheet[1,1]`
- The data which the simulation manipulates should be put into `outputSheet`
- A "End Run Logic" Visual Logic Block must be created containing the wanted logic for creating the data which you want exported. Hence it needs to contain `Sheet to File    "output.csv" ,  outputSheet[1,1]`


The order of parameters in the YAML file must align **precisely** with the order of the function arguments. The Simulation Bridge extracts these parameters from the YAML file and passes them directly to the function without any intermediate processing. Each YAML parameter corresponds to a specific function argument, ensuring a direct and automatic binding.

#### Example
#### Input in simulation.yaml 
In this example:
```
- Inputs: 
run_time: 500
columns: [co2, energy]
    r1: [25, 100]
    r2: [25, 200]
- Outputs: 
total_co2: Total CO2
total_energy: Total Energy <br>
```
Below is an example of the "On Simulation Open" Visual Logic  :

```python
File to Sheet "input.csv" , inputSheet[1,1]
``` 
<br>
You need to create visual logic, which will use the "input.csv".
Below is an example of visual logic in the "End Run Logic" :
##### Visual Logic
```python
SET outputSheet[1,1]  =  "Total CO2"
SET outputSheet[2,1]  =  "Total Energy"
SET outputSheet[1,2]  =  inputSheet[1,2]+inputSheet[1,3]
SET outputSheet[2,2]  =  inputSheet[2,2]+inputSheet[2,3]
Sheet to File    "output.csv" ,  outputSheet[1,1]
```
*IMPORTANT* The Headers, here seen by the SET outputSheet[1,1]  =  "Total CO2" and  SET outputSheet[2,1]  =  "Total Energy" needs to match the simulation request output text i.e total_co2: Total CO2. If the two do not match, the value in the output defaults to 0.




This structure is needed to convert the input data to a csv file.

#### References

For additional guidance, refer to the example files located in the `examples/` folder:

- `simulation_batch.s8`

This file provide reference implementations that can help in structuring your simulation logic.

#### Notes

No additional constraints are imposed on the implementation. The simulation file should be designed to meet the specific requirements of the simulation scenario.


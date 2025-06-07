function generateData(mode, nSim)
% mode = 'training' or 'streaming'
% Update to use generateSimulationEnsemble function

%   Copyright 2023 The MathWorks, Inc.

rng('default') %To reset random stream for reproducibility

%% Define nominal/default values
dayInSeconds = 60*60*24;
DefaultModelParameters = struct(...
    'ConvectionFanPowerMax', 5, ...
    'ConvectionFanPowerMin', 0, ...
    'ConvectionFanPowerStartTime', 0, ...
    'ConvectionFanPowerTimeMin', 1.5*dayInSeconds, ...
    'DCSourceNumAnomalies', 4, ...
    'DCSourceVoltageDrop', 3, ...
    'DCSourceVoltageDropDuration', 60, ...
    'DCSourceVoltageNominal', 12, ...
    'DragCoeffNominal', 8e-8, ...
    'DragIncreaseAmplitude', 8e-7, ...
    'DragIncreaseDuration', 60, ...
    'DragNoiseVariance', 10, ...
    'DragNumAnomalies', 4, ...
    'ExternalTempIncreaseAmplitude', 30, ...
    'ExternalTempIncreaseDuration', 60, ...
    'ExternalTempNumAnomalies', 4, ...
    'SimEndTime', dayInSeconds, ...
    'ThermalHeatCoeffMax', 1000, ...
    'ThermalHeatCoeffMin', 1, ...
    'ThermalHeatCoeffStartTime', 0, ...
    'ThermalHeatCoeffTimeMin', 1.5*dayInSeconds, ...
    'RngSeed', 1);

%% Create variations on nominal values.
DefaultModelParameters.DCSourceNumAnomalies = 10;
DefaultModelParameters.ExternalTempNumAnomalies = 10;
DefaultModelParameters.DragNumAnomalies = 10;

%% Create Simulation Inputs
addpath(fullfile(pwd, 'industrial-cooling-fan-anomaly-detection', 'Data_Generator'));
mdl = 'CoolingFanWithFaults';
load_system(mdl)
simInp = Simulink.SimulationInput(mdl);

if strcmpi(mode, 'training')
   simInp = setModelParameter(simInp,'SimulationMode','Normal');
   set_param(mdl, 'EnablePacing', 'off'),
   %simInp = setModelParameter(simInp,'RapidAcceleratorUpToDateCheck','off');
   numSim = nSim;
else   
   simInp = setModelParameter(simInp,'SimulationMode','Normal');
   set_param(mdl, 'EnablePacing', 'on'), set_param(mdl, 'PacingRate', 0.1)
   numSim = 1;
end

%Set initial values for degradation parameters, creates models different initial
%conditions for each system
ConvectionFanPowerMax = generateValues(DefaultModelParameters.ConvectionFanPowerMax,0.2,numSim);
ConvectionFanPowerTimeMin = generateValues(DefaultModelParameters.ConvectionFanPowerTimeMin,0.2,numSim, [DefaultModelParameters.SimEndTime, inf]);
ThermalHeatCoeffMax = generateValues(DefaultModelParameters.ThermalHeatCoeffMax,0.2,numSim);
ThermalHeatCoeffTimeMin = generateValues(DefaultModelParameters.ThermalHeatCoeffTimeMin,0.2,numSim, [DefaultModelParameters.SimEndTime, inf]);
RngSeed = randperm(1000,numSim);

%Set nominal disturbance amplitudes
DCSourceVoltageDrop = generateValues(DefaultModelParameters.DCSourceVoltageDrop,0.2,numSim, [0 inf]);
DragIncreaseAmplitude = generateValues(DefaultModelParameters.DragIncreaseAmplitude,0.2,numSim, [0 inf]);
ExternalTempIncreaseAmplitude = generateValues(DefaultModelParameters.ExternalTempIncreaseAmplitude,0.2,numSim, [0 inf]);

%Set nominal disturbance durations
DCSourceVoltageDropDuration = generateValues(DefaultModelParameters.DCSourceVoltageDropDuration,0.2,numSim, [20 120]);
DragIncreaseDuration = generateValues(DefaultModelParameters.DragIncreaseDuration,0.2,numSim, [20 120]);
ExternalTempIncreaseDuration = generateValues(DefaultModelParameters.ExternalTempIncreaseDuration,0.2,numSim, [20 120]);

allSimInp = [];
for ctS = 1:numSim
    ModelParameters = DefaultModelParameters;
    ModelParameters.ConvectionFanPowerMax = ConvectionFanPowerMax(ctS);
    ModelParameters.ConvectionFanPowerTimeMin = ConvectionFanPowerTimeMin(ctS);
    ModelParameters.ThermalHeatCoeffMax = ThermalHeatCoeffMax(ctS);
    ModelParameters.ThermalHeatCoeffTimeMin = ThermalHeatCoeffTimeMin(ctS);
    ModelParameters.RngSeed = RngSeed(ctS);
    
    ModelParameters.DCSourceVoltageDrop = DCSourceVoltageDrop(ctS);
    ModelParameters.DragIncreaseAmplitude = DragIncreaseAmplitude(ctS);
    ModelParameters.ExternalTempIncreaseAmplitude = ExternalTempIncreaseAmplitude(ctS);
    
    ModelParameters.DCSourceVoltageDropDuration = DCSourceVoltageDropDuration(ctS);
    ModelParameters.DragIncreaseDuration = DragIncreaseDuration(ctS);
    ModelParameters.ExternalTempIncreaseDuration = ExternalTempIncreaseDuration(ctS);

    simInpNew = simInp;
    fnames = fieldnames(ModelParameters);
    for ct=1:numel(fnames)
        simInpNew = setVariable(simInpNew,fnames{ct},ModelParameters.(fnames{ct}),'Workspace',mdl);
    end
    
    allSimInp = [allSimInp; simInpNew];
end

% If Data folder exists
folderPath = fullfile(pwd, 'industrial-cooling-fan-anomaly-detection', 'Data');
if isfolder(folderPath)
    % Delete all files
    delete(fullfile(folderPath, '*.mat'))
else
    mkdir(folderPath);
end

location = fullfile(pwd,'industrial-cooling-fan-anomaly-detection','Data');
[status,E] = generateSimulationEnsemble(allSimInp,location, 'useparallel', true, 'ShowProgress', false);
end

function values = generateValues(Nominal,stddev_percent,numPoints,range)

pd = makedist('Normal','mu',Nominal,'sigma',stddev_percent*Nominal);
if nargin > 3
    pd = truncate(pd,range(1),range(2));
end
values = random(pd,numPoints,1);
end

% LocalWords:  Inp useparallel

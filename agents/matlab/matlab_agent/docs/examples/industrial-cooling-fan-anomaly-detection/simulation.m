function [confMatrixOverall, confMatrixAnomaly1, confMatrixAnomaly2] = simulation(input1)
    % Add necessary paths and open Simulink model
    addpath(pwd);
    addpath('industrial-cooling-fan-anomaly-detection/Data_Generator/', 'industrial-cooling-fan-anomaly-detection/Data_Generator/VaryingConvectionLib/');
    mdl = "CoolingFanWithFaults";
    open_system(mdl);

    % Logic to check if data generation is needed
    generateFlag = false;
    if isfolder('./industrial-cooling-fan-anomaly-detection/Data')
        folderContent = dir('Data/CoolingFan*.mat');
        if isempty(folderContent)
            generateFlag = true;
        else
            numSim = numel(folderContent);
        end
    else
        generateFlag = true;
    end

    if generateFlag
        numSim = 4;
        rng("default");
        generateData('training', numSim);
    end

    % Load ensemble datastore and select variables
    ensemble = simulationEnsembleDatastore('./industrial-cooling-fan-anomaly-detection/Data');
    ensemble.SelectedVariables = ["Signals", "Anomalies"];

    % Split ensemble into train/test/validation
    trainEnsemble = subset(ensemble, 1:numSim-3);
    testEnsemble = subset(ensemble, numSim-2:numSim-1);
    validationEnsemble = subset(ensemble, numSim);

    % Prepare training data
    trainingData = trainEnsemble.readall;
    anomaly_data = vertcat(trainingData.Anomalies{:});
    yTrainAnomaly1 = logical(anomaly_data.Data(:,1));
    yTrainAnomaly2 = logical(anomaly_data.Data(:,2));
    yTrainAnomaly3 = logical(anomaly_data.Data(:,3));

    windowSize = 2000;
    sensorDataTrain = vertcat(trainingData.Signals{:});

    ensembleTableTrain1 = generateEnsembleTable(sensorDataTrain.Data, yTrainAnomaly1, windowSize);
    ensembleTableTrain2 = generateEnsembleTable(sensorDataTrain.Data, yTrainAnomaly2, windowSize);
    ensembleTableTrain3 = generateEnsembleTable(sensorDataTrain.Data, yTrainAnomaly3, windowSize);

    ensembleTableTrain1_reduced = downsampleNormalData(ensembleTableTrain1);
    ensembleTableTrain2_reduced = downsampleNormalData(ensembleTableTrain2);
    ensembleTableTrain3_reduced = downsampleNormalData(ensembleTableTrain3);

    % Extract features
    featureTableTrain1 = diagnosticFeatures(ensembleTableTrain1_reduced);
    featureTableTrain2 = diagnosticFeatures(ensembleTableTrain2_reduced);
    featureTableTrain3 = diagnosticFeatures(ensembleTableTrain3_reduced);

    % Train SVM models
    m.m1 = fitcsvm(featureTableTrain1, 'Anomaly', 'Standardize', true, 'KernelFunction', 'gaussian');
    m.m2 = fitcsvm(featureTableTrain2, 'Anomaly', 'Standardize', true, 'KernelFunction', 'gaussian');
    m.m3 = fitcsvm(featureTableTrain3, 'Anomaly', 'Standardize', true, 'KernelFunction', 'gaussian');

    % Test on test dataset
    testData = testEnsemble.readall;
    anomaly_data_test = vertcat(testData.Anomalies{:});

    yTestAnomaly1 = logical(anomaly_data_test.Data(:,1));
    yTestAnomaly2 = logical(anomaly_data_test.Data(:,2));
    yTestAnomaly3 = logical(anomaly_data_test.Data(:,3));

    sensorDataTest = vertcat(testData.Signals{:});

    ensembleTableTest1 = generateEnsembleTable(sensorDataTest.Data, yTestAnomaly1, windowSize);
    ensembleTableTest2 = generateEnsembleTable(sensorDataTest.Data, yTestAnomaly2, windowSize);
    ensembleTableTest3 = generateEnsembleTable(sensorDataTest.Data, yTestAnomaly3, windowSize);

    featureTableTest1 = diagnosticFeatures(ensembleTableTest1);
    featureTableTest2 = diagnosticFeatures(ensembleTableTest2);
    featureTableTest3 = diagnosticFeatures(ensembleTableTest3);

    results1 = m.m1.predict(featureTableTest1(:, 2:end));
    results2 = m.m2.predict(featureTableTest2(:, 2:end));
    results3 = m.m3.predict(featureTableTest3(:, 2:end));

    labelArray = {'Normal', 'Anomaly1', 'Anomaly2', 'Anomaly3', 'Anomaly12', 'Anomaly13', 'Anomaly23', 'Anomaly123'}';

    yT = [featureTableTest1.Anomaly, featureTableTest2.Anomaly, featureTableTest3.Anomaly];
    yCategoricalT = labelArray(sum(yT .* 2.^(size(yT,2)-1:-1:0), 2) + 1, 1);
    yCategoricalT = categorical(yCategoricalT);

    yHat = [results1, results2, results3];
    yCategoricalTestHat = labelArray(sum(yHat .* 2.^(size(yHat,2)-1:-1:0), 2) + 1, 1);
    yCategoricalTestHat = categorical(yCategoricalTestHat);

    % Compute confusion matrices as output
    confMatrixOverall = confusionmat(yCategoricalT, yCategoricalTestHat);
    confMatrixAnomaly1 = confusionmat(featureTableTest1.Anomaly, results1);
    confMatrixAnomaly2 = confusionmat(featureTableTest2.Anomaly, results2);

    % Optionally close Simulink model
    close_system(mdl, 0);
end

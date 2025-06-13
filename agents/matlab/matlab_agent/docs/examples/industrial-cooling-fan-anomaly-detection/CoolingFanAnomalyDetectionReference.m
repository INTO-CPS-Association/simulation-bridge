%% CoolingFanAnomalyDetectionExample
% This is the original example simulation that has been copied and modified to
% support batch constraints inside simulation.m. The current file serves as a reference
% for the original implementation before the modifications were made to handle
% batch processing constraints.

addpath('Data_Generator/', 'Data_Generator/VaryingConvectionLib/');
mdl = "CoolingFanWithFaults";
open_system(mdl)

generateFlag = false;
if isfolder('./Data')
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
    numSim = 5;
    rng("default");
    generateData('training', numSim);
end

ensemble = simulationEnsembleDatastore(pwd,'simulation','Data');
ensemble.SelectedVariables = ["Signals", "Anomalies"];

trainEnsemble = subset(ensemble, 1:numSim-3);
testEnsemble = subset(ensemble, numSim-2:numSim-1);
validationEnsemble = subset(ensemble, numSim);

tempData = trainEnsemble.read;
signal_data = tempData.Signals{1};
anomaly_data = tempData.Anomalies{1};

h = figure;
tiledlayout("vertical");
ax1 = nexttile; plot(signal_data.Data(:,1));
ax2 = nexttile; plot(signal_data.Data(:,2));
ax3 = nexttile; plot(signal_data.Data(:,3));
ax4 = nexttile; plot(anomaly_data.Data(:,1), 'bx', 'MarkerIndices',find(anomaly_data.Data(:,1)>0.1), 'MarkerSize', 5); hold on;
plot(anomaly_data.Data(:,2), 'ro', 'MarkerIndices',find(anomaly_data.Data(:,2)>0.1), 'MarkerSize', 5);
plot(anomaly_data.Data(:,3), 'square', 'Color', 'g', 'MarkerIndices',find(anomaly_data.Data(:,3)>0.1), 'MarkerSize', 5); 
linkaxes([ax1 ax2 ax3 ax4],'x')
ylim([0, 2]);
legend("Load Anomaly", "Fan Anomaly", "Power Supply Anomaly", 'Location', 'bestoutside')
set(h,'Units','normalized','Position',[0 0 1 .8]);

trainingData = trainEnsemble.readall;
anomaly_data = vertcat(trainingData.Anomalies{:});
labelArray={'Normal','Anomaly1','Anomaly2', 'Anomaly3', 'Anomaly12','Anomaly13','Anomaly23','Anomaly123'}';
yCategoricalTrain=labelArray(sum(anomaly_data.Data.*2.^(size(anomaly_data.Data,2)-1:-1:0),2)+1,1);
yCategoricalTrain=categorical(yCategoricalTrain);
summary(yCategoricalTrain);

yTrainAnomaly1=logical(anomaly_data.Data(:,1));
yTrainAnomaly2=logical(anomaly_data.Data(:,2));
yTrainAnomaly3=logical(anomaly_data.Data(:,3));

windowSize=2000;
sensorDataTrain = vertcat(trainingData.Signals{:});
ensembleTableTrain1 = generateEnsembleTable(sensorDataTrain.Data,yTrainAnomaly1,windowSize);
ensembleTableTrain2 = generateEnsembleTable(sensorDataTrain.Data,yTrainAnomaly2,windowSize);
ensembleTableTrain3 = generateEnsembleTable(sensorDataTrain.Data,yTrainAnomaly3,windowSize);

ensembleTableTrain1_reduced = downsampleNormalData(ensembleTableTrain1);
ensembleTableTrain2_reduced = downsampleNormalData(ensembleTableTrain2);
ensembleTableTrain3_reduced = downsampleNormalData(ensembleTableTrain3);

startApp = false;
if startApp 
    diagnosticFeatureDesigner; %#ok<UNRCH>
end

featureTableTrain1 = diagnosticFeatures(ensembleTableTrain1_reduced);
featureTableTrain2 = diagnosticFeatures(ensembleTableTrain2_reduced);
featureTableTrain3 = diagnosticFeatures(ensembleTableTrain3_reduced);

head(featureTableTrain1);

m.m1 = fitcsvm(featureTableTrain1, 'Anomaly', 'Standardize',true, 'KernelFunction','gaussian');
m.m2 = fitcsvm(featureTableTrain2, 'Anomaly', 'Standardize',true, 'KernelFunction','gaussian');
m.m3 = fitcsvm(featureTableTrain3, 'Anomaly', 'Standardize',true, 'KernelFunction','gaussian');

save anomalyDetectionModelSVM m

testData = testEnsemble.readall;
anomaly_data_test = vertcat(testData.Anomalies{:});

yTestAnomaly1=logical(anomaly_data_test.Data(:,1));
yTestAnomaly2=logical(anomaly_data_test.Data(:,2));
yTestAnomaly3=logical(anomaly_data_test.Data(:,3));

sensorDataTest = vertcat(testData.Signals{:});
ensembleTableTest1 = generateEnsembleTable(sensorDataTest.Data,yTestAnomaly1,windowSize);
ensembleTableTest2 = generateEnsembleTable(sensorDataTest.Data,yTestAnomaly2,windowSize);
ensembleTableTest3 = generateEnsembleTable(sensorDataTest.Data,yTestAnomaly3,windowSize);

featureTableTest1 = diagnosticFeatures(ensembleTableTest1);
featureTableTest2 = diagnosticFeatures(ensembleTableTest2);
featureTableTest3 = diagnosticFeatures(ensembleTableTest3);

results1 = m.m1.predict(featureTableTest1(:, 2:end));
results2 = m.m2.predict(featureTableTest2(:, 2:end));
results3 = m.m3.predict(featureTableTest3(:, 2:end));

yT = [featureTableTest1.Anomaly, featureTableTest2.Anomaly, featureTableTest3.Anomaly];
yCategoricalT = labelArray(sum(yT.*2.^(size(yT,2)-1:-1:0),2)+1,1);
yCategoricalT = categorical(yCategoricalT);

yHat = [results1, results2, results3];
yCategoricalTestHat=labelArray(sum(yHat.*2.^(size(yHat,2)-1:-1:0),2)+1,1);
yCategoricalTestHat=categorical(yCategoricalTestHat);

figure
confusionchart(yCategoricalT, yCategoricalTestHat)

figure
tiledlayout(1,3);
nexttile; confusionchart(featureTableTest1.Anomaly, results1);
nexttile; confusionchart(featureTableTest2.Anomaly, results2);
nexttile; confusionchart(featureTableTest3.Anomaly, results3);

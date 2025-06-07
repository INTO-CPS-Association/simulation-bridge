function [predictedAnomalies, trueAnomalies] = detectCoolingFanAnomaly(x, y)
% x is a n by 3 double matrix of the raw measurement of cooling fan data
% x can also be a timetable from the Kafka cooling fan data stream
% y is a n by 1 categorical array which could be omitted when unknown
% anomalyDetectionModel is the struct of model obtained from training. It 
% includes the model object used for prediction, raw data normalization 
% information, and function handles for feature extraction.

%   Copyright 2023 The MathWorks, Inc.

model=load('anomalyDetectionModelSVM.mat');
anomalyDetectionModel=model.m;
% Do we extract the same features for each output or do we extract diff
% features?
windowSize = size(x, 1);
ensembleTable1 = generateEnsembleTable(x,y(:,1),windowSize);
ensembleTable2 = generateEnsembleTable(x,y(:,2),windowSize);
ensembleTable3 = generateEnsembleTable(x,y(:,3),windowSize);

featureTable1 = diagnosticFeatures_streaming(ensembleTable1);
featureTable2 = diagnosticFeatures_streaming(ensembleTable2);
featureTable3 = diagnosticFeatures_streaming(ensembleTable3);

% Predict
results1 = anomalyDetectionModel.m1.predict(featureTable1);
results2 = anomalyDetectionModel.m2.predict(featureTable2);
results3 = anomalyDetectionModel.m3.predict(featureTable3);

predictedAnomalies = [results1, results2, results3];
trueAnomalies = [ensembleTable1.Anomaly, ensembleTable2.Anomaly, ensembleTable3.Anomaly];
end

% LocalWords:  SVM

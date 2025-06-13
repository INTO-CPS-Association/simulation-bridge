function out = downsampleNormalData(ensemble)
%

%   Copyright 2023 The MathWorks, Inc.

% Find all elements that have normal label (i.e Anomaly = 0)
index1 = find(ensemble.Anomaly~=1);
% Create a random index vector that selects 87.5% of all rows that have Anomaly=0 
index11 = randsample(numel(index1), floor(numel(index1)*3.5/4));

% Create out and delete all rows corresponding to indices specified by
% index11
out = ensemble;
out(index1(index11),:) = [];

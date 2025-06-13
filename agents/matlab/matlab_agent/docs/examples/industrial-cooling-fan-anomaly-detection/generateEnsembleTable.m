function ensembleTable = generateEnsembleTable(x,y,ws)
%

%   Copyright 2023 The MathWorks, Inc.
    
parfor j=1:floor(size(x,1)/ws)
    index = ((j-1)*2000)+1:2000*j;
    signals{j} = array2table(x(index,:), 'VariableNames', {'Signal1', 'Signal2', 'Signal3'});
    labels{j} = sum(y(index))>40;
end

out = [signals', labels'];

if ~isempty(y)
    ensembleTable = cell2table(out, 'VariableNames', {'Signal', 'Anomaly'});  
else
    ensembleTable = cell2table(out, 'VariableNames', {'Signal'}); 
end

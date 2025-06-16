classdef IndexIterator < handle
    %UNTITLED3 Summary of this class goes here
    %   Detailed explanation goes here

%   Copyright 2023 The MathWorks, Inc.

    properties
        StartValue
        EndValue
        StepSize
        WindowSize
        %Overlap
        CurrentIndexValue
        EndofRangeFlag = false;
    end

    methods
        function obj = IndexIterator(startValue,endValue, varargin)
            %UNTITLED3 Construct an instance of this class
            %   Detailed explanation goes here
            obj.StartValue = startValue;
            obj.EndValue = endValue;
            if ~isempty(varargin)
                try
                    obj.WindowSize = varargin{1};
                    obj.StepSize = varargin{2};
                catch
                end
            end
        end

        function [range, indices] = nextFrameIndex(obj)
            
            if isempty(obj.CurrentIndexValue)
                obj.CurrentIndexValue = obj.StartValue;
            end

            range = [obj.CurrentIndexValue, obj.CurrentIndexValue+obj.WindowSize-1];

            if nargin == 2
                indices = range(1):obj.StepSize:range(2);
            end

            obj.CurrentIndexValue = range(2)+1;
             
            if obj.CurrentIndexValue+1 > obj.EndValue
                obj.EndofRangeFlag = true;
            end
        end

        function reset(obj)
            %METHOD1 Summary of this method goes here
            %   Detailed explanation goes here
            obj.CurrentIndexValue = obj.StartValue;
            obj.EndofRangeFlag = false;
        end
    end
end

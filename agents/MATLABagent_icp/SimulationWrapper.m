classdef (Abstract) SimulationWrapper < handle
    properties
        shm
        isRunning
    end
    
    methods
        function obj = SimulationWrapper()
            obj.setupSharedMemory();
            obj.isRunning = false;
        end
        
        function setupSharedMemory(obj)
            filename = 'shared_memory.bin';
            if ~exist(filename, 'file')
                f = fopen(filename, 'wb');
                fwrite(f, zeros(128, 1), 'uint8'); % File di 128 bytes
                fclose(f);
            end
            obj.shm = memmapfile(filename, 'Format', ...
                {'double', [10,1], 'input_data'; ...
                 'double', [5,1], 'output_data'; ...
                 'uint8', 1, 'input_ready'; ...
                 'uint8', 1, 'output_ready'; ...
                 'uint8', 1, 'start_signal'}, ...
                 'Writable', true);
        end
        
        function run(obj)
            % Attendi il segnale di start da Python
            while obj.shm.Data.start_signal ~= 1
                pause(0.1);
            end
            obj.shm.Data.start_signal = uint8(0);
            
            % Avvia simulazione
            obj.isRunning = true;
            obj.initialize();
            while obj.isRunning
                if obj.shm.Data.input_ready == 1
                    input = obj.shm.Data.input_data;
                    obj.shm.Data.input_ready = uint8(0);  % <-- Corretto
                    obj.update(input);
                    obj.shm.Data.output_data = obj.getOutput();
                    obj.shm.Data.output_ready = uint8(1);  % <-- Corretto
                end
                obj.isRunning = ~obj.checkTermination();
                pause(0.01);
            end
            obj.cleanup();
        end
        
        function cleanup(obj)
            clear obj.shm;
            delete('shared_memory.bin');
        end
    end
    
    methods (Abstract)
        initialize(obj)
        update(obj, input)
        output = getOutput(obj)
        stop = checkTermination(obj)
    end
end
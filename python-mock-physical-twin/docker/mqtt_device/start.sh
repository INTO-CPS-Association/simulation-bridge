#!/bin/bash

# Running Interactive
#docker run -it --entrypoint /bin/bash registry.gitlab.com/carmony-project/carmony-http-api:0.1 -s

docker run --name=physical_twin_emulator \
    -p 5555:5555 \
    --restart always \
    -v $(pwd)/mqtt_acc_config.yaml:/app/emulator_conf.yaml \
    -v $(pwd)/accelerometer_data_seconds.csv:/app/data/accelerometer_data_seconds.csv \
    -d registry.gitlab.com/piconem-university/projects/digital-twin/physical-twin-emulator:0.1
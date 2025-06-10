#!/bin/bash
python3 ./main.py \
  --discriminator "1234" \
  --pin "20202021" \
  --nodeID "1" \
  --endpointID "1" \
  --target_device_serial_num "440266221" \
  --use_json_list False \
  --single_run_count "1" \
  --multiple_run_count "0" \
  --test_list_run_count "0" \
  --test_plan_run_count "1" \
  --target_device_ip "10.4.215.46" \
  --test_list "Test_TC_CC_3_1" \
  --factory_reset_device "True"
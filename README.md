# chip-tool-automation

Python script to automate chip-tool commands to perform tests.

## Arguments

- `--chip_path`: Path to the CHIP repo (default: `~/connectedhomeip`)
- `--otbrhex`: The OTBR hex string (default: None).
- `--discriminator`: The discriminator (default: '3840').
- `--pin`: The PIN code (default: '20202021').
- `--nodeID`: The node ID (default: None).
- `--endpointID`: The endpoint ID (default: '1').
- `--target_device_ip`: The target device IP (default: '10.4.215.46').
- `--target_device_serial_num`: The target device serial number (default: None).
- `--test_list`: Comma-separated list of YAML test names to run (default: None).
- `--use_json_list`: Whether to use a JSON file for the test list (default: False).
- `--single_run_count`: The number of single fabric commissioning test runs (default: 1).
- `--multiple_run_count`: The number of multiple fabric commissioning test runs (default: 0).
- `--test_list_run_count`: The number of times to run the whole test list (default: 0).
- `--test_plan_run_count`: The number of times to run a single YAML test plan (default: 0).
- `--toggle_test_run_count`: The number of times to run the toggle test (default: 0).
- `--toggle_sleep_time`: The sleep time between toggle actions in seconds (default: 1).
- `--factory_reset_device`: Whether to factory reset the device before running tests (default: False).
- `--commission_device`: Whether to commission the device (default: False).
- `--use_script_input_json`: If set, loads all arguments from `script_input.json` and ignores other CLI arguments.

## Example Commands

### Run with default arguments

```sh
python3 main.py
```

### Run with custom arguments

```sh
python3 main.py --otbrhex "0e08000000000001000000030000154a0300000c35060004001fffe0020836f26e038696ff5d0708fdb3d465ff59e0860510dfe8b148f078dd4003b4b332687a0a3b030f4f70656e5468726561642d36376261010267ba041015791942db7b3b4cc82db2336d0eb0190c0402a0f7f8" --discriminator "3840" --pin "20202021" --endpointID "1" --target_device_ip "10.4.215.46" --single_run_count 2 --multiple_run_count 3
```

### Run with json file arguments

You can provide all arguments in a JSON file (`script_input.json`) and run the script using:

```sh
python3 main.py --use_script_input_json
```

or with the provided helper script:

```sh
./run_from_json.sh
```

The `script_input.json` file should contain all the arguments as keys, for example:
```json
{
  "otbrhex": "...",
  "discriminator": "1234",
  "pin": "20202021",
  "nodeID": "1",
  "endpointID": "1",
  "target_device_ip": "10.4.215.46",
  "target_device_serial_num": "440266221",
  "use_json_list": false,
  "commission_device": true,
  "single_run_count": 0,
  "multiple_run_count": 0,
  "test_list_run_count": 1,
  "test_plan_run_count": 1,
  "test_list": ["Test_TC_CC_3_1"],
  "factory_reset_device": true
}
```
When `--use_script_input_json` is set, all other CLI arguments are ignored and values from the JSON file are used.

## Explanation of the Loops

### Single Fabric Commissioning Test Loop

The single fabric commissioning test loop runs the `single_fabric_commissioning_test` function for the specified number of times (`single_run_count`). This function performs the following steps:
1. Commissions the device using BLE.
2. Toggles the device on and off.
3. Reads the on-off state.
4. Unpairs the device.

If any error occurs during the test, the error is handled, and the test is terminated.

### Multiple Fabric Commissioning Test Loop

The multiple fabric commissioning test loop runs the `multiple_fabric_commissioning_test` function for the specified number of times (`multiple_run_count`). This function performs the following steps:
1. Commissions the device using BLE on fabric 1.
2. For each fabric predefined on chip-tool:
   1. Opens the commissioning window from fabric 1.
   2. Pairs the device with the pairing code on the new fabric using a new nodeId (here the fabric index).
   3. Toggles the device on and off.
   4. Reads the on-off state.
3. For each commissioned fabric, starting by the last one:
   1. Unpairs the device.

If any error occurs during the test, the error is handled, and the test is terminated.

### Yaml Test List Test Loop

The YAML Test List Test Loop runs a set of YAML-based test scripts as specified in the `test_list` argument or loaded from a JSON file. This loop is controlled by the `test_plan_run_count` argument, which determines how many times the entire test plan is executed. For each run:
1. The device is commissioned using BLE.
2. For each test name in the test list, the script runs the corresponding YAML test using `chiptool.py`.
3. Device logs are collected for each test.
4. After all tests are run, the device is unpaired.
5. If any error occurs during a test, error handling is performed and the loop is terminated early.

This loop is useful for running a batch of YAML-defined tests in a repeatable and automated fashion.

### Toggle Test Loop
The toggle test loop runs the `toggle_test` function for the specified number of times (`toggle_test_run_count`). This test does not require the device to be commissioned, only to be reachable via IP. The function performs the following steps:
1. Connects to the device via telnet
2. Press and release the device button 1
3. Wait a defined amount of time
4. Repeat step 2 and 3 for the number of times specified in `toggle_test_run_count`
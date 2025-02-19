# chip-tool-automation

Python script to automate chip-tool commands to perform tests.

## Arguments

- `--otbrhex`: The OTBR hex string (default: None).
- `--discriminator`: The discriminator (default: '3840').
- `--pin`: The PIN code (default: '20202021').
- `--endpointID`: The endpoint ID (default: '1').
- `--target_device_ip`: The target device IP (default: '10.4.215.46').
- `--single_run_count`: The number of single fabric commissioning test runs (default: 1).
- `--multiple_run_count`: The number of multiple fabric commissioning test runs (default: 1).

## Example Commands

### Run with default arguments

```sh
python3 main.py
```

### Run with custom arguments

```sh
python3 main.py --otbrhex "0e08000000000001000000030000154a0300000c35060004001fffe0020836f26e038696ff5d0708fdb3d465ff59e0860510dfe8b148f078dd4003b4b332687a0a3b030f4f70656e5468726561642d36376261010267ba041015791942db7b3b4cc82db2336d0eb0190c0402a0f7f8" --discriminator "3840" --pin "20202021" --endpointID "1" --target_device_ip "10.4.215.46" --single_run_count 2 --multiple_run_count 3
```

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

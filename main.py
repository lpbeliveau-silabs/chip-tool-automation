from utils import send_cmd, open_commissioning_window, commission_pairing_code, commission_bleThread, CommandError
from utils.jlink_logger import start_reading_device_output, stop_reading_device_output
import argparse
import subprocess
import pexpect
import datetime
import sys
import os
import json
from time import sleep
from typing import Literal, List

discriminator: str = '3840'
pin: str = '20202021'
endpointID: str = '1'
target_device_ip: str = '10.4.215.46'
single_run_count: int = 0
multiple_run_count: int = 0
test_list_run_count: int = 0
test_plan_run_count: int = 0
toggle_test_run_count: int = 0
toggle_sleep_time: int = 1
commission_device: bool = True
device_uart_suffix: str = '_device-uart-logs.txt'
device_rtt_suffix: str = '_device-rtt-logs.txt'
chip_tool_suffix: str = '_chip-tool-logs.txt'
device_uart_error_suffix: str = '_device-uart-error-logs.txt'
device_rtt_error_suffix: str = '_device-rtt-error-logs.txt'
chip_tool_error_suffix: str = '_chip-tool-error-logs.txt'

env = os.environ.copy()

chip_path = os.path.expanduser('~/connectedhomeip')
matter_yamltests_path = os.path.join(chip_path, 'scripts', 'py_matter_yamltests')
matter_idl_path = os.path.join(chip_path, 'scripts', 'py_matter_idl')

existing_pythonpath = os.environ.get("PYTHONPATH", "")
extra_env_path = f"{matter_yamltests_path}:{matter_idl_path}"
if existing_pythonpath:
    extra_env_path = f"{existing_pythonpath}:{extra_env_path}"

def str2bool(value: str) -> bool:
    """
    Convert a string representation of truth to a boolean value.
    Args:
        value (str): The string to convert. Accepts "yes", "true", "t", "1" for True and "no", "false", "f", "0" for False.
    Returns:
        bool: The boolean value.
    Raises:
        argparse.ArgumentTypeError: If the string is not a valid boolean representation.
    """
    if isinstance(value, bool):
        return value
    if value.lower() in ("yes", "true", "t", "1"):
        return True
    elif value.lower() in ("no", "false", "f", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")

def setup_device_logs(output_file: str, target_ip: str, serial_num: str = ""):
    """
    Setup the device logs. This appends a suffix to the output file to mark it in a way the the error handling function can identify it 
    and move it to the error logs files.

    Steps:
    1. Start a tmux session.
    2. Start a screen session in the tmux session.
    3. Start reading device output using RTT. (currently disabled)
    Args:
        output_file_prefix (str): The output file prefix.
    """
    send_cmd(f'tmux new-session -d -s chip_tool_test_session')
    # Screen session to temporary store out logs in uart output_file
    send_cmd(
        f'tmux send-keys -t chip_tool_test_session "screen -L -Logfile {output_file}{device_uart_suffix} //telnet {target_ip} 4901" C-m')
    # TODO: Fix/Verify rtt logging before enabling this
    # Start RTT logging
    # start_reading_device_output(serial_num=serial_num, log_file_path=f'{output_file}{device_rtt_suffix}')


def teardown_device_logs():
    """
    Teardown the device logs.
    Steps:
    1. Kill the tmux session.
    2. Stop reading device output using RTT. (currently disabled)
    """
    send_cmd('tmux kill-session -t chip_tool_test_session')
    # TODO: Fix/Verify rtt logging before enabling this
    # Stop RTT logging
    # stop_reading_device_output()

def verify_device_logs(output_file: str) -> bool:
    """
    Verify the device logs are not empty. Empty logs are interpretted as if the device became unresponsive.
    Steps:
    1. Check the device UART logs for errors.
    2. Check the device RTT logs for errors. (currently disabled)
    
    Args:
        output_file (str): The output file prefix.

    Returns:
        bool: True if no errors are found, False otherwise.
    """
    # Check UART logs
    with open(f'{output_file}{device_uart_suffix}', 'r') as f:
        uart_logs = f.read()
    if not uart_logs:
        print(f'No UART logs found in {output_file}{device_uart_suffix}. Device might be unresponsive.')
        return False

    return True  # TODO: Add RTT log verification when implemented

def setup_test(otbrhex_input: str, target_ip: str) -> str:
    """
    Setup the test environment on the raspberry pi.
    Steps:
    1. Fetch the otbrhex dataset using ot-ctl (if not provided).
    2. Open a telnet session, wake up the device and close the telnet session.

    Args:
        otbrhex_input (str): The OTBR hex string, default is None.
        target_ip (str): The target device IP.
    """
    cmd: str = 'sudo ot-ctl dataset active -x'

    if otbrhex_input == '':
        print(f'===== cmd: {cmd}')
        result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Recover the 1st line of the output ot-ctl dataset active -x, second line being "Done" if successful
        otbrhex_output = result.communicate()[0].decode().splitlines(keepends=False)
        if otbrhex_output[1] != 'Done':
            print(f'Failed to fetch otbrhex dataset')
            return "Error"

        otbrhex_output = otbrhex_output[0]
        print(f'otbrhex_output: {otbrhex_output}')
    else:
        otbrhex_output = otbrhex_input
        print(f'Using provided otbrhex: {otbrhex_output}')

    # Ensure the device is advertising by toggling the button 0
    telnet_cmds = [
        "target button enable"
        "target button press 0",
        "target button release 0",
        "quit"
    ]

    child = pexpect.spawn(f'telnet {target_ip} 4902')
    for cmd in telnet_cmds:
        child.sendline(cmd)
        sleep(0.5)

    child.close()

    return otbrhex_output


def teardown_test():
    """
    Teardown the test environment on the raspberry pi.
    Steps:
    1. Tears down the device logging if it wasn't done already.
    2. Remove the log files that contained no errors (currently disabled).
    """
    teardown_device_logs()
    #TODO: Verify we want to remove the logs
    #send_cmd('rm -rf /tmp/*')

def factory_reset_device():
    """
    Factory reset the device by:
    1. Opening a telnet session.
    2. Sending the factory reset command.
    3. Closing the telnet session.
    """
    telnet_cmds = [
        "device factoryreset",
    ]

    child = pexpect.spawn(f'telnet {target_device_ip} 4901')
    for cmd in telnet_cmds:
        child.sendline(cmd)
        sleep(1)

    child.close()

def handle_error(error_code: int, output_file: str):
    """
    Handle a test failure by:
    1. Printing the error code.
    2. Moving the device logs to the output directory.
    3. Moving the chip-tool logs to the output directory.
    5. Calling the teardown_test function.
    Args:
        error_code (CommandError): The error code.
    """
    print(f'Error: {CommandError.to_string(error_code)}')
    send_cmd(f'mv {output_file}{device_uart_suffix} {output_file}{device_uart_error_suffix}')
    # TODO: Fix/Verify rtt logging before enabling this
    # send_cmd(f'mv {output_file}{device_rtt_suffix} {output_file}{device_rtt_error_suffix}')
    send_cmd(f'mv {output_file}{chip_tool_suffix} {output_file}{chip_tool_error_suffix}')
    teardown_test()

def toggle_test(
        output_dir: str,
        output_file_prefix: str,
        target_ip: str, 
        target_device_serial_num: str,
        run_count: int, 
        sleep_time: int
    ) -> Literal[0, 1]:
    """
    Perform a toggle test on the device.
    Steps:
    1. Open a telnet session.
    2. Press and release the button 1 on the device, this should toggle the device's light.
    3. Wait for a short period of time (in seconds).
    4. repeat step 2 and 3 for the specified number of times.
    5. Close the telnet session.

    Args:
        output_dir (str): The output path of the chip-tool logs.
        output_file_prefix (str): The output file prefix (typically the time when the test were started)
        target_ip (str): The target device IP.
        run_count (int): The number of times to run the test.
        sleep_time (int): The time to wait between toggles in seconds.

    Returns:
        CommandError: SUCCESS if there were no error, the failed command error otherwise.
    """
    device_output_file = output_dir + output_file_prefix + '_toggle_test_'
    setup_device_logs(device_output_file, target_device_ip, target_device_serial_num)
    child = pexpect.spawn(f'telnet {target_ip} 4902')
    print('Enabling buttons')
    child.sendline("target button enable")
    sleep(1)
    for i in range(run_count):
        print(f'Toggle Test Run #{i + 1}')
        telnet_cmds = [
            "target button press 1",
            "target button release 1",
        ]

        
        for cmd in telnet_cmds:
            child.sendline(cmd)
            sleep(0.5)

        sleep(sleep_time)
    teardown_device_logs()
    child.close()
    return CommandError.SUCCESS

def single_fabric_commissioning_test(
        nodeID: str,
        endpointID: str,
        otbrhex: str,
        pin: str,
        discriminator: str,
        output_dir: str,
        output_file_prefix: str,
        target_device_ip: str,
        run_count: int,
        commission_device: bool,
        chip_tool_path: str ="~/connectedhomeip/out/standalone/chip-tool"
    ) -> Literal[0,1,2,3]:
    """
    Perform a single fabric commissioning test.
    Steps:
    1. Commission the device using BLE.
    2. Toggle the device on and off.
    3. Read the on-off state.
    4. Unpair the device.

    Args:
        endpointID (str): The endpoint ID.
        otbrhex (str): The OTBR hex string.
        pin (str): The PIN code.
        discriminator (str): The discriminator.
        output_dir (str): The output path of the chip-tool logs.
        target_device_ip (str): The target device IP.
        run_count (int): The number of times to run the test.
        chip_tool_path (str): The path to the chip-tool binary.

    Returns:
        CommandError: SUCCESS if there were no error, the failed command error otherwise.
    """
    result = CommandError.SUCCESS
    for i in range(run_count):
        test_prefix = output_file_prefix + f'_single_run_{i + 1}'
        output_file = output_dir + test_prefix
        chip_tool_output_file = output_file + chip_tool_suffix

        setup_device_logs(output_file, target_device_ip)
        # If this is the first run and the device is commissioned, we skip commissioning.
        if i != 0 or commission_device:
            result = commission_bleThread(nodeID, otbrhex, pin, discriminator, chip_tool_output_file, chip_tool_path)
            if result != CommandError.SUCCESS:
                teardown_device_logs()
                break

        send_cmd(f'{chip_tool_path} onoff toggle 1 {endpointID} --commissioner-name alpha', chip_tool_output_file)
        send_cmd(f'{chip_tool_path} onoff read on-off 1 {endpointID} --commissioner-name alpha', chip_tool_output_file)
        send_cmd(f'{chip_tool_path} pairing unpair 1 --commissioner-name alpha', chip_tool_output_file)
        teardown_device_logs()

    if result != CommandError.SUCCESS:
        print(f'Single Fabric Commissioning Test Error #{i + 1}: {CommandError.to_string(result)}')
        handle_error(result, output_file)
        
    return result


def multiple_fabric_commissioning_test(
        nodeID: str,
        endpointID: str,
        otbrhex: str,
        pin: str,
        discriminator: str,
        output_dir: str,
        output_file_prefix: str,
        target_device_ip: str,
        run_count: int,
        commission_device: bool,
        chip_tool_path: str = "~/connectedhomeip/out/standalone/chip-tool"
    ) -> Literal[0,1,2,3]:
    """
    Perform multiple fabric commissioning tests.
    Steps:
    1. Commission the device using BLE on fabric 1.
    2. For each fabric predefined on chip-tool:
        1. Open the commissioning window from fabric 1.
        2. Pair the device with the pairing code on the new fabric using a new nodeId (here the fabric index).
        3. Toggle the device on and off.
        4. Read the on-off state.
    3. For each commissioned fabric, starting by the last one:
        1. Unpair the device.
    Note: We currently run this test on 5 fabrics since this is the default defined on chip-tool.

    Args:
        endpointID (str): The endpoint ID.
        otbrhex (str): The OTBR hex string.
        pin (str): The PIN code.
        discriminator (str): The discriminator.
        output_dir (str): The output path of the chip-tool logs.
        target_device_ip (str): The target device IP.
        run_count (int): The number of times to run the test.
        chip_tool_path (str): The path to the chip-tool binary.

    Returns:
        CommandError: SUCCESS if there were no error, the failed command error otherwise.
    """
    result = CommandError.SUCCESS
    fabric_names = {1: 'alpha', 2: 'beta', 3: 'gamma', 4: 4, 5: 5}
    for i in range(run_count):
        test_prefix = output_file_prefix + f'_multiple_run_{i + 1}'
        output_file = output_dir + test_prefix
        chip_tool_output_file = output_file + chip_tool_suffix

        setup_device_logs(output_file, target_device_ip)
        # If this is the first run and the device is commissioned, we skip commissioning.
        if i != 0 or commission_device:
            result = commission_bleThread(nodeID, otbrhex, pin, discriminator, chip_tool_output_file, chip_tool_path)
            if result != CommandError.SUCCESS:
                teardown_device_logs()
                break

        # Commission additional fabrics
        for fabric_idx, fabric_name in fabric_names.items():
            if fabric_idx == 1:
                continue
            pairing_code = open_commissioning_window(chip_tool_output_file)
            if CommandError.OPEN_COMMISSIONING_WINDOW_ERROR == pairing_code:
                result = CommandError.OPEN_COMMISSIONING_WINDOW_ERROR
                break
            if CommandError.COMMISSION_PAIRING_CODE_ERROR == commission_pairing_code(pairing_code, fabric_idx, fabric_name, chip_tool_output_file):
                result = CommandError.COMMISSION_PAIRING_CODE_ERROR
                break

        if result != CommandError.SUCCESS:
            teardown_device_logs()
            break

        # Toggle and read on-off state for each fabric
        for fabric_idx, fabric_name in fabric_names.items():
            send_cmd(f'{chip_tool_path} onoff toggle {fabric_idx} {endpointID} --commissioner-name {fabric_name}', chip_tool_output_file)
            send_cmd(f'{chip_tool_path} onoff read on-off {fabric_idx} {endpointID} --commissioner-name {fabric_name}', chip_tool_output_file)

        # Unpair each fabric in reverse order
        for fabric_idx, fabric_name in reversed(fabric_names.items()):
            send_cmd(f'{chip_tool_path} pairing unpair {fabric_idx} --commissioner-name {fabric_name}', chip_tool_output_file)

        teardown_device_logs()

    if result != CommandError.SUCCESS:
        print(f'Multiple Fabric Commissioning Test Error #{i + 1}: {CommandError.to_string(result)}')
        handle_error(result, output_file)

    return result


def yaml_test_script_test(
    nodeID: str,
    otbrhex: str,
    pin: str,
    discriminator: str,
    chip_path: str,
    commission_device: bool,
    output_dir: str,
    output_file_prefix: str,
    test_list: List[str],
    test_list_run_count: int,
    test_plan_run_count: int,
    target_device_ip: str,
    target_device_serial_num: str,
    extra_env_path: str,
    chip_tool_path: str ="~/connectedhomeip/out/standalone/chip-tool"
) -> Literal[0,1,2,3,4,5]:
    """
    Run a set of YAML test scripts using chip-tool and handle errors.
    Steps:
    1. Commission the device using BLE.
    2. For each test in the test list, run the test using chiptool.py.
    3. Unpair the device after all tests.
    Args:
        nodeID, otbrhex, pin, discriminator, chip_path, chip_tool_path, output_dir, output_file_prefix, test_list, test_plan_run_count, target_device_ip, target_device_serial_num, extra_env_path
    Returns:
        CommandError: SUCCESS if all tests pass, otherwise the error code.
    """
    result = CommandError.SUCCESS

    if commission_device:
        output_file = output_dir + output_file_prefix + "_test_plan_run_commissioning"
        chip_tool_output_file = output_file + chip_tool_suffix
        result = commission_bleThread(nodeID, otbrhex, pin, discriminator, chip_tool_output_file, chip_tool_path)
        if result != CommandError.SUCCESS:
            print(f'Commissioning failed with error: {result}')
            handle_error(result, output_file)
            return result

    for i in range(test_list_run_count):
        test_prefix = output_file_prefix + f'_test_plan_run_{i + 1}_'
        output_file = output_dir + test_prefix

        for test in test_list:
            print(f'Running test: {test}')
            for j in range(test_plan_run_count):  # Run each yaml test plan 3 times
                device_output_file = output_file + test + f'_run_{j + 1}'
                chip_tool_output_file = output_file + test + f'_run_{j + 1}' +  chip_tool_suffix
                setup_device_logs(device_output_file, target_device_ip, target_device_serial_num)
                buff = send_cmd(
                    chip_cmd=f'python3 {chip_path}/scripts/tests/chipyaml/chiptool.py tests {test} --server_path {chip_tool_path} --nodeId 1',
                    output_file=chip_tool_output_file,
                    extra_env_path=extra_env_path,
                    cwd=chip_path
                )
                if not verify_device_logs(device_output_file):
                    handle_error(CommandError.DEVICE_UNRESPONSIVE, device_output_file)
                    result = CommandError.DEVICE_UNRESPONSIVE
                    break
                else:
                    for line in reversed(buff):
                        if "########## FAILURE ##########" in line:
                            handle_error(CommandError.TEST_FAILURE, device_output_file)
                            # If a failure is detected, we identify the failure logs but we don't stop the test run.
                teardown_device_logs()

            if result != CommandError.SUCCESS:
                break
        if result != CommandError.SUCCESS:
            break
        
    # Unpair after all tests if commissioning succeeded
    if result == CommandError.SUCCESS:
        send_cmd(f'{chip_tool_path} pairing unpair 1 --commissioner-name alpha', chip_tool_output_file)
    else:
        # TODO: Add error handling to recover the device if it is unresponsive
        print(f'YAML Test Script Test Error: {CommandError.to_string(result)}')

    return result


if __name__ == '__main__':
    output_dir: str = './test_logs/'

    # Ensure output directories exist
    os.makedirs(output_dir, exist_ok=True)

    parser = argparse.ArgumentParser()
    parser.add_argument('--chip_path', type=str, required=False, default=chip_path)
    parser.add_argument('--otbrhex', type=str, required=False)
    parser.add_argument('--discriminator', type=str, required=False)
    parser.add_argument('--pin', type=str, required=False)
    parser.add_argument('--nodeID', type=str, required=False)
    parser.add_argument('--endpointID', type=str, required=False)
    parser.add_argument('--target_device_ip', type=str, required=False)
    parser.add_argument('--target_device_serial_num', type=str, required=False)
    parser.add_argument('--test_list', type=str, required=False)
    parser.add_argument('--use_json_list', type=str2bool, required=False, default=False)
    parser.add_argument('--single_run_count', type=int, required=False)
    parser.add_argument('--multiple_run_count', type=int, required=False)
    parser.add_argument('--test_list_run_count', type=int, required=False)
    parser.add_argument('--test_plan_run_count', type=int, required=False)
    parser.add_argument('--toggle_test_run_count', type=int, required=False)
    parser.add_argument('--toggle_sleep_time', type=int, required=False)
    parser.add_argument('--factory_reset_device', type=str2bool, required=False, default=False)
    parser.add_argument('--commission_device', type=str2bool, required=False, default=False)
    parser.add_argument('--use_script_input_json', type=str2bool, required=False, default=False)
    args = parser.parse_args()

    # Load from script_input.json if requested
    if 'use_script_input_json' in vars(args) and args.use_script_input_json:
        with open('script_input.json', 'r') as f:
            json_args = json.load(f)
        # Override args with json_args
        for k, v in json_args.items():
            # Convert test_list to comma-separated string for compatibility
            if k == "test_list" and isinstance(v, list):
                setattr(args, k, ",".join(v))
            else:
                setattr(args, k, v)

    otbrhex: str = ""
    # output file prefix based on date
    output_file_prefix = str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

    if 'chip_path' in vars(args) and args.chip_path:
        chip_path = args.chip_path
    if 'otbrhex' in vars(args) and args.otbrhex:
        otbrhex = args.otbrhex
    if 'discriminator' in vars(args) and args.discriminator:
        discriminator = args.discriminator
    if 'pin' in vars(args) and args.pin:
        pin = args.pin
    if 'nodeID' in vars(args) and args.nodeID is not None:
        nodeID = args.nodeID
    if 'endpointID' in vars(args) and args.endpointID:
        endpointID = args.endpointID
    if 'target_device_ip' in vars(args) and args.target_device_ip:
        target_device_ip = args.target_device_ip
    if 'target_device_serial_num' in vars(args) and args.target_device_serial_num:
        target_device_serial_num = args.target_device_serial_num
    if 'commission_device' in vars(args):
        commission_device = args.commission_device
    if 'single_run_count' in vars(args) and args.single_run_count is not None:
        single_run_count = args.single_run_count
    if 'multiple_run_count' in vars(args) and args.multiple_run_count is not None:
        multiple_run_count = args.multiple_run_count
    if 'test_list_run_count' in vars(args) and args.test_list_run_count is not None:
        test_list_run_count = args.test_list_run_count
    if 'test_plan_run_count' in vars(args) and args.test_plan_run_count is not None:
        test_plan_run_count = args.test_plan_run_count
    if 'toggle_test_run_count' in vars(args) and args.toggle_test_run_count is not None:
        toggle_test_run_count = args.toggle_test_run_count
    if 'toggle_sleep_time' in vars(args) and args.toggle_test_run_count is not None:
        toggle_sleep_time = args.toggle_test_run_count
    if 'factory_reset_device' in vars(args) and args.factory_reset_device:
        factory_reset_device() 

    test_list = []
    if 'use_json_list' in vars(args) and args.use_json_list:
        with open("yaml_test_list.json", "r") as f:
            jsonData = json.load(f)
            test_list = jsonData.get("YamlTestCasesToRun", [])
    elif 'test_list' in vars(args) and args.test_list:
        if isinstance(args.test_list, str):
            test_list = [t.strip() for t in args.test_list.split(',') if t.strip()]

    otbrhex = setup_test(otbrhex, target_device_ip)
    chip_tool_path = chip_path + '/out/standalone/chip-tool'

    result = single_fabric_commissioning_test(
        nodeID, 
        endpointID, 
        otbrhex, 
        pin, 
        discriminator, 
        output_dir, 
        output_file_prefix,
        target_device_ip, 
        single_run_count,
        commission_device
    )
    if result != CommandError.SUCCESS:
        exit(-1)

    result = multiple_fabric_commissioning_test(
        nodeID, 
        endpointID, 
        otbrhex, 
        pin, 
        discriminator, 
        output_dir, 
        output_file_prefix,
        target_device_ip, 
        multiple_run_count,
        commission_device
    )
    if result != CommandError.SUCCESS:
        exit(-1)

    if test_plan_run_count >= 1:
        result = yaml_test_script_test(
            nodeID=nodeID,
            otbrhex=otbrhex,
            pin=pin,
            discriminator=discriminator,
            chip_path=chip_path,
            commission_device=commission_device,
            chip_tool_path=chip_tool_path,
            output_dir=output_dir,
            output_file_prefix=output_file_prefix,
            test_list=test_list,
            test_list_run_count=test_list_run_count,
            test_plan_run_count=test_plan_run_count,
            target_device_ip=target_device_ip,
            target_device_serial_num=target_device_serial_num if 'target_device_serial_num' in locals() else "",
            extra_env_path=extra_env_path
        )
        if result != CommandError.SUCCESS:
            exit(-1)

    if toggle_test_run_count >= 1:
        result = toggle_test(
            output_dir=output_dir,
            output_file_prefix=output_file_prefix,
            target_ip=target_device_ip,
            target_device_serial_num=target_device_serial_num if 'target_device_serial_num' in locals() else "",
            run_count=toggle_test_run_count,
            sleep_time=1
        )
        if result != CommandError.SUCCESS:
            exit(-1)

    teardown_test()

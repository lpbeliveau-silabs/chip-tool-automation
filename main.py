from utils import send_cmd, open_commissioning_window, commission_pairing_code, commission_bleThread, CommandError
from utils.jlink_logger import start_reading_device_output, stop_reading_device_output
import argparse
import subprocess
import pexpect
import datetime
from time import sleep

discriminator: str = '3840'
pin: str = '20202021'
endpointID: str = '1'
target_device_ip: str = '10.4.215.46'
single_run_count = 1
multiple_run_count = 1
output_dir = './chip_tool_output'
device_uart_suffix = '_device-uart-logs.txt'
device_rtt_suffix = '_device-rtt-logs.txt'
chip_tool_suffix = '_chip-tool-logs.txt'
device_uart_error_suffix = '_device-uart-error-logs.txt'
device_rtt_error_suffix = '_device-rtt-error-logs.txt'
chip_tool_error_suffix = '_chip-tool-error-logs.txt'


def setup_device_logs(output_file: str, target_ip: str):
    """
    Setup the device logs.
    Steps:
    1. Start a tmux session.
    2. Start a screen session in the tmux session.
    Args:
        output_file_prefix (str): The output file prefix.
    """
    send_cmd(f'tmux new-session -d -s chip_tool_test_session')
    # Screen session to temporary store out logs in uart output_file
    send_cmd(
        f'tmux send-keys -t chip_tool_test_session "screen -L -Logfile {output_file}{device_uart_suffix} //telnet {target_ip} 4901" C-m')
    # Start RTT logging
    start_reading_device_output(serial_num="440298742", log_file_path=f'{output_file}{device_rtt_suffix}')


def teardown_device_logs():
    """
    Teardown the device logs.
    Steps:
    1. Kill the tmux session.
    """
    send_cmd('tmux kill-session -t chip_tool_test_session')
    stop_reading_device_output()


def setup_test(otbrhex_input: str, target_ip: str) -> str:
    """
    Setup the test environment on the raspberry pi.
    Steps:
    1. Remove any previous chip_tool files.
    2. Create an output directory for the logs.
    3. Fetch the otbrhex dataset using ot-ctl (if not provided).
    4. Start tmux session.
    5. Starts screen session in tmux using screen -L -Logfile device-logs.txt //telnet 10.4.215.46 4901.
    6. Open a telnet session, wake up the device and close the telnet session.

    Args:
        otbrhex_input (str): The OTBR hex string, default is None.
        target_ip (str): The target device IP.
    """
    send_cmd('rm -rf /tmp/chip_*')
    send_cmd(f'mkdir -p {output_dir}')
    cmd: str = 'sudo ot-ctl dataset active -x'

    if otbrhex_input == None:
        print(f'===== cmd: {cmd}')
        result = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Recover the 1st line of the output ot-ctl dataset active -x, second line being "Done" if successful
        otbrhex_output = result.communicate()[0].decode().splitlines(keepends=False)
        if otbrhex_output[1] != 'Done':
            print(f'Failed to fetch otbrhex dataset')
            return

        otbrhex_output = otbrhex_output[0]
        print(f'otbrhex_output: {otbrhex_output}')

    # Ensure the device is advertising by toggling the button 0
    telnet_cmds = [
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
    1. Kill the tmux session.
    2. Remove the chip_tool files.
    """
    teardown_device_logs()
    send_cmd('rm -rf /tmp/chip_*')


def handle_error(error_code: CommandError, output_file: str):
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
    send_cmd('mv {output_file}{device_uart_suffix} {output_file}{device_uart_error_suffix}')
    send_cmd('mv {output_file}{device_rtt_suffix} {output_file}{device_rtt_error_suffix}')
    send_cmd('mv {output_file}{chip_tool_suffix} {output_file}{chip_tool_error_suffix}')
    teardown_test()


def single_fabric_commissioning_test(endpointID: str, otbrhex: str, pin: str, discriminator: str, output_file: str) -> CommandError:
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

    Returns:
        CommandError: SUCCESS if there were no error, the failed command error otherwise.
    """
    chip_tool_output_file = output_file + chip_tool_suffix
    result = commission_bleThread(endpointID, otbrhex, pin, discriminator, chip_tool_output_file)
    if result != CommandError.SUCCESS:
        return result

    send_cmd(f'~/chip-tool onoff toggle 1 {endpointID} --commissioner-name alpha', chip_tool_output_file)
    send_cmd(f'~/chip-tool onoff read on-off 1 {endpointID} --commissioner-name alpha', chip_tool_output_file)
    send_cmd(f'~/chip-tool pairing unpair 1 --commissioner-name alpha', chip_tool_output_file)
    return CommandError.SUCCESS


def multiple_fabric_commissioning_test(endpointID: str, otbrhex: str, pin: str, discriminator: str, output_file: str) -> CommandError:
    """
    Perform a multiple fabric commissioning test.
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

    Returns:
        CommandError: SUCCESS if there were no error, the failed command error otherwise.
    """
    chip_tool_output_file = output_file + chip_tool_suffix
    result = commission_bleThread(endpointID, otbrhex, pin, discriminator, chip_tool_output_file)
    if result != CommandError.SUCCESS:
        return result

    # fabric names predefined in chip-tool
    fabric_names = {1: 'alpha', 2: 'beta', 3: 'gamma', 4: 4, 5: 5}
    for fabric_idx, fabric_name in fabric_names.items():
        if fabric_idx == 1:
            continue
        pairing_code = open_commissioning_window(chip_tool_output_file)
        if CommandError.OPEN_COMMISSIONING_WINDOW_ERROR == pairing_code:
            return CommandError.OPEN_COMMISSIONING_WINDOW_ERROR
        if CommandError.COMMISSION_PAIRING_CODE_ERROR == commission_pairing_code(pairing_code, fabric_idx, fabric_name, chip_tool_output_file):
            return CommandError.COMMISSION_PAIRING_CODE_ERROR

    for fabric_idx, fabric_name in fabric_names.items():
        send_cmd(f'~/chip-tool onoff toggle {fabric_idx} {endpointID} --commissioner-name {fabric_name}', chip_tool_output_file)
        send_cmd(
            f'~/chip-tool onoff read on-off {fabric_idx} {endpointID} --commissioner-name {fabric_name}', chip_tool_output_file)

    # goes through the fabric names in reversed order
    for fabric_idx, fabric_name in reversed(fabric_names.items()):
        send_cmd(f'~/chip-tool pairing unpair {fabric_idx} --commissioner-name {fabric_name}', chip_tool_output_file)
    return CommandError.SUCCESS


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--otbrhex', type=str, required=False)
    parser.add_argument('--discriminator', type=str, required=False)
    parser.add_argument('--pin', type=str, required=False)
    parser.add_argument('--endpointID', type=str, required=False)
    parser.add_argument('--target_device_ip', type=str, required=False)
    parser.add_argument('--single_run_count', type=int, required=False)
    parser.add_argument('--multiple_run_count', type=int, required=False)
    args = parser.parse_args()

    otbrhex: str = None

    # output file prefix based on date
    output_file_prefix = str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

    if 'otbrhex' in vars(args) and args.otbrhex:
        otbrhex = args.otbrhex
    if 'discriminator' in vars(args) and args.discriminator:
        discriminator = args.discriminator
    if 'pin' in vars(args) and args.pin:
        pin = args.pin
    if 'endpointID' in vars(args) and args.endpointID:
        endpointID = args.endpointID
    if 'target_device_ip' in vars(args) and args.target_device_ip:
        target_device_ip = args.target_device_ip
    if 'single_run_count' in vars(args) and args.single_run_count is not None:
        single_run_count = args.single_run_count
    if 'multiple_run_count' in vars(args) and args.multiple_run_count is not None:
        multiple_run_count = args.multiple_run_count

    otbrhex = setup_test(otbrhex, target_device_ip)

    for i in range(single_run_count):
        test_prefix = output_dir + '/' + output_file_prefix + f'_single_run_{i + 1}'
        device_output_file = test_prefix

        setup_device_logs(device_output_file, target_device_ip)
        result = single_fabric_commissioning_test(endpointID, otbrhex, pin, discriminator, test_prefix)
        teardown_device_logs()
        if result != CommandError.SUCCESS:
            print(f'Single Fabric Commissioning Test Error #{i + 1}: {CommandError.to_string(result)}')
            handle_error(result, test_prefix)
            exit(-1)

    for i in range(multiple_run_count):
        test_prefix = output_file_prefix + '/' + f'_multiple_run_{i + 1}'
        device_output_file = test_prefix

        setup_device_logs(device_output_file, target_device_ip)
        result = multiple_fabric_commissioning_test(endpointID, otbrhex, pin, discriminator, test_prefix)
        teardown_device_logs()

        if result != CommandError.SUCCESS:
            print(f'Multiple Fabric Commissioning Test Error #{i + 1}: {CommandError.to_string(result)}')
            handle_error(result, test_prefix)
            exit(-1)

    teardown_test()

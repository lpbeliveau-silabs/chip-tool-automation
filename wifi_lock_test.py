from utils import send_cmd, open_commissioning_window, commission_pairing_code, CommandError
import argparse
import subprocess
import pexpect
import datetime
import sys
import os
import json
from time import sleep
from typing import Literal, List

from utils.commands import commission_bleWifi

discriminator: str = '3840'
pin: str = '20202021'
endpointID: str = '1'
target_device_ip: str = '10.4.215.46'
single_run_count: int = 0
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

def setup_test(ssid: str, pw: str, target_ip: str) -> tuple[str, str]:
    """
    Setup the test environment on the raspberry pi.
    Steps:
    1. Fetch ssid and pw of the network from wpa_supplicant config file.
    2. Open a telnet session, wake up the device and close the telnet session.

    Args:
        ssid (str): The SSID of the network.
        pw (str): The password of the network.
        target_ip (str): The target device IP.
    """
    
    if ssid == '':
        # Get the first SSID from wpa_supplicant config file
        ssid_cmd = "grep 'ssid=' /etc/wpa_supplicant/wpa_supplicant.conf | head -1 | cut -d= -f2 | tr -d '\"'"
        try:
            print(f'===== Getting first SSID from config: {ssid_cmd}')
            result = subprocess.Popen(ssid_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            ssid_output = result.communicate()[0].decode().strip()
            if ssid_output:
                print(f'Found SSID: {ssid_output}')
            else:
                print(f'No SSID found in wpa_supplicant config file')
                return 'Error', 'Error'
        except Exception as e:
            print(f'SSID retrieval failed: {e}')
            return 'Error', 'Error'
    else:
        ssid_output = ssid
        print(f'Using provided SSID: {ssid_output}')

    # Get password for the specific SSID
    if pw == '':
        # Get password for the specific SSID from wpa_supplicant config file
        pw_cmd = f"grep -A 5 'ssid=\"{ssid_output}\"' /etc/wpa_supplicant/wpa_supplicant.conf | grep 'psk=' | cut -d= -f2 | tr -d '\"'"
        try:
            print(f'===== Getting password for SSID: {ssid_output}')
            result = subprocess.Popen(pw_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            pw_output = result.communicate()[0].decode().strip()
            if pw_output:
                print(f'Found password for SSID: {ssid_output}')
                # Don't print the actual password for security
            else:
                print(f'No password found in config file for SSID: {ssid_output}')
                pw_output = 'Error'
        except Exception as e:
            print(f'Password retrieval failed: {e}')
            pw_output = 'Error'
    else:
        pw_output = pw
        print(f'Using provided password')

    # Ensure the device is advertising by toggling the button 0
    telnet_cmds = [
        "target button enable",
        "target button press 0",
        "target button release 0",
        "quit"
    ]

    child = pexpect.spawn(f'telnet {target_ip} 4902')
    for cmd in telnet_cmds:
        child.sendline(cmd)
        sleep(0.5)

    child.close()

    return ssid_output, pw_output


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

def single_fabric_commissioning_test(
        nodeID: str,
        endpointID: str,
        ssid: str,
        pw: str,
        pin: str,
        discriminator: str,
        output_dir: str,
        output_file_prefix: str,
        target_device_ip: str,
        run_count: int,
        commission_device: bool,
        toggle_count: int = 1,
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
        ssid (str): The Wi-Fi SSID.
        pw (str): The Wi-Fi password.
        pin (str): The PIN code.
        discriminator (str): The discriminator.
        output_dir (str): The output path of the chip-tool logs.
        output_file_prefix (str): The output file prefix.
        target_device_ip (str): The target device IP.
        run_count (int): The number of times to run the test.
        commission_device (bool): Whether to commission the device or not.
        toggle_count (int): The number of times to toggle the device on and off.
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
            result = commission_bleWifi(nodeID, ssid, pin, pw, discriminator, chip_tool_output_file, chip_tool_path)
            if result != CommandError.SUCCESS:
                teardown_device_logs()
                break
        
        for j in range(1, toggle_count):
            send_cmd(f'{chip_tool_path} doorlock unlock-door 1 {endpointID} --commissioner-name alpha', chip_tool_output_file)
            send_cmd(f'{chip_tool_path} doorlock read lock-state 1 {endpointID} --commissioner-name alpha', chip_tool_output_file)
            sleep(1)
            send_cmd(f'{chip_tool_path} doorlock lock-door 1 {endpointID} --commissioner-name alpha', chip_tool_output_file)
            send_cmd(f'{chip_tool_path} doorlock read lock-state 1 {endpointID} --commissioner-name alpha', chip_tool_output_file)

        send_cmd(f'{chip_tool_path} pairing unpair 1 --commissioner-name alpha', chip_tool_output_file)
        teardown_device_logs()

    if result != CommandError.SUCCESS:
        print(f'Single Fabric Commissioning Test Error #{i + 1}: {CommandError.to_string(result)}')
        handle_error(result, output_file)
        
    return result

if __name__ == '__main__':
    output_dir: str = './test_logs/'

    # Ensure output directories exist
    os.makedirs(output_dir, exist_ok=True)

    parser = argparse.ArgumentParser()
    parser.add_argument('--chip_path', type=str, required=False, default=chip_path)
    parser.add_argument('--discriminator', type=str, required=False)
    parser.add_argument('--pin', type=str, required=False)
    parser.add_argument('--nodeID', type=str, required=False)
    parser.add_argument('--endpointID', type=str, required=False)
    parser.add_argument('--target_device_ip', type=str, required=False)
    parser.add_argument('--target_device_serial_num', type=str, required=False)
    parser.add_argument('--single_run_count', type=int, required=False)
    parser.add_argument('--factory_reset_device', type=str2bool, required=False, default=False)
    parser.add_argument('--commission_device', type=str2bool, required=False, default=False)
    args = parser.parse_args()

    otbrhex: str = ""
    # output file prefix based on date
    output_file_prefix = str(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

    if 'chip_path' in vars(args) and args.chip_path:
        chip_path = args.chip_path
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
    if 'factory_reset_device' in vars(args) and args.factory_reset_device:
        factory_reset_device() 

    ssid,pw = setup_test('', '', target_device_ip)
    chip_tool_path = chip_path + '/out/standalone/chip-tool'

    if single_run_count > 0:
        result = single_fabric_commissioning_test(
            nodeID, 
            endpointID, 
            ssid,
            pw, 
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

    teardown_test()

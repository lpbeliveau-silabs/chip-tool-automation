from utils import send_cmd, open_commissioning_window, commission_pairing_code, commission_bleThread, CommandError
from utils.jlink_logger import start_reading_device_output, stop_reading_device_output
import argparse
import json
import datetime
from time import sleep
import sys
import os

env = os.environ.copy()

chip_path = os.path.expanduser('~/connectedhomeip')
matter_yamltests_path = os.path.join(chip_path, 'scripts', 'py_matter_yamltests')
matter_idl_path = os.path.join(chip_path, 'scripts', 'py_matter_idl')

existing_pythonpath = os.environ.get("PYTHONPATH", "")
extra_env_path = f"{matter_yamltests_path}:{matter_idl_path}"
if existing_pythonpath:
    extra_env_path = f"{existing_pythonpath}:{extra_env_path}"


def str2bool(value):
    if isinstance(value, bool):
        return value
    if value.lower() in ("yes", "true", "t", "1"):
        return True
    elif value.lower() in ("no", "false", "f", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")

def setup_device_logs(output_file: str, target_ip: str, serial_num: str = "440298742"):
    """
    Setup the device logs.
    Steps:
    1. Start a tmux session.
    2. Start a screen session in the tmux session.
    3. Start reading device output using RTT.
    Args:
        output_file_prefix (str): The output file prefix.
    """
    device_uart_suffix = '_device-uart-logs.txt'
    device_rtt_suffix = '_device-rtt-logs.txt'
    send_cmd(f'tmux new-session -d -s chip_tool_test_session')
    # Screen session to temporary store out logs in uart output_file
    send_cmd(
        f'tmux send-keys -t chip_tool_test_session "screen -L -Logfile {output_file}{device_uart_suffix} //telnet {target_ip} 4901" C-m')
    # Start RTT logging
    # start_reading_device_output(serial_num=serial_num, log_file_path=f'{output_file}{device_rtt_suffix}')

def teardown_device_logs():
    """
    Teardown the device logs.
    Steps:
    1. Kill the tmux session.
    """
    send_cmd('tmux kill-session -t chip_tool_test_session')
    stop_reading_device_output()

if __name__ == '__main__':
    chip_tool_output_dir = './chip_tool_output/'
    device_output_dir = './device_output/'
    # Ensure output directories exist
    os.makedirs(chip_tool_output_dir, exist_ok=True)
    os.makedirs(device_output_dir, exist_ok=True)

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
    parser.add_argument('--commission_device', type=str2bool, required=False, default=False)
    args = parser.parse_args()

    otbrhex: str = None
    run_commissioning: bool = False

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
    if 'commission_device' in vars(args) and args.commission_device:
        run_commissioning = args.commission_device

    test_list = []
    if 'use_json_list' in vars(args) and args.use_json_list:
        with open("yaml_test_list.json", "r") as f:
            jsonData = json.load(f)
            test_list = jsonData.get("YamlTestCasesToRun", [])
    elif 'test_list' in vars(args) and args.test_list:
        if isinstance(args.test_list, str):
            test_list = [t.strip() for t in args.test_list.split(',') if t.strip()]

    chip_tool_path = chip_path + '/out/standalone/chip-tool'
    chip_tool_output_file = chip_tool_output_dir + 'Commissioning' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '.log'

    if run_commissioning:
        result = commission_bleThread(nodeID, otbrhex, pin, discriminator, chip_tool_output_file, chip_tool_path)
        if result != CommandError.SUCCESS:
            print(f'Commissioning failed with error: {result}')
            sys.exit(1)

    for test in test_list:
        print(f'Running test: {test}')
        chip_tool_output_file = chip_tool_output_dir + test + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '.log'
        device_output_file = device_output_dir + test + '_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '.log'
        setup_device_logs(device_output_file, target_device_ip, target_device_serial_num)
        send_cmd(
            chip_cmd= f'python3 {chip_path}/scripts/tests/chipyaml/chiptool.py tests {test} --server_path {chip_tool_path} --nodeId 1', 
            output_file= chip_tool_output_file, 
            extra_env_path= extra_env_path,
            cwd=chip_path
        )
        teardown_device_logs()
    
    if run_commissioning:
        send_cmd(f'~/chip-tool pairing unpair 1 --commissioner-name alpha', chip_tool_output_file)
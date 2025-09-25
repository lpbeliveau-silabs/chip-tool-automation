import subprocess
import re
import os
from typing import Literal, Optional

class CommandError:
    SUCCESS = 0x00
    BLE_COMMISSIONING_FAILURE = 0x01
    OPEN_COMMISSIONING_WINDOW_ERROR = 0x02
    COMMISSION_PAIRING_CODE_ERROR = 0x03
    TEST_FAILURE = 0x04
    DEVICE_UNRESPONSIVE = 0x05

    @staticmethod
    def to_string(error_code: int) -> str:
        if error_code == CommandError.SUCCESS:
            return "Success"
        elif error_code == CommandError.BLE_COMMISSIONING_FAILURE:
            return "BLE Commissioning Failure"
        elif error_code == CommandError.OPEN_COMMISSIONING_WINDOW_ERROR:
            return "Open Commissioning Window Error"
        elif error_code == CommandError.COMMISSION_PAIRING_CODE_ERROR:
            return "Commission Pairing Code Error"
        elif error_code == CommandError.TEST_FAILURE:
            return "Test Failure"
        elif error_code == CommandError.DEVICE_UNRESPONSIVE:
            return "Device Unresponsive"
        else:
            return "Unknown Error"


def send_cmd(chip_cmd, output_file: Optional[str] = None,  extra_env_path: Optional[str] = None, cwd: Optional[str] = None):
    env = os.environ.copy()

    if extra_env_path:
        env["PYTHONPATH"] = extra_env_path

    print(f'===== cmd: {chip_cmd}')
    process = subprocess.Popen(
        chip_cmd,
        env=env,
        cwd=cwd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()
    buff = stdout.decode().splitlines(keepends=True)
    stderr_buff = stderr.decode().splitlines(keepends=True)
    
    # Combine stdout and stderr for complete output
    combined_output = buff + ["\n=== STDERR ===\n"] + stderr_buff if stderr_buff else buff

    if output_file:
        with open(output_file, 'w') as f:
            f.write(''.join(combined_output))
    else:
        print(''.join(combined_output))

    # Print stderr to console regardless of output_file setting
    if stderr_buff:
        print("STDERR OUTPUT:")
        print(''.join(stderr_buff))

    for line in reversed(combined_output):
        tiemout_pattern = re.compile('Run command failure(.*)CHIP Error 0x00000032(.*)Timeout')
        matcher = tiemout_pattern.search(line)
        if matcher:
            print("########## TIMEOUT ##########")
            process = subprocess.Popen('sudo tail -n 50 /var/log/syslog', shell=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            buff = stdout.decode().splitlines(keepends=True)
            if output_file:
                with open(output_file, 'a') as f:
                    f.write("########## OTBR LOGS ##########\r\n")
                    f.write(''.join(buff))
            else:
                print(''.join(buff))

        failure_pattern = re.compile(r'\*{5} Test Failure :')
        matcher = failure_pattern.search(line)
        if matcher:
            print("########## FAILURE ##########")
            process = subprocess.Popen('sudo tail -n 50 /v ar/log/syslog', shell=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            buff = stdout.decode().splitlines(keepends=True)
            if output_file:
                with open(output_file, 'a') as f:
                    f.write("########## OTBR LOGS ##########\r\n")
                    f.write(''.join(buff))
            else:
                print(''.join(buff))
    return combined_output


def commission_bleThread(nodeID, otbrhex, pin, discriminator, output_file: str, chipt_tool_path:str = '~/chip-tool') -> Literal[0,1]:
    buff = send_cmd(f'{chipt_tool_path} pairing ble-thread {nodeID} hex:{otbrhex} {pin} {discriminator}', output_file)
    for line in reversed(buff):
        if "Device commissioning completed with success" in line:
            return CommandError.SUCCESS
    return CommandError.BLE_COMMISSIONING_FAILURE

def commission_bleWifi(nodeID, ssid, password, pin, discriminator, output_file: str, chipt_tool_path:str = '~/chip-tool') -> Literal[0,1]:
    '''$ ./chip-tool pairing ble-wifi <node_id> <ssid> <password> <pin_code> <discriminator>
    '''
    buff = send_cmd(f'{chipt_tool_path} pairing ble-wifi {nodeID} {ssid} {password} {pin} {discriminator}', output_file)
    for line in reversed(buff):
        if "Device commissioning completed with success" in line:
            return CommandError.SUCCESS
    return CommandError.BLE_COMMISSIONING_FAILURE


def open_commissioning_window(output_file: str, chipt_tool_path:str = '~/chip-tool'):
    buff = send_cmd(f'{chipt_tool_path} pairing open-commissioning-window 1 1 400 2000 3841', output_file)
    for line in reversed(buff):
        if 'Manual pairing code' in line:
            pattern = re.compile(r'Manual pairing code: \[(.*)]')
            matcher = pattern.search(line)
            if matcher:
                return matcher[1]
    return CommandError.OPEN_COMMISSIONING_WINDOW_ERROR


def commission_pairing_code(code, fabric_idx, fabric_name, output_file: str, chipt_tool_path:str = '~/chip-tool')-> Literal[0,3]:
    buff = send_cmd(f'{chipt_tool_path} pairing code {fabric_idx} {code} --commissioner-name {fabric_name}', output_file)
    for line in reversed(buff):
        if "Device commissioning completed with success" in line:
            return CommandError.SUCCESS
    return CommandError.COMMISSION_PAIRING_CODE_ERROR

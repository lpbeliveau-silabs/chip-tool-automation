import subprocess
import re


class CommandError:
    SUCCESS = 0x00
    BLE_COMMISSIONING_FAILURE = 0x01
    OPEN_COMMISSIONING_WINDOW_ERROR = 0x02
    COMMISSION_PAIRING_CODE_ERROR = 0x03

    @staticmethod
    def to_string(error_code):
        if error_code == CommandError.SUCCESS:
            return "Success"
        elif error_code == CommandError.BLE_COMMISSIONING_FAILURE:
            return "BLE Commissioning Failure"
        elif error_code == CommandError.OPEN_COMMISSIONING_WINDOW_ERROR:
            return "Open Commissioning Window Error"
        elif error_code == CommandError.COMMISSION_PAIRING_CODE_ERROR:
            return "Commission Pairing Code Error"
        else:
            return "Unknown Error"


def send_cmd(chip_cmd, output_file: str = None):
    print(f'===== cmd: {chip_cmd}')
    process = subprocess.Popen(chip_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    buff = stdout.decode().splitlines(keepends=True)

    if output_file:
        with open(output_file, 'w') as f:
            f.write(''.join(buff))
    else:
        print(''.join(buff))

    for line in reversed(buff):
        pattern = re.compile('Run command failure(.*)CHIP Error 0x00000032(.*)Timeout')
        matcher = pattern.search(line)
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
    return buff


def commission_bleThread(endpointID, otbrhex, pin, discriminator, output_file: str = None):
    buff = send_cmd(f'~/chip-tool pairing ble-thread {endpointID} hex:{otbrhex} {pin} {discriminator}', output_file)
    for line in reversed(buff):
        if "Device commissioning completed with success" in line:
            return CommandError.SUCCESS
    return CommandError.BLE_COMMISSIONING_FAILURE


def open_commissioning_window(output_file: str = None):
    buff = send_cmd('~/chip-tool pairing open-commissioning-window 1 1 400 2000 3841', output_file)
    for line in reversed(buff):
        if 'Manual pairing code' in line:
            pattern = re.compile('Manual pairing code: \[(.*)]')
            matcher = pattern.search(line)
            if matcher:
                return matcher[1]
    return CommandError.OPEN_COMMISSIONING_WINDOW_ERROR


def commission_pairing_code(code, fabric_idx, fabric_name, output_file: str = None):
    buff = send_cmd(f'~/chip-tool pairing code {fabric_idx} {code} --commissioner-name {fabric_name}', output_file)
    for line in reversed(buff):
        if "Device commissioning completed with success" in line:
            return CommandError.SUCCESS
    return CommandError.COMMISSION_PAIRING_CODE_ERROR

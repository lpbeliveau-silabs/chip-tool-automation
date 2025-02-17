import subprocess
import re

def send_cmd(chip_cmd):
    print(f'===== cmd: {chip_cmd}')
    process = subprocess.Popen(chip_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    buff = stdout.decode().splitlines(keepends=True)
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
            print(''.join(buff))
    return buff


def open_commissioning_window():
    buff = send_cmd('./chip-tool pairing open-commissioning-window 1 1 400 2000 3841')
    for line in reversed(buff):
        if 'Manual pairing code' in line:
            pattern = re.compile('Manual pairing code: \[(.*)]')
            matcher = pattern.search(line)
            if matcher:
                return matcher[1]
            else:
                return 0


def commission_pairing_code(code, fabric_idx, fabric_name):
    buff = send_cmd(f'./chip-tool pairing code {fabric_idx} {code} --commissioner-name {fabric_name}')
    for line in reversed(buff):
        if "Device commissioning completed with success" in line:
            return True
    else:
        return False
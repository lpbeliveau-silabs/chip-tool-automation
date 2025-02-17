from utils import send_cmd, open_commissioning_window, commission_pairing_code

otbrhex = '0e08000000000001000000030000154a0300000c35060004001fffe0020836f26e038696ff5d0708fdb3d465ff59e0860510dfe8b148f078dd4003b4b332687a0a3b030f4f70656e5468726561642d36376261010267ba041015791942db7b3b4cc82db2336d0eb0190c0402a0f7f8'
discriminator = '3840'

send_cmd('rm -rf /tmp/chip_*')

buff = send_cmd(f'~/chip-tool pairing ble-thread 1 hex:{otbrhex} 20202021 {discriminator}')
for line in reversed(buff):
    if "Device commissioning completed with success" in line:
        break
else:
    exit(-1)

fabric_names = {1: 'alpha', 2: 'beta', 3: 'gamma', 4: 4, 5: 5}
for fabric_idx, fabric_name in fabric_names.items():
    if fabric_idx == 1:
        continue
    pairing_code = open_commissioning_window()
    if pairing_code == 0:
        exit(-2)
    if not commission_pairing_code(pairing_code, fabric_idx, fabric_name):
        exit(-3)

for idx in range(5):
    for fabric_idx, fabric_name in fabric_names.items():
        send_cmd(f'./chip-tool onoff toggle {fabric_idx} 1 --commissioner-name {fabric_name}')
        send_cmd(f'./chip-tool onoff read on-off {fabric_idx} 1 --commissioner-name {fabric_name}')

pass

import logging
import sys
import pylink
import threading

# Configuration
LOG_TO_FILE = True
LOG_FILE_PATH = './chip_tool_output/jlink_device_output.log'


def setup_logging(log_to_file: bool = True, log_file_path: str = LOG_FILE_PATH):
    if log_to_file:
        logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(message)s')
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(message)s')


read_thread = None
stop_event = threading.Event()


def read_device_output_thread(jlink):
    while not stop_event.is_set():
        output = jlink.rtt_read(0, 1024)
        if output:
            logging.info(bytes(output).decode('utf-8'))


def start_reading_device_output(device: str = "EFR32MG24BXXXF1536", serial_num: str = None, log_to_file: bool = True, log_file_path: str = LOG_FILE_PATH):
    global read_thread, stop_event
    setup_logging(log_to_file, log_file_path)
    jlink = pylink.JLink()
    jlink.open(serial_no=serial_num)
    jlink.set_tif(interface=pylink.JLinkInterfaces.SWD)
    jlink.connect(chip_name=device, speed="auto", verbose=True)
    jlink.rtt_start()

    stop_event.clear()
    read_thread = threading.Thread(target=read_device_output_thread, args=(jlink,))
    read_thread.start()


def stop_reading_device_output():
    global read_thread, stop_event
    stop_event.set()
    if read_thread is not None:
        read_thread.join()
        read_thread = None


if __name__ == "__main__":
    setup_logging()
    start_reading_device_output()
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Terminating connection...")
        stop_reading_device_output()

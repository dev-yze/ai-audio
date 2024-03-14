import subprocess
import threading
from config import logger

def start_frp():
    def run_process():
        command = ['./frp/frpc', '-c', './frp/frpc.toml']
        frp_result = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True)

        for line in iter(frp_result.stderr.readline, ""):
            logger.info(line)

        frp_result.wait()
    thread = threading.Thread(target=run_process)
    thread.start()
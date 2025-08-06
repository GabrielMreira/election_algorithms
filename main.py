import threading
import time
import sys
from process import Process

class Simulator:
    def __init__(self):
        self.processos = {}
        self.threads = {}
        self.peers = {}
        self.base_port = 5000

    def start_process(self, pid, algorithm):
        port = self.base_port + pid
        self.peers[pid] = port

        p = Process(pid=pid, port=port, peers=self.peers, algorithm=algorithm)
        self.processos[pid] = p
        print(f"Process {pid} started on port {port}.")
        return p

    def setup(self):
        try:
            n_processes = int(input("To type process number (ex: 5): "))
            algorithm = ''
            while algorithm not in ['bully', 'anel']:
                algorithm = input("Chose election algorithm ('bully' or 'anel'): ").lower()
        except ValueError:
            print("Invalid data, using comum values")
            n_processes = 5
            algorithm = 'bully'

        for i in range(1, n_processes + 1):
            self._start_process(pid=i, algorithm=algorithm)

        time.sleep(2)
        initial_coordinator_pid = max(self.processos.keys())
        print(f"\nInitial coordinator: {initial_coordinator_pid}\n")
        for p in self.processos.values():
            p._set_new_coordinator(initial_coordinator_pid)
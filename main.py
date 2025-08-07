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

    def _start_process(self, pid, algorithm):
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
            while algorithm not in ['bully', 'ring']:
                algorithm = input("Chose election algorithm ('bully' or 'ring'): ").lower()
        except ValueError:
            print("Invalid data, using commum values")
            n_processes = 5
            algorithm = 'bully'

        for i in range(1, n_processes + 1):
            self._start_process(pid=i, algorithm=algorithm)

        time.sleep(2)
        initial_coordinator_pid = max(self.processos.keys())
        print(f"\nInitial coordinator: {initial_coordinator_pid}\n")
        for p in self.processos.values():
            p._set_new_coordinator(initial_coordinator_pid)

    def run_cli(self):
        while True:
            print("\n--- Simulation Menu ---")
            print("status           - Show stats from all process")
            print("fail <pid>       - Simulates a process fail")
            print("retrive <pid>    - Semilates a process retrive")
            print("scenario a       - Coordinator fails and return")
            print("scenario b       - Multiple fails")
            print("exit             - End Simulation")

            cmd = input("> ").lower().strip().split()

            if not cmd: continue

            if cmd[0] == 'status':
                self._print_status()
            elif cmd[0] == 'fail' and len(cmd) > 1:
                self._fail_process(int(cmd[1]))
            elif cmd[0] == 'retrive' and len(cmd) > 1:
                self._recover_process(int(cmd[1]))
            elif cmd[0] == 'scenario' and len(cmd) > 1:
                if cmd[1] == 'a':
                    self._run_scenario_a()
                elif cmd[1] == 'b':
                    self._run_scenario_b()
            elif cmd[0] == 'exit':
                self._shutdown()
                break
            else:
                print("Invalid comand.")

    def _print_status(self):
        print("\n--- Atual status ---")
        for pid, p in sorted(self.processos.items()):
            status = "ON" if p.is_active else "OFF"
            is_coord = " (Coordinator)" if p.is_coordinator else ""
            print(f"Process {pid}: {status}, Coordinators: {p.coordinator_pid}{is_coord}")

    def _fail_process(self, pid):
        if pid in self.processos and self.processos[pid].is_active:
            print(f"\n--- Simulating process fails {pid} ---")
            self.processos[pid].stop()

            del self.peers[pid]

            for p in self.processos.values():
                if p.is_active:
                    p.peers = self.peers.copy()
        else:
            print(f"Process {pid} not found or already failed.")

    def _recover_process(self, pid):
        if pid in self.processos and not self.processos[pid].is_active:
            print(f"\n--- Simulating process retrive {pid} ---")
            alg = self.processos[pid].algorithm

            self._start_process(pid, alg)

            for p in self.processos.values():
                if p.is_active:
                    p.peers = self.peers.copy()

            time.sleep(1)
            self.processos[pid].start_election()
        else:
            print(f"Process {pid} not found or already activated.")

    def _run_scenario_a(self):
        print("\n--- Runing scenario A ---")
        current_coordinator_pid = max([p.pid for p in self.processos.values() if p.is_active])

        self._fail_process(current_coordinator_pid)

        print("\nWaiting fails")
        time.sleep(10)
        self._print_status()

        print(f"\nRetriving old coordinator ({current_coordinator_pid})")
        self._recover_process(current_coordinator_pid)
        print("\nThe retrive process will start a new election")
        time.sleep(10)
        self._print_status()

    def _run_scenario_b(self):

        print("\n--- Runing scenario B ---")
        active_pids = sorted([p.pid for p in self.processos.values() if p.is_active])
        if len(active_pids) < 3:
            print("You need 3 process on this scenario.")
            return

        pid_to_fail1 = active_pids[0]
        pid_to_fail2 = active_pids[1]

        self._fail_process(pid_to_fail1)
        self._fail_process(pid_to_fail2)

        print("\nTwo process failed, the system must be runing normaly")
        time.sleep(5)
        self._print_status()

        current_coordinator_pid = max([p.pid for p in self.processos.values() if p.is_active])
        self._fail_process(current_coordinator_pid)

        print("\nThe coordinator failed, waiting a new election among the survivors")
        time.sleep(10)
        self._print_status()

    def _shutdown(self):
        print("Ending all process")
        for p in self.processos.values():
            if p.is_active:
                p.stop()
        sys.exit(0)

if __name__ == '__main__':
    sim = Simulator()
    sim.setup()
    sim.run_cli()
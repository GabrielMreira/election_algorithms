import socket
import threading
import time
import json
import logging
from random import randint

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [%(process_name)s] %(message)s')

class Process:
    def __init__(self, pid, port, peers, algorithm):
        self.pid = pid
        self.port = port
        self.host = '127.0.0.1'
        self.peers = peers
        self.algorithm = algorithm

        self.coordinator_pid = None
        self.is_coordinator = False
        self.is_active = True
        self.election_in_progress = False
        self.lock = threading.Lock()

        threading.current_thread().name = f"Process-{self.pid}"
        self.server_thread = threading.Thread(target=self._listen, daemon=True)
        self.server_thread.start()

        self.health_check_thread = threading.Thread(target=self._check_coordinator_health, daemon=True)
        self.health_check_thread.start()

    def _check_coordinator_health(self):
        while self.is_active:
            time.sleep(5 + randint(0, 3))
            if self.coordinator_pid is None or self.pid == self.coordinator_pid:
                continue

            logging.info(f"Cheking coordinator health {self.coordinator_pid}")
            is_alive = self._send_message(self.coordinator_pid, {'type': 'PING', 'sender_pid': self.pid})

            if not is_alive and not self.election_in_progress:
                logging.warning(f"Coodinator {self.coordinator_pid} failed. Initializing election.")
                self.start_election()

    def _announce_victory(self):
        logging.info("Election won")
        self._set_new_coordinator(self.pid)
        self._send_message_to_all({'type': 'COORDINATOR', 'sender_pid': self.pid})

    def stop(self):
        self.is_active = False
        try:
            socket.create_connection((self.host, self.port), timeout=1)
        except (ConnectionRefusedError, socket.timeout):
            pass
        logging.info(f"Process {self.pid} ended.")

    def _get_next_peer_in_ring(self):
        sorted_pids = sorted(self.peers.keys())
        current_idx = sorted_pids.index(self.pid)

        for i in range(1, len(sorted_pids) + 1):
            next_idx = (current_idx + i) % len(sorted_pids)
            next_pid = sorted_pids[next_idx]

            if self._send_message(next_pid, {'type': 'PING', 'sender_pid': self.pid}):
                return next_pid

        return None

    def _start_election_bully(self):
        higher_pids = [p for p in self.peers if p > self.pid]

        if not higher_pids:
            self._announce_victory()
            return

        responded = False
        for pid in higher_pids:
            if self._send_message(pid,  {'type': 'ELECTION', 'sender_pid': self.pid}):
                responded = True

        time.sleep(3)
        if not responded:
            self._announce_victory()

    def _start_election_ring(self):
        next_peer = self._get_next_peer_in_ring()

        if next_peer is not None:
            self._send_message(next_peer, {'type': 'ELECTION', 'participants': [self.pid], 'sender_pid': self.pid})
        else:
            self._announce_victory()

    def start_election(self):
        with self.lock:
            if self.election_in_progress:
                logging.info("Election in progress")
                return

            logging.info("Initializing election.")
            self.election_in_progress = True

        if self.algorithm == 'bully':
            self._start_election_bully()
        elif self.algorithm == 'ring':
            self._start_election_ring()


    def _send_message_to_all(self, msg):
        for pid in self.peers:
            if pid != self.pid:
                self._send_message(pid, msg)

    def _set_new_coordinator(self, coord_id):
        with self.lock:
            if self.coordinator_pid != coord_id:
                self.coordinator_pid = coord_id
                self.is_coordinator = (self.pid == coord_id)
                logging.info(f"New coordinator elected: {self.coordinator_pid}")
                if self.is_coordinator:
                    logging.info("I'm the new coordinator")
            self.election_in_progress = False

    def _send_message(self, target_pid, msg):
        if not self.is_active:
            return

        target_port = self.peers.get(target_pid)
        if not target_port:
            logging.error(f"PID {target_pid} not found")

        try:
            with socket.create_connection((self.host, target_port), timeout=2) as sock:
                logging.info(f"Sending '{msg.get('type')}' for {target_pid}")
                sock.sendall(json.dumps(msg).encode())
                return True
        except (ConnectionResetError, socket.timeout, OSError) as e:
            logging.warning(f"Cannot conect in process {target_pid}: {e}")
            return False


    def _handle_message(self, msg, conn=None):
        msg_type = msg.get('type')
        sender_pid = msg.get('sender_pid')
        logging.info(f"Message type {msg_type} received from {sender_pid}")

        if self.algorithm == 'bully':
            if msg_type == 'ELECTION':
                response = {'type': 'OK', 'sender_pid': self.pid}
                self._send_message(sender_pid, response)
                if not self.election_in_progress:
                    self.start_election()

            elif msg_type == 'OK':
                with self.lock:
                    self.election_in_progress = True

            elif msg_type == 'COORDINATOR':
                self._set_new_coordinator(sender_pid)

        elif self.algorithm == 'ring':
            if msg_type == 'ELECTION':
                participants = msg.get('participants', [])
                if self.pid in participants:
                    new_coordinator_pid = max(participants)
                    self._send_message_to_all({'type': 'COORDINATOR', 'sender_pid': new_coordinator_pid})
                else:
                    participants.append(self.pid)
                    next_peer = self._get_next_peer_in_ring()
                    self._send_message(next_peer, {'type': 'ELECTION', 'participants': participants, 'sender_pid': self.pid})



            elif msg_type == 'COORDINATOR':
                self._set_new_coordinator(sender_pid)

        if msg_type == 'PING':
            conn.sendall(json.dumps({'type': 'PONG', 'sender_pid': self.pid}).encode())


    def _listen(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen()

        logging.info(f"Listening in  {self.host}:{self.port}")

        while self.is_active:
            try:
                conn, addr = server_socket.accept()
                threading.Thread(target=self._handle_connection, args=(conn,)).start()
            except OSError:
                break

    def _handle_connection(self, conn):
        try:
            with conn:
                data = conn.recv(1024)
                if not data:
                    return

                message = json.load(data.decode())
                self._handle_message(message, conn)
        except (json.JSONDecodeError, ConnectionResetError) as e:
            logging.error(f"Erro processing message: {e}")

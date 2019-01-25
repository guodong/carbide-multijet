import socket, json, time
from core.space import Space

BUF_SIZE = 4096


class Server:
    def __init__(self):
        self.on_peer_notify = None

    def start(self, port=9999):
        self.port = port
        ip_port = ('0.0.0.0', port)
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(ip_port)
        while True:
            data, client = server.recvfrom(BUF_SIZE)
            if client[0] == self.ip:  # ignore broadcast from myself
                continue

            print 'starttime: %d' % int(time.time() * 1000000)
            print('recv: ', len(data), client[0], data)
            msg = json.loads(data)
            # self.on_peer_notify(msg['protocol'], msg['property'], msg['space'])
            continue

            if False: # 'type' in msg and msg['type'] == 'request':
                for property in self.pm.entries:
                    msg_to_send = {
                        'protocol': 'p1',  # TODO: consider different protocol
                        'property': property,
                        'space': self.pm.union_space(property)
                    }
                    self.unicast(json.dumps(msg_to_send), self.get_node_by_ip(client[0])['ip'])
            else:
                space = Space(areas=msg['space'])
                changed = self.cal_pm(msg['protocol'], msg['property'], space, self.get_node_by_ip(client[0])['name'])
                if changed:
                    msg_to_send = {
                        'protocol': msg['protocol'],
                        'property': msg['property'],
                        # 'action': msg['action'],
                        'space': self.pm.union_space(msg['property'])
                    }
                    self.flood(json.dumps(msg_to_send), client[0])

            print 'endtime: %d' % int(time.time() * 1000000)

    def flood(self, msg):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(msg, ('255.255.255.255', self.port))
        return


import struct, socket


def intersect(space1, space2):
    if space1 is None or space2 is None:  # if space is empty
        return None
    result_space = ''
    for i in range(0, len(space1)):
        if space1[i] == space2[i]:
            result_space += space1[i]
        elif ord(space1[i]) + ord(space2[i]) == 97:  # 1 0 or 0 1
            return None
        elif space1[i] == '*':
            result_space += space2[i]
        else:
            result_space += space1[i]

    return result_space


header_map = {
    "dl_dst": (0, 48),
    "dl_src": (1, 48),
    "eth_type": (2, 16),
    "ip_version": (3, 4),
    "ihl": (4, 4),
    "diffserv": (5, 8),
    "total_length": (6, 16),
    "identification": (7, 16),
    "flags": (8, 3),
    "frag": (9, 13),
    "ttl": (10, 8),
    "protocol": (11, 8),
    "checksum": (12, 16),
    "ipv4_src": (13, 32),
    "ipv4_dst": (14, 32),
    "tcp_src": (15, 16),
    "tcp_dst": (16, 16),
    "tcp_length": (17, 16),
    "tcp_checksum": (18, 16)
}


class Space:
    def __init__(self, areas=None, match=None):
        if areas is None:
            areas = []
        self.areas = areas

        if match is None:
            match = {}
        self.match = match

        if len(match) > 0:
            self.areas.append(self.build_space_for_match(match))

    @staticmethod
    def gen_bits(size, bit='*'):
        bits = ''
        for i in range(0, size):
            bits += bit
        return bits

    def build_space_for_match(self, match):

        headers = [
            self.gen_bits(48),  # dl_dst
            self.gen_bits(48),  # dl_src
            self.gen_bits(16),  # dl_type
            self.gen_bits(4),  # ip_version
            self.gen_bits(4),  # ihl
            self.gen_bits(8),  # diffserv
            self.gen_bits(16),  # total_length
            self.gen_bits(16),  # identification
            self.gen_bits(3),  # flags
            self.gen_bits(13),  # frag
            self.gen_bits(8),  # ttl
            self.gen_bits(8),  # protocol
            self.gen_bits(16),  # checksum
            self.gen_bits(32),  # nw_src
            self.gen_bits(32),  # nw_dst
            self.gen_bits(16),  # tcp_src
            self.gen_bits(16),  # tcp_dst
            self.gen_bits(16),  # tcp_length
            self.gen_bits(16)  # tcp_checksum
        ]
        for field, value in match.items():
            index = header_map[field][0]
            v = self.gen_bits(header_map[field][1])
            if field == 'ipv4_dst' or field == 'ipv4_src':
                ipint = struct.unpack("!I", socket.inet_aton(value[0]))[0]  # 1.1.1.1
                mask = sum([bin(int(x)).count('1') for x in value[1].split('.')])  # 24
                bits = self.gen_match_bits(field=field, value=ipint, mask=mask)
            else:
                bits = self.gen_match_bits(field=field, value=value)
            headers[index] = intersect(headers[index], bits)

        return ''.join(headers)


    def gen_match_bits(self, field='', value=0, mask=None):
        '''
        generate bit string from filed=value+mask
        :param field: header field
        :param value: int value in decimal
        :param mask: int value of mask
        :return: bit string
        '''
        size = header_map[field][1]
        if mask is None:
            mask = size

        bits = "{0:b}".format(value).rjust(size, '0')
        bits = bits[:mask]
        bits = bits.ljust(size, '*')

        return bits

    # returns boolean: space changed or not
    def plus(self, space):
        if len(space.areas) == 0:
            return False

        changed = False

        for sa in space.areas:
            exist = False
            for a in self.areas:
                if a == sa:
                    exist = True
                    break

            if exist is False:
                self.areas.append(sa)
                changed = True

        self.areas.sort()

        return changed

    def minus(self, space):
        for sa in space.areas:
            if sa in self.areas:
                self.areas.remove(sa)
            else:
                # TODO: remove area using algebra
                return

    def multiply(self, space):
        result = []
        for sa in space.areas:
            for a in self.areas:
                result.append(intersect(sa, a))

        self.areas = [x for x in result if x is not None]
        self.areas = list(set(self.areas))
        self.areas.sort()

    # TODO: unordered areas compare
    def equal(self, space):
        space.areas.sort()
        if len(space.areas) != len(self.areas):
            return False

        for i in range(len(self.areas)):
            if space.areas[i] != self.areas[i]:
                return False

        return True

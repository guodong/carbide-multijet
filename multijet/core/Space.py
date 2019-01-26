import struct, socket

header_map = {
    "eth_dst": (0, 48),
    "eth_src": (1, 48),
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
    print result_space
    return result_space


class Space:
    def __init__(self, areas=None, match=None):
        if areas is None:
            areas = []

        self.areas = []

        # must copy areas, in case area change outside makes this space change
        for a in areas:
            self.areas.append(a)

        if match is None:
            match = {}
        self.match = match

        if len(match) > 0:
            self.areas.append(self.build_space_for_match(match))

    def build_space_for_match(self, match):

        headers = [
            ''.ljust(48, '*'),  # dl_dst
            ''.ljust(48, '*'),  # dl_src
            ''.ljust(16, '*'),  # dl_type
            ''.ljust(4, '*'),  # ip_version
            ''.ljust(4, '*'),  # ihl
            ''.ljust(8, '*'),  # diffserv
            ''.ljust(16, '*'),  # total_length
            ''.ljust(16, '*'),  # identification
            ''.ljust(3, '*'),  # flags
            ''.ljust(13, '*'),  # frag
            ''.ljust(8, '*'),  # ttl
            ''.ljust(8, '*'),  # protocol
            ''.ljust(16, '*'),  # checksum
            ''.ljust(32, '*'),  # nw_src
            ''.ljust(32, '*'),  # nw_dst
            ''.ljust(16, '*'),  # tcp_src
            ''.ljust(16, '*'),  # tcp_dst
            ''.ljust(16, '*'),  # tcp_length
            ''.ljust(16, '*')  # tcp_checksum
        ]
        for field, value in match.items():
            index = header_map[field][0]
            if field == 'ipv4_dst' or field == 'ipv4_src':
                ipint = struct.unpack("!I", socket.inet_aton(value[0]))[0]  # eg: 1.1.1.1 -> int
                mask = sum([bin(int(x)).count('1') for x in value[1].split('.')])  # eg: 255.255.255.0 -> 24
                bits = self.gen_match_bits(field=field, value=ipint, mask=mask)
            elif field == 'eth_src' or field == 'eth_dst':
                bits = bin(int(value.replace(':', ''), 16))[2:]
                bits = bits.rjust(48, '0')
            else:
                bits = self.gen_match_bits(field=field, value=value)
            headers[index] = bits

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

        # self.areas.sort()

        return changed

    def multiply(self, space):
        result = []
        for sa in space.areas:
            for a in self.areas:
                result.append(intersect(sa, a))

        self.areas = [x for x in result if x is not None]
        # self.areas = list(set(self.areas))
        # self.areas.sort()

    def notme(self):
        spaces = []
        for a in self.areas:
            s = Space()
            for i in range(len(a)):
                if a[i] is not '*':
                    item = list(''.ljust(len(a), '*'))
                    item[i] = a[i]
                    s.areas.append(''.join(item))
            spaces.append(s)

        result = Space(areas=[''.ljust(336, '*')])
        for s in spaces:
            result.multiply(s)

        return result

    def clone(self):
        space = Space()
        for a in self.areas:
            space.areas.append(a)

        return space





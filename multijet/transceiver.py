import pickle
import zlib
import struct

from .utils import debug


class Transceiver(object):
    def __init__(self):
        self._recv_callback = None

    def set_recv_callback(self, callback):
        self._recv_callback = callback

    def send(self, obj, target): raise NotImplementedError

    def on_recv(self, data, source): raise NotImplementedError

    def dump(self): raise NotImplementedError


class LayeredTransceiver(Transceiver):
    def __init__(self, out_trans):
        super(LayeredTransceiver, self).__init__()
        self._out_trans = out_trans  # type: Transceiver
        self._out_trans.set_recv_callback(self.on_recv)

    def send(self, obj, target): raise NotImplementedError

    def on_recv(self, data, source): raise NotImplementedError

    def dump(self):
        return self._out_trans.dump()


class PickledZippedTransceiver(LayeredTransceiver):
    def send(self, obj, target):
        pickled = pickle.dumps(obj, protocol=-1)
        data = zlib.compress(pickled)
        self._out_trans.send(data, target)

    def on_recv(self, data, source):
        pickled = zlib.decompress(data)
        obj = pickle.loads(pickled)
        if self._recv_callback:
            self._recv_callback(obj, source)


class _Buffer:
    def __init__(self, length):
        self.buf = bytearray(length)
        self.pad_size = 0
        self.pad_set = set()

    def pad(self, start, end, fragment):
        self.buf[start: end] = fragment
        self.pad_size += end-start

    def get_if_full(self):
        debug("pad_size=%d len=%d"%(self.pad_size, len(self.buf)))
        if self.pad_size==len(self.buf):
            return str(self.buf)
        return None


class ReassembleTransceiver(LayeredTransceiver):
    HEADER_FORMAT = "IIII"
    HEADER_LENGTH = struct.calcsize(HEADER_FORMAT)

    def __init__(self, out_trans, MTU=1200):
        super(ReassembleTransceiver, self).__init__(out_trans)
        self._seq_nums = {}
        self._MTU = MTU
        self._reassemble_buf = {}

    def send(self, data, target):
        sn = self._seq_nums.get(target, 0) + 1
        self._seq_nums[target] = sn
        for fragment in self._split_msg(data, sn):
            self._out_trans.send(fragment, target)

    def _split_msg(self, data, seq_num):
        # cpid seq_num  total_size start_offset end_offset  fragment
        total_size = len(data)
        offset = 0
        while offset<total_size:
            frag = data[offset:offset + self._MTU]
            start_offset = offset
            offset = offset + len(frag)
            end_offset = offset
            header = struct.pack(self.HEADER_FORMAT, seq_num, total_size, start_offset, end_offset)
            yield header+frag

    def on_recv(self, fragment, source):
        seq_num, ts, so, eo = struct.unpack_from(self.HEADER_FORMAT, fragment)
        debug("recv %d %d %d %d from %s" % (seq_num, ts, so, eo, str(source)))
        source_bufs = self._reassemble_buf.setdefault(source, {})
        buf = source_bufs.setdefault(seq_num, _Buffer(ts))
        data = fragment[self.HEADER_LENGTH:]
        if len(data) != eo - so:
            debug("error data length")
            return
        buf.pad(so, eo, data)
        msg = buf.get_if_full()
        if msg:
            source_bufs.pop(seq_num)
            self._recv_callback(msg, source)

    def dump(self):
        for source, d in self._reassemble_buf.items():
            if len(d)>0:
                return "error len(buf)=%d source=%s" % (len(d), str(source))
        return None


class DeMuxTransceiver(object):
    def __init__(self):
        self._recv_callback = {}

    def set_recv_callback(self, inst_id, callback):
        self._recv_callback[inst_id] = callback   # (data, source)

    def send(self, obj, target, source): raise NotImplementedError

    def on_recv(self, obj, source): raise NotImplementedError


class DeMuxAdapter(Transceiver):
    def __init__(self, out_demux, instance_id):
        super(DeMuxAdapter, self).__init__()
        self._out_demux = out_demux  # type: DeMuxTransceiver
        self._out_demux.set_recv_callback(instance_id, self.on_recv)
        self._id = instance_id

    def send(self, obj, target):
        self._out_demux.send(obj, target, self._id)

    def on_recv(self, obj, source):
        if self._recv_callback is not None:
            self._recv_callback(obj, source)


class BinaryLayeredDeMuxTransceiver(DeMuxTransceiver):
    HEADER_FORMAT = "I"
    HEADER_LENGTH = struct.calcsize(HEADER_FORMAT)

    def __init__(self, out_trans):
        super(BinaryLayeredDeMuxTransceiver, self).__init__()
        self._out_trans = out_trans  # type: Transceiver
        out_trans.set_recv_callback(self.on_recv)

    def send(self, data, target, source):
        header = struct.pack(self.HEADER_FORMAT, source)
        self._out_trans.send(header+data, target)

    def on_recv(self, data, source):
        inst_id = struct.unpack_from(self.HEADER_FORMAT, data)[0]
        f = self._recv_callback.get(inst_id)
        if f:
            f(data[self.HEADER_LENGTH:], source)


def build_transceiver(insts, out_trans):
    demux = BinaryLayeredDeMuxTransceiver(out_trans)
    l = {}
    for inst_id in insts:
        t = PickledZippedTransceiver(ReassembleTransceiver(DeMuxAdapter(demux, inst_id)))
        l[inst_id] = t
    return demux, l
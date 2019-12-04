import json
import re
import time
import os
import datetime

import numpy as np
import pandas as pd
import operator
from functools import reduce

import matplotlib.pyplot as plt


def pkt_rate(path='ignored/eval3/topo32/result-8-0.250000/netstat-ns-result.dat'):
    linfo = []
    with open(path) as f:
        while True:
            line = f.readline()
            if line:
                if line[:4] == 'pkts':
                    data = line.split('=')[1].split(' ')
                    result = []
                    for i in range(2, len(data) - 1):
                        rate = (int(data[i]) - int(data[i - 1])) * 10
                        result.append(rate)

                    linfo.append(result)
            else:
                break

    d = reduce(operator.add, linfo)
    da = [i for i in d if i != 0]
    print sorted(da)
    print len(linfo)
    print len(d)
    n, bins, patches = plt.hist(da, 400, density=True, cumulative=True, label='CDF',
                                histtype='step', color='k')
    patches[0].set_xy(patches[0].get_xy()[:-1])
    plt.xlabel('rate(bps)')
    plt.ylabel('CDF')
    plt.show()


def byte_count(path='ignored/eval3/topo32/result-8-0.250000/netstat-ns-result.dat'):
    with open(path) as f:
        total_bytes = 0
        total_pkts = 0
        while True:
            line = f.readline()
            if line:
                if line[:5] == 'bytes':
                    data = line.split('=')[1].split(' ')
                    total_bytes += (int(data[-2]) - int(data[0]))
                elif line[:4] == 'pkts':
                    data = line.split('=')[1].split(' ')
                    total_pkts += (int(data[-2]) - int(data[0]))
            else:
                break
        print total_bytes, total_pkts
        return total_bytes, total_pkts

def cdf(da, xl='Latency(ms)', savefig=None):
    plt.clf()
    n, bins, patches = plt.hist(da, 400, density=True, cumulative=True, label='CDF',
                                histtype='step', color='k')
    patches[0].set_xy(patches[0].get_xy()[:-1])
    plt.xlabel(xl)
    plt.ylabel('CDF')
    if savefig is None:
        plt.show()
    else:
        plt.savefig(savefig, bbox_inches='tight')


def timeline():
    x = []
    y = []
    with open('result/raw/' + 'output.0.25.dat') as f:
        s = f.read()
        d = json.loads(s)  # {nid: [tms]}
        # print len(d)
        i = 0
        print len(d.items())
        print d
        for id in d:
            time_list = d[id]
            x = x + time_list
            for _t in range(len(time_list)):
                y.append(i)
            i += 1
    print y
    plt.scatter(x, y, s=4)
    plt.grid(True)
    plt.xlabel('Time(s)')
    plt.ylabel('Router id')
    plt.xlim(0, 8)
    plt.show()


def pc_cdf(path='ignored/eval3/topo32/result-8-0.250000/netstat-ns-result.dat', savefig=None, savefig2=None):
    bdata = {}
    pdata = {}
    with open(path) as f:
        total_bytes = 0
        total_pkts = 0
        current_sw = 1

        bdata[current_sw] = 0
        pdata[current_sw] = 0
        while True:
            line = f.readline()
            if line:
                if line[:5] == 'bytes':
                    data = line.split('=')[1].split(' ')
                    bdata[current_sw] += (int(data[-2]) - int(data[0]))
                elif line[:4] == 'pkts':
                    data = line.split('=')[1].split(' ')
                    pdata[current_sw] += (int(data[-2]) - int(data[0]))
                elif line[:2] == 'ns':
                    current_sw += 1
                    bdata[current_sw] = 0
                    pdata[current_sw] = 0
                    total_bytes = 0
                    total_pkts = 0

            else:
                break
        d = [i for i in bdata.values()]
        p = [i for i in pdata.values()]
        cdf(d, '#Bytes', savefig)
        cdf(p, '#Pkts', savefig2)

def pc_cdf_2(path='ignored/eval3/topo32/result-8-0.250000/netstat-ns-result.dat', savefig_prefix = None):
    bdata = []
    pdata = []
    with open(path) as f:
        total_bytes = 0
        total_pkts = 0
        current_sw = 1
        last_port_name = None

        while True:
            line = f.readline()
            if line:
                if line.startswith("port_name="):
                    last_port_name = line[len("port_name="):]
                    last_port_name = last_port_name.strip()
                    print(last_port_name)
                elif line[:5] == 'bytes' and last_port_name == "eth0":
                    data = line.split('=')[1].split(' ')
                    total_bytes = (int(data[-2]) - int(data[0]))
                    bdata.append(total_bytes)
                elif line[:4] == 'pkts' and last_port_name == "eth0":
                    data = line.split('=')[1].split(' ')
                    total_pkts = (int(data[-2]) - int(data[0]))
                    pdata.append(total_pkts)
            else:
                break
        if savefig_prefix:
            cdf(bdata, '#Bytes', savefig_prefix+"-bytes.png")
            cdf(pdata, '#Pkts', savefig_prefix + "-pkts.png")
            bdata.remove(max(bdata))
            cdf(bdata, '#Bytes', savefig_prefix+"-bytes-no-ctl.png")
            pdata.remove(max(pdata))
            cdf(pdata, '#Pkts', savefig_prefix + "-pkts-no-ctl.png")
        else:
            cdf(bdata, '#Bytes')
            cdf(pdata, '#Pkts')
            bdata.remove(max(bdata))
            cdf(bdata, '#Bytes')
            pdata.remove(max(pdata))
            cdf(pdata, '#Pkts')


def plot_byte_count_all():

    data_dir = 'ignored/eval3/topo64-5'
    figures_dir = data_dir + '-figures'
    os.system("mkdir -p " + figures_dir)

    y1 = []
    y2 = []
    for i in range(0, 8):
        freq = 0.125 * 2**i
        path = data_dir + '/result-8-%f/netstat-ns-result.dat' % freq
        total_bytes, total_pkts = byte_count(path)
        y1.append(total_bytes)
        y2.append(total_pkts)
    x = [0.125, 0.25, 0.5, 1, 2, 4, 8, 16]

    plt.clf()
    plt.xlabel('Link status change frequency(Hz)')
    plt.ylabel('#Bytes')
    plt.plot(x, y1, "x-", label="")
    # plt.show()
    plt.savefig(figures_dir + '/bytes.png', bbox_inches='tight')

    plt.clf()
    plt.xlabel('Link status change frequency(Hz)')
    plt.ylabel('#Packets')
    plt.plot(x, y2, "x-", label="")
    # plt.show()
    plt.savefig(figures_dir + '/packets.png', bbox_inches='tight')

    with open(figures_dir + '/data-bytes-packets.json', 'w') as f:
        json.dump({
            "freq": x,
            "bytes": y1,
            "pkts": y2
        }, f)


def plot_pc_cdf_all():
    data_dir = 'ignored/eval3/topo64-5'
    figures_dir = data_dir + '-figures'
    os.system("mkdir -p " + figures_dir)

    for i in range(1, 8):
        freq = 0.125 * 2 ** i
        path = data_dir + '/result-8-%f/netstat-ns-result.dat' % freq
        savefig = figures_dir + '/cdf-bytes-%f.png' % freq
        savefig2 = figures_dir + '/cdf-packets-%f.png' % freq
        # savefig = None
        # savefig2 = None
        pc_cdf_2(path, savefig_prefix = figures_dir + "/cdf-%f" % freq)


def plot_ryufly_update(path='ignored/eval3/topo32/result-8-16.000000/ryufly.log'):
    with open(path) as f:
        lines = f.readlines()

    t1 = t2 = None

    data = []

    for line in lines:
        mats = re.findall("'update start', ([\d\\.]+)", line)
        if mats:
            assert t1 is None
            t1 = float(mats[0])
        else:
            mats = re.findall("'update finish', ([\d\\.]+)", line)
            if mats:
                assert t1 is not None and t2 is None
                t2 = float(mats[0])
                data.append((t1, t2))
                t1 = t2 = None
    print(data)

    y = [a[1]-a[0] for a in data[1:]]
    x = list(range(1, len(y)+1))
    # plt.clf()
    # plt.plot(x, y)
    # plt.show()
    freq = 16.000000
    savefig = 'ignored/eval3/topo32-figures/cdf-controller-update-time-%f.png' % freq
    cdf(y, xl="SDN controller update time(s)", savefig=savefig)



def plot_byte_count_all_compare():
    y1 = []
    y2 = []
    for i in range(0, 8):
        if i==0:
            y1.append(90000)
            y2.append(900)
            continue
        freq = 0.125 * 2**i
        path = 'ignored/eval3/topo64-5/result-8-%f/netstat-ns-result.dat' % freq
        print(path)
        total_bytes, total_pkts = byte_count(path)
        y1.append(total_bytes)
        y2.append(total_pkts)
        print(y1)
    x = [0.125, 0.25, 0.5, 1, 2, 4, 8, 16]
    print(y1)


    # ospf_y1 = [106782,198390,370120,615622,1018816,1313168,1471672]
    ospf_y1 = [286404, 394054, 676826, 1571450, 2253536, 4100508, 5916858, 7271384]
    # ospf_y2 = [1033,1809,3019,5043,7936,10024,11132]
    ospf_y2 = [2454, 3843, 6395, 12517, 17412, 31132, 41993, 52232]

    plt.clf()
    plt.xlabel('Link status change frequency(Hz)')
    plt.ylabel('#Bytes')
    plt.plot(x, y1, "x-", label="SDN")
    plt.plot(x, ospf_y1, "o-", label="OSPF")
    plt.legend()
    # plt.show()
    plt.savefig('ignored/eval3/topo64-5-figures/bytes-cmp.png', bbox_inches='tight')

    plt.clf()
    plt.xlabel('Link status change frequency(Hz)')
    plt.ylabel('#Packets')
    plt.plot(x, y2, "x-", label="SDN")
    plt.plot(x, ospf_y2, "o-", label="OSPF")
    plt.legend()
    # plt.show()
    plt.savefig('ignored/eval3/topo64-5-figures/packets-cmp.png', bbox_inches='tight')


def load_ovs_vswitchd_log(path="configs/common/11-ovs-vswitchd.log"):
    with open(path) as f:
        lines = f.readlines()
    rec = re.compile(r"^([\d-]+)T([\d:\.]+)Z.*(OFPT_PORT_STATUS|OFPT_FLOW_MOD).*")

    time_port_status = []
    time_flow_mod = []

    epoch = datetime.datetime.utcfromtimestamp(0)

    for line in lines:
        a = rec.match(line)
        if a is not None:
            d, t, msg = a.groups()
            tt = "%s %s000" % (d, t)
            t1 = datetime.datetime.strptime(tt, "%Y-%m-%d %H:%M:%S.%f")
            t2 = (t1 - epoch).total_seconds()
            if msg == "OFPT_PORT_STATUS":
                time_port_status.append(t2)
            elif msg == "OFPT_FLOW_MOD":
                time_flow_mod.append(t2)
    return time_port_status, time_flow_mod


def plot_time_line_all():
    data_dir = "ignored/eval3/topo64-precompute"
    figures_dir = data_dir + "-figures"
    os.system("mkdir -p " + figures_dir)

    port_time = []
    port_node = []
    flow_time = []
    flow_node = []
    for i in range(64):
        path = "%s/n%d-ovs-vswitchd.log" % (data_dir, i)
        tp, tf = load_ovs_vswitchd_log(path)
        port_time.extend(tp)
        port_node.extend([i] * len(tp))
        flow_time.extend(tf)
        flow_node.extend([i] * len(tf))

    port_node = np.array(port_node)
    flow_node = np.array(flow_node)
    port_time = np.array(port_time)
    flow_time = np.array(flow_time)
    # start_time = min(port_time.min(), flow_time.min())
    # port_time -= start_time
    # flow_time -= start_time
    for i in range(0, 8):
        freq = 0.125 * 2 ** i
        path = '%s/result-8-%f/link-down-up.log' % (data_dir, freq)
        with open(path) as f:
            link_hist = json.load(f)
        start_time = link_hist[0]['time']

        ft1 = flow_time - start_time
        pt1 = port_time - start_time


        x_axis_start = 0
        x_axis_end = 20

        # if i in (4,5):
        #     x_axis_end = 10
        # elif i==6:
        #     x_axis_end = 14
        # elif i==7:
        #     x_axis_end = 40

        fts = np.logical_and((x_axis_start < ft1), (ft1 < x_axis_end))
        pts = np.logical_and((x_axis_start < pt1), (pt1 < x_axis_end))

        ft2 = ft1[fts]
        fn2 = flow_node[fts]
        pt2 = pt1[pts]
        pn2 = port_node[pts]

        # print(ft2)
        print(freq, ft2.max()-pt2.max())

        plt.clf()
        plt.grid()
        plt.scatter(ft2, fn2, label="Flow_Mod", s=1.5)
        plt.scatter(pt2, pn2, label="Port Event", s=1.5)
        plt.legend()
        plt.xlim([x_axis_start, x_axis_end])
        # plt.show()
        plt.xlabel("Time(s)")
        plt.ylabel("Router id")
        plt.savefig(figures_dir+"/timeline-%f.png" % freq, bbox_inches='tight')


def load_netstat_ns_result(path):
    with open(path) as f:
        lines = f.readlines()

    data = {}
    node_data = None
    port_data = None

    timestamps = None
    data_columns = ["timestamps", "bytes", "pkts", "tbytes", "tpkts"]

    for line in lines:
        line = line.strip()
        if line.startswith("node_name= "):
            node_name = line[len("node_name= ") :]
            node_data = data[node_name] = {}
        elif line.startswith("port_name="):
            port_name = line[len("port_name=") :]
            port_data = node_data[port_name] = pd.DataFrame({"timestamps": timestamps})
        else:
            for c in data_columns:
                if line.startswith(c+"="):
                    if c=="timestamps":
                        d = np.fromstring(line[len(c + "="):], dtype=float, sep=" ")
                        timestamps = d
                    else:
                        d = np.fromstring(line[len(c + "="):], dtype=int, sep=" ")
                        port_data[c] = d

    # for n,v in data.items():
    #     data[n] = pd.DataFrame(v)
    # data = pd.DataFrame(data)
    return data


def get_rate(d):
    data_columns = ["timestamps", "bytes", "pkts", "tbytes", "tpkts"]
    ret = []
    for yi in (1, 2):
        x = d[data_columns[0]]
        yname = data_columns[yi]
        y = d[yname]
        y = y.values
        x = x.values
        x = x - x.min()
        x = x[:-1]
        y = y[1:] - y[:-1]
        if yi == 1:
            y = y*8.0/0.02 / 1024.0

        # y = y[y>0]

        # plt.clf()
        # plt.plot(x,y)
        # plt.ylabel(yname)
        # plt.show()
        ret.append(y)
    return ret


def main():

    data_dir = "ignored/eval3/topo64-precompute-bw48"
    figures_dir = data_dir + "-figures"
    os.system("mkdir -p " + figures_dir)

    for i in range(7, 8):
        freq = 0.125 * 2 ** i
        path = '%s/result-8-%f/netstat-ns-result.dat' % (data_dir, freq)
        data = load_netstat_ns_result(path)
        br_all = np.array([])
        for n, v in data.items():
            # if n == "ryufly":
            #     continue
            for p, d in v.items():
                if p=="eth0":
                    br, pr = get_rate(d)
                    br_all = np.append(br_all, br)
                    break
        cdf(br_all, xl="eth0 flow rate(kb/s)")


if __name__=="__main__":
    main()
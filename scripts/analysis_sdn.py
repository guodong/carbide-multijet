import json
import re

import numpy as np
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


def byte_rate():
    with open("ospf_64k_100ms.dat") as f:
        linfo = []
        while True:
            line = f.readline()
            if line:
                if line[:5] == 'bytes':
                    data = line.split('=')[1].split(' ')
                    result = []
                    for i in range(2, len(data) - 1):
                        rate = (int(data[i]) - int(data[i - 1])) * 10 * 8
                        result.append(rate)

                    linfo.append(result)

                    # print result

                # elif line[:4] == 'pkts':
                #
                #     data = line.split('=')[1].split(' ')
                #     result = []
                #     for i in range(2, len(data) - 1):
                #         result.append(int(data[i]) - int(data[i - 1]))
                #
                #     print result


            else:
                break
        # print len(linfo), len(linfo[0])
        # plt.figure(figsize=(20, 8), dpi=80)
        # x = range(len(linfo[0])) #[i * 20 for i in range(len(linfo[0]))]
        # y = linfo[1]
        # plt.bar(x, y)
        # plt.show()
        # print len(linfo[0])
        # exit()

        d = reduce(operator.add, linfo)
        da = [i for i in d if i != 0]
        da = sorted(da)
        print sorted(da)
        print len(linfo)
        print len(d)
        print da.index(40000), len(da)
        print np.mean(da), np.median(da)
        n, bins, patches = plt.hist(da, 4000, density=True, cumulative=True, label='CDF',
                                    histtype='step', color='k')
        patches[0].set_xy(patches[0].get_xy()[:-1])
        plt.xlabel('Rate(bps)')
        plt.ylabel('CDF')
        plt.show()


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


# byte_rate()

def timeana():
    arr = '''
151 0.70992898941
211 0.187452077866
311 0.0279128551483
191 0.167434930801
61 0.0562980175018
131 0.174026012421
111 0.0417718887329
81 0.0553939342499
231 0.0270888805389
171 0.027783870697
01 0.251693964005
21 0.285852909088
41 0.027557849884
181 0.165605068207
281 0.0767800807953
201 0.0249910354614
141 0.142961025238
301 0.0819129943848
121 0.0263860225677
261 0.0268168449402
241 0.0264718532562
71 0.028501033783
91 0.0277960300446
251 0.0270059108734
101 0.0268878936768
161 0.0280320644379
221 0.027538061142
11 0.0929660797119
271 0.0528318881989
31 0.0274260044098
51 0.0441439151764
291 0.0336039066315
    '''
    t = arr.split('\n')
    t = [i.strip() for i in t][1:-1]
    x = sorted(t, key=lambda a: float(a.split(' ')[1]))
    for i in x:
        print i
    t = [float(i.split(' ')[1]) for i in t]
    t = sorted(t)
    print t, len(t)
    print np.mean(t), np.median(t)

    u = [i * 1000 for i in t]
    cdf(u)


def time_count_each():
    file_map = {
        '0.125': 'ospf_bw64k_fq0125.time.dat',
        '0.25': 'ospf_bw64k_fq025.time.dat',
        '0.5': 'ospf_bw64k_fq05.time.dat',
        '1': 'ospf_bw64k_fq1.time.dat',
        '2': 'ospf_bw64k_fq2.time.dat',
        '4': 'ospf_bw64k_fq4.time.dat',
        '8': 'ospf_bw64k_fq8.time.dat',
        '16': 'ospf_bw64k_fq16.time.dat',
    }
    tms = []

    with open('./result/raw/' + 'ospf_bw64k_fq05.time.dat') as f:
        while True:
            line = f.readline()
            if line:
                ct = float(line.split(' ')[1][:-1])
                tms.append(ct)
            else:
                break
    y = range(32)
    plt.scatter(tms, y)
    plt.grid(True)
    plt.xlabel('Time(s)')
    plt.ylabel('Router id')
    plt.xlim(0)
    plt.show()


def time_count():
    index_map = ['0.125', '0.25', '0.5', '1', '2', '4', '8', '16']
    file_map = {
        '0.125': 'ospf_bw64k_fq0125.time.dat',
        '0.25': 'ospf_bw64k_fq025.time.dat',
        '0.5': 'ospf_bw64k_fq05.time.dat',
        '1': 'ospf_bw64k_fq1.time.dat',
        '2': 'ospf_bw64k_fq2.time.dat',
        '4': 'ospf_bw64k_fq4.time.dat',
        '8': 'ospf_bw64k_fq8.time.dat',
        '16': 'ospf_bw64k_fq16.time.dat',
    }
    pval = {}
    for i in index_map:
        pval[i] = []
        with open('./result/raw/' + file_map[i]) as f:
            while True:
                line = f.readline()
                if line:
                    ct = float(line.split(' ')[1][:-1])
                    pval[i].append(ct)
                else:
                    break
        pval[i] = sorted(pval[i])

    for k, v in pval.items():
        print k, round(min(v), 3), round(max(v), 3), round(np.mean(v), 3), round(np.median(v), 3)

    x = range(32)
    for i in pval.values():
        n, bins, patches = plt.hist(i, 400, density=True, cumulative=True, label='CDF',
                                    histtype='step')
        patches[0].set_xy(patches[0].get_xy()[:-1])
    plt.xlabel('Latency(s)')
    plt.ylabel('CDF')
    # plt.plot(x, i, "x-",label="test_zhexian")
    plt.show()
    return

    fig = plt.figure()
    ax = fig.add_subplot(111)
    x = []
    for i in index_map:
        for j in range(32):
            x.append(i)
    print x
    y = pval
    print len(y)

    # ax.scatter(x, y, s=2, c='k', marker='x')
    plt.show()


fq = [0.125, 0.25, 0.5, 1, 2, 4, 8, 16]


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


def plot_byte_count_all():
    y1 = []
    y2 = []
    for i in range(1, 8):
        freq = 0.125 * 2**i
        path = 'ignored/eval3/topo32/result-8-%f/netstat-ns-result.dat' % freq
        total_bytes, total_pkts = byte_count(path)
        y1.append(total_bytes)
        y2.append(total_pkts)
    x = [0.25, 0.5, 1, 2, 4, 8, 16]

    plt.clf()
    plt.xlabel('Link status change frequency(Hz)')
    plt.ylabel('#Bytes')
    plt.plot(x, y1, "x-", label="")
    # plt.show()
    plt.savefig('ignored/eval3/topo32-figures/bytes.png', bbox_inches='tight')

    plt.clf()
    plt.xlabel('Link status change frequency(Hz)')
    plt.ylabel('#Packets')
    plt.plot(x, y2, "x-", label="")
    # plt.show()
    plt.savefig('ignored/eval3/topo32-figures/packets.png', bbox_inches='tight')

    with open('ignored/eval3/topo32-figures/data-bytes-packets.json', 'w') as f:
        json.dump({
            "freq": x,
            "bytes": y1,
            "pkts": y2
        }, f)


def plot_pc_cdf_all():
    for i in range(1, 8):
        freq = 0.125 * 2 ** i
        path = 'ignored/eval3/topo32/result-8-%f/netstat-ns-result.dat' % freq
        savefig = 'ignored/eval3/topo32-figures/cdf-bytes-%f.png' % freq
        savefig2 = 'ignored/eval3/topo32-figures/cdf-packets-%f.png' % freq
        pc_cdf(path, savefig, savefig2)


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
    for i in range(1, 8):
        freq = 0.125 * 2**i
        path = 'ignored/eval3/topo32/result-8-%f/netstat-ns-result.dat' % freq
        total_bytes, total_pkts = byte_count(path)
        y1.append(total_bytes)
        y2.append(total_pkts)
    x = [0.25, 0.5, 1, 2, 4, 8, 16]


    ospf_y1 = [106782,198390,370120,615622,1018816,1313168,1471672]
    ospf_y2 = [1033,1809,3019,5043,7936,10024,11132]

    plt.clf()
    plt.xlabel('Link status change frequency(Hz)')
    plt.ylabel('#Bytes')
    plt.plot(x, y1, "x-", label="SDN")
    plt.plot(x, ospf_y1, "o-", label="OSPF")
    plt.legend()
    # plt.show()
    plt.savefig('ignored/eval3/topo32-figures/bytes-cmp.png', bbox_inches='tight')

    plt.clf()
    plt.xlabel('Link status change frequency(Hz)')
    plt.ylabel('#Packets')
    plt.plot(x, y2, "x-", label="SDN")
    plt.plot(x, ospf_y2, "o-", label="OSPF")
    plt.legend()
    # plt.show()
    plt.savefig('ignored/eval3/topo32-figures/packets-cmp.png', bbox_inches='tight')


def main():
    plot_pc_cdf_all()


if __name__=="__main__":
    main()
import json

from collections import defaultdict

from matplotlib import pyplot as plt


def load_data(path):
    with open(path) as f:
        data = json.load(f)

    delta=[]
    num=[]
    send_stats = []
    recv_stats = []
    detail_delta_list = []

    send_statistics_map = [defaultdict(lambda: 0) for i in range(6)]
    recv_statistics_map = [defaultdict(lambda: 0) for i in range(6)]

    for item in data:
        delta.append(float(item['delta']))
        num.append(int(item['num']))

        send_delta_stats = [0] * 6
        recv_delta_stats = [0] * 6

        detail_delta = {}

        for n, detail in item['detail'].items():
            if 'stat' not in detail:
                break
            send_stat = detail['stat'][0]
            for i in range(6):
                send_delta_stats[i] += send_stat[i] - send_statistics_map[i][n]
                send_statistics_map[i][n] = send_stat[i]
            recv_stat = detail['stat'][1]
            for i in range(6):
                recv_delta_stats[i] += recv_stat[i] - recv_statistics_map[i][n]
                recv_statistics_map[i][n] = recv_stat[i]

            detail_delta[n]=detail['delta']

        send_stats.append(send_delta_stats)
        recv_stats.append(recv_delta_stats)
        detail_delta_list.append(detail_delta)

    return num, delta, send_stats, recv_stats, detail_delta_list

OUTPUTDIR = 'output.log/'

GLOBAL_SAVEFIG = True

GLOBAL_SHOW = False


def plot1(xx1, yy1, xx2, yy2, xl='Update sequence number',
          yl='Time (s)',
          title = 'Convergence time of network',
          savefig = None):
    plt.clf()
    plt.grid()
    plt.plot(xx1, yy1, 'b', label='Flood')
    plt.plot(xx2, yy2, 'r', label='PushPullNeighbor')
    plt.legend()
    if xl:
        plt.xlabel(xl)
    if yl:
        plt.ylabel(yl)
    if title:
        plt.title(title)

    if GLOBAL_SAVEFIG and savefig:
        plt.savefig(OUTPUTDIR + savefig)

    if GLOBAL_SHOW:
        plt.show()


def plot_detail_delta(detail_delta_list1, detail_delta_list2, xl='Update sequence number',
          yl='Time (s)',
          title = 'Convergence time of each node',
          savefig = None):
    assert len(detail_delta_list1)==len(detail_delta_list2)

    plt.clf()

    data1 = []
    data2 = []
    xlen = len(detail_delta_list1)
    for i in range(xlen):
        dd1 = detail_delta_list1[i]
        dd2 = detail_delta_list2[i]
        ks = set(dd1.keys()) & set(dd2.keys())
        l1 = [dd1[a] for a in ks]
        l2 = [dd2[a] for a in ks]
        data1.append(l1)
        data2.append(l2)
    widths = 0.3
    p1 = [i + 1 - widths/2 for i in range(xlen)]
    p2 = [i + 1 + widths/2 for i in range(xlen)]
    plt.boxplot(data1, positions=p1, widths=widths, boxprops=dict(color="blue"))
    plt.boxplot(data2, positions=p2, widths=widths, boxprops=dict(color="red"))
    x = [i+1 for i in range(xlen)]
    plt.xticks(x, [a for a in x])

    if xl:
        plt.xlabel(xl)
    if yl:
        plt.ylabel(yl)
    if title:
        plt.title(title)

    if GLOBAL_SAVEFIG and savefig:
        plt.savefig(OUTPUTDIR + savefig)

    plt.grid()

    if GLOBAL_SHOW:
        plt.show()


def singlepath(suffix='5-8'):
    num1, delta1, send_stat1, recv_stat1, detail_delta_list1 = load_data('/home/yutao/tmp/flood-node-%s.log' % suffix)
    num2, delta2, send_stat2, recv_stat2, detail_delta_list2 = load_data('/home/yutao/tmp/pp-node-%s.log' % suffix)

    prefix = 'single-path-%s-' % suffix
    type = ('install-path', 'delete', 'add')

    for i in range(3):
        _prefix = prefix + type[i]
        # xx1 = num1[i::3]
        xx1 = xx2 = list(range(1, 51))
        yy1 = delta1[i::3]
        # xx2 = num2[i::3]
        yy2 = delta2[i::3]
        plot1(xx1, yy1, xx2, yy2, savefig = '%s-time.png'%_prefix)

        _send_stat1 = send_stat1[i::3]
        _send_stat2 = send_stat2[i::3]
        _recv_stat1 = recv_stat1[i::3]
        _recv_stat2 = recv_stat2[i::3]
        base = 1024*1024.0
        send_pkts1 = [(a[1]+a[3]+a[5]) / base for a in _send_stat1]
        send_pkts2 = [(a[1]+a[3]+a[5]) / base for a in _send_stat2]
        plot1(xx1, send_pkts1, xx2, send_pkts2, yl='Send message size (MB)', title='Send message size',
              savefig='%s-send-msg.png'%_prefix)

        recv_pkts1 = [(a[1]+a[3]+a[5]) / base for a in _recv_stat1]
        recv_pkts2 = [(a[1]+a[3]+a[5]) / base for a in _recv_stat2]
        plot1(xx1, recv_pkts1, xx2, recv_pkts2, yl = 'Received message size (MB)', title='Received message size',
              savefig='%s-recv-msg.png'%_prefix)

        _detail_delta_list1 = detail_delta_list1[i:(30+i):3]
        _detail_delta_list2 = detail_delta_list2[i:(30+i):3]
        plot_detail_delta(_detail_delta_list1, _detail_delta_list2, savefig='%s-node-time.png'%_prefix)


def ospf():
    num1, delta1, send_stat1, recv_stat1, detail_delta_list1 = load_data('/home/yutao/tmp/flood-ospf1.log')
    num2, delta2, send_stat2, recv_stat2, detail_delta_list2 = load_data('/home/yutao/tmp/pp-ospf1.log')

    plot1(num1, delta1, num2, delta2, savefig='ospf-path-time.png')

    base = 1024*1024.0
    send_pkts1 = [(i[1]+i[3]+i[5]) / base for i in send_stat1]
    send_pkts2 = [(i[1]+i[3]+i[5]) / base for i in send_stat2]
    plot1(num1, send_pkts1, num2, send_pkts2, yl='Send message size (MB)', title='Send message size', savefig='ospf-path-send-msg.png')

    recv_pkts1 = [(i[1]+i[3]+i[5]) / base for i in recv_stat1]
    recv_pkts2 = [(i[1]+i[3]+i[5]) / base for i in recv_stat2]
    plot1(num1, recv_pkts1, num2, recv_pkts2, yl = 'Received message size (MB)', title='Received message size', savefig='ospf-path-recv-msg.png')

    _detail_delta_list1 = detail_delta_list1[0:10]
    _detail_delta_list2 = detail_delta_list2[0:10]
    plot_detail_delta(_detail_delta_list1, _detail_delta_list2, savefig= 'ospf-path-node-time.png')


if __name__=='__main__':
    # plt.boxplot([[1,2,3,4], [1,2,3,4]], positions=[1,3], widths=0.5, patch_artist=True)
    # plt.boxplot([[1, 2, 3, 6], [1, 3, 3]],positions=[1.5,3.5], widths=0.5, patch_artist=True)
    # plt.xlim(0,50)
    # plt.show()
    singlepath('5-8')
    singlepath('15-18')
    singlepath('25-28')
    ospf()
    # ospf()

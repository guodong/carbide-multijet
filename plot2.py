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
    changed_delta = []

    send_statistics_map = [defaultdict(lambda: 0) for i in range(6)]
    recv_statistics_map = [defaultdict(lambda: 0) for i in range(6)]

    for item in data:
        delta.append(float(item['delta']))
        changed_delta.append(float(item['last_changed_delta_t']))
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

    # print(send_stats)
    # print(recv_stats)
    # for i in range(len(send_stats)):
    #     print(float(recv_stats[i][4])/send_stats[i][4])
    #     print(float(recv_stats[i][5]) / send_stats[i][5])
    return num, delta, changed_delta, send_stats, recv_stats, detail_delta_list

DATADIR = 'data.log/'

OUTPUTDIR = 'output.log/'

GLOBAL_SAVEFIG = True

GLOBAL_SHOW = False


def plot1(xx1, yy1, xx2, yy2, xl='Update sequence number',
          yl='Time (s)',
          title = 'time delta1 of network',
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
        plt.savefig(OUTPUTDIR + savefig, bbox_inches='tight')

    if GLOBAL_SHOW:
        plt.show()


def plot_detail_delta(detail_delta_list1, detail_delta_list2, xl='Update sequence number',
          yl='Time (s)',
          title = 'time delta1 of each node',
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
        plt.savefig(OUTPUTDIR + savefig, bbox_inches='tight')

    plt.grid()

    if GLOBAL_SHOW:
        plt.show()


def plot_flood_add_pp(data1, data2, prefix):
    num1, delta1, changed_delta1, send_stat1, recv_stat1, detail_delta_list1 = data1
    num2, delta2, changed_delta2, send_stat2, recv_stat2, detail_delta_list2 = data2

    plot1(num1, delta1, num2, delta2, savefig=prefix + '-time.png')

    plot1(num1, changed_delta1, num2, changed_delta2, title='time delta2', savefig=prefix + '-real-time.png')

    base = 1024 * 1024.0
    send_pkts1 = [(i[1] + i[3] + i[5]) / base for i in send_stat1]
    send_pkts2 = [(i[1] + i[3] + i[5]) / base for i in send_stat2]
    plot1(num1, send_pkts1, num2, send_pkts2, yl='Send message size (MB)', title='Send message size',
          savefig=prefix + '-send-msg-size.png')

    recv_pkts1 = [(i[1] + i[3] + i[5]) / base for i in recv_stat1]
    recv_pkts2 = [(i[1] + i[3] + i[5]) / base for i in recv_stat2]
    plot1(num1, recv_pkts1, num2, recv_pkts2, yl='Received message size (MB)', title='Received message size',
          savefig=prefix + '-recv-msg-size.png')

    _detail_delta_list1 = detail_delta_list1[0:10]
    _detail_delta_list2 = detail_delta_list2[0:10]
    plot_detail_delta(_detail_delta_list1, _detail_delta_list2,
                      savefig=prefix + '-node-time.png')


def ospf(flood_file='flood-ospf1.log', pp_file='pp-ospf1.log', prefix='ospf1-update-one-subnet'):
    data1 = load_data(DATADIR+flood_file)
    data2 = load_data(DATADIR+pp_file)
    plot_flood_add_pp(data1, data2, prefix=prefix)


def singlepath(suffix='5-8'):
    data1 = load_data(DATADIR + 'flood-node-%s.log' % suffix)
    data2 = load_data(DATADIR + 'pp-node-%s.log' % suffix)
    prefix = 'single-path-%s-' % suffix
    type = ('install-path', 'delete', 'add')
    for i in range(3):
        _prefix = prefix + type[i]

        _data1 = [item[i::3] for item in data1]
        _data2 = [item[i::3] for item in data2]
        plot_flood_add_pp(_data1, _data2, prefix=_prefix)


if __name__=='__main__':
    # plt.boxplot([[1,2,3,4], [1,2,3,4]], positions=[1,3], widths=0.5, patch_artist=True)
    # plt.boxplot([[1, 2, 3, 6], [1, 3, 3]],positions=[1.5,3.5], widths=0.5, patch_artist=True)
    # plt.xlim(0,50)
    # plt.show()
    # singlepath('5-8')
    # singlepath('15-18')
    # singlepath('25-28')
    # ospf()
    # ospf()
    singlepath('4sw-3hop')

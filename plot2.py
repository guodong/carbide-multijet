import json

from collections import defaultdict

from matplotlib import pyplot as plt


def load_data(path):
    with open(path) as f:
        data = json.load(f)

    delta = []
    num = []
    send_stats = []
    recv_stats = []
    detail_delta_list = []
    changed_delta = []

    send_statistics_map = [defaultdict(lambda: 0) for i in range(6)]
    recv_statistics_map = [defaultdict(lambda: 0) for i in range(6)]

    for item in data:
        delta.append(float(item['delta']))
        a = item['last_changed_delta_t']
        if a is not None:
            changed_delta.append(float(a))
        else:
            changed_delta.append(0)  # TODO
            print('abnormal changed_delta')
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

            detail_delta[n] = detail['delta']

        send_stats.append(send_delta_stats)
        recv_stats.append(recv_delta_stats)
        detail_delta_list.append(detail_delta)

    # print(send_stats)
    # print(recv_stats)
    # for i in range(len(send_stats)):
    #     print(float(recv_stats[i][4])/send_stats[i][4])
    #     print(float(recv_stats[i][5]) / send_stats[i][5])
    return num, delta, changed_delta, send_stats, recv_stats, detail_delta_list


DATADIR = 'data3.log/'

OUTPUTDIR = 'output.log/'

GLOBAL_SAVEFIG = True

GLOBAL_SHOW = False


def plot1(xx1, yy1, xx2, yy2, xl='Update sequence number',
          yl='Time (s)',
          title='time delta1 of network',
          savefig=None):
    if len(yy1) != len(yy2):
        return
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
                      title='time delta1 of each node',
                      savefig=None):
    assert len(detail_delta_list1) == len(detail_delta_list2)

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
    data1 = load_data(DATADIR + flood_file)
    data2 = load_data(DATADIR + pp_file)
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


def bbox_plot(d1, d2, xl='Path hops number',
              yl='Time (s)',
              title='time_delta1 of each node',
              savefig=None,
              xticks=None):
    plt.clf()
    xlen = len(d1)
    assert len(d2) == xlen

    widths = 0.3
    p1 = [i + 1 - widths / 2 for i in range(xlen)]
    p2 = [i + 1 + widths / 2 for i in range(xlen)]
    plt.boxplot(d1, positions=p1, widths=widths, boxprops=dict(color="blue"), meanprops=dict(color='blue'), showfliers=False)
    plt.boxplot(d2, positions=p2, widths=widths, boxprops=dict(color="red"), meanprops=dict(color='red'), showfliers=False)
    if xticks is not None:
        assert len(xticks) == xlen
    else:
        xticks = [i + 1 for i in range(xlen)]
    plt.xticks([i + 1 for i in range(xlen)], xticks)

    if xl:
        plt.xlabel(xl)
    if yl:
        plt.ylabel(yl)
    if title:
        plt.title(title)

    plt.gca().set_ylim(bottom=0)
    plt.grid()

    if GLOBAL_SAVEFIG and savefig:
        plt.savefig(OUTPUTDIR + savefig, bbox_inches='tight')

    if GLOBAL_SHOW:
        plt.show()


def subfunc(data1, data2, prefix="", xticks=None, title_types=None):
    group_num = len(data1)
    assert group_num == len(data2)

    prefix2_l = ("time1", "time2")
    titles = ('Events-start-finish interval', 'ECS-stabilized interval')
    item_indexes = (1, 2)
    for i in range(len(item_indexes)):  # delta changed_delta
        item_index = item_indexes[i]
        d1 = [group[item_index] for group in data1]
        d2 = [group[item_index] for group in data2]
        bbox_plot(d1, d2, title=titles[i] + " ("+title_types+")", savefig=prefix + '-' + prefix2_l[i] + '.png', xticks=xticks)

    base = 1024.0
    d1 = [[(stat[1]+stat[3]+stat[5])/base for stat in group[3]] for group in data1]
    d2 = [[(stat[1]+stat[3]+stat[5])/base for stat in group[3]] for group in data2]

    bbox_plot(d1, d2, title="Total send message size"+ " ("+title_types+")", savefig=prefix + '-send-msg-size.png',
         xticks=xticks, yl="Size (KB)")

    r1 = [[(stat[1]+stat[3]+stat[5])/base for stat in group[4]] for group in data1]
    r2 = [[(stat[1]+stat[3]+stat[5])/base for stat in group[4]] for group in data2]
    bbox_plot(r1, r2, title="Total received message size"+ " ("+title_types+")", savefig=prefix + '-recv-msg-size.png',
         xticks=xticks, yl="Size (KB)")

    rt1 = [[float(a[0]) / a[1] for a in zip(r1[i], d1[i])] for i in range(len(d1))]
    rt2 = [[float(a[0]) / a[1] for a in zip(r2[i], d2[i])] for i in range(len(d2))]
    bbox_plot(rt1, rt2, title="Total received message size / total send message size" + " (" + title_types + ")",
              savefig=prefix + '-msg-size-ratio.png',
              xticks=xticks, yl=None)


def plot_flood_and_pp_average():
    d1 = [[], [], []]
    d2 = [[], [], []]

    xrange = list(range(3,19,1))

    for i in xrange:
        # num, delta, changed_delta, send_stats, recv_stats, detail_delta_list
        data1 = load_data(DATADIR + 'flood-node-10-32-%d.log' % i)
        data2 = load_data(DATADIR + 'pp-node-10-32-%d.log' % i)
        for i in range(3):
            _data1 = [item[i::3] for item in data1]
            _data2 = [item[i::3] for item in data2]
            d1[i].append(_data1)
            d2[i].append(_data2)

    xticks = [i for i in xrange]
    prefix = ('install', 'delete', 'add')
    title_types_l = ('install path', 'delete last hop', 'add last hop')
    for i in range(3):
        subfunc(d1[i], d2[i], prefix='result-10-32-' + prefix[i], xticks=xticks, title_types=title_types_l[i])


if __name__ == '__main__':
    # plt.boxplot([[1,2,3,4], [1,2,3,4]], positions=[1,3], widths=0.5, patch_artist=True)
    # plt.boxplot([[1, 2, 3, 6], [1, 3, 3]],positions=[1.5,3.5], widths=0.5, patch_artist=True)
    # plt.xlim(0,50)
    # plt.show()
    # singlepath('5-8')
    # singlepath('15-18')
    # singlepath('25-28')
    # ospf()
    # ospf()
    # singlepath('10-31-3')
    plot_flood_and_pp_average()

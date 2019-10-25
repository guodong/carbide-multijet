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

    send_statistics_map = [defaultdict(lambda: 0) for i in range(6)]
    recv_statistics_map = [defaultdict(lambda: 0) for i in range(6)]

    for item in data:
        delta.append(float(item['delta']))
        num.append(int(item['num']))

        send_delta_stats = [0] * 6
        recv_delta_stats = [0] * 6

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

        send_stats.append(send_delta_stats)
        recv_stats.append(recv_delta_stats)

    return num, delta, send_stats, recv_stats


def plot1(xx1, yy1, xx2, yy2, xl='Update sequence number',
          yl='Convergence time (s)',
          title = 'Convergence time of network',
          savefig = None):
    plt.grid()
    plt.plot(xx1, yy1, 'r', label='Flood')
    plt.plot(xx2, yy2, 'b', label='PushPullNeighbor')
    plt.legend()
    if xl:
        plt.xlabel(xl)
    if yl:
        plt.ylabel(yl)
    if title:
        plt.title(title)

    if savefig:
        plt.savefig(savefig)

    plt.show()


def singlepath():
    num1, delta1, send_stat1, recv_stat1 = load_data('/home/yutao/tmp/flood-node.log')
    num2, delta2, send_stat2, recv_stat2 = load_data('/home/yutao/tmp/pp-node.log')

    for i in range(3):
        xx1 = num1[i::3]
        yy1 = delta1[i::3]
        xx2 = num2[i::3]
        yy2 = delta2[i::3]
        plot1(xx1, yy1, xx2, yy2)


def ospf():
    num1, delta1, send_stat1, recv_stat1 = load_data('/home/yutao/tmp/flood-ospf1.log')
    num2, delta2, send_stat2, recv_stat2 = load_data('/home/yutao/tmp/pp-ospf1.log')

    plot1(num1, delta1, num2, delta2, savefig='ospf-path-time.png')

    send_pkts1 = [i[1]+i[3]+i[5] for i in send_stat1]
    send_pkts2 = [i[1]+i[3]+i[5] for i in send_stat2]
    plot1(num1, send_pkts1, num2, send_pkts2, yl='Send message size', title='Send message size', savefig='ospf-path-send-msg.png')

    recv_pkts1 = [i[1]+i[3]+i[5] for i in recv_stat1]
    recv_pkts2 = [i[1]+i[3]+i[5] for i in recv_stat2]
    plot1(num1, recv_pkts1, num2, recv_pkts2, yl = 'Received message size', title='Received message size', savefig='ospf-path-recv-msg.png')


if __name__=='__main__':
    singlepath()
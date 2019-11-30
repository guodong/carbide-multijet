import os
import json
import matplotlib.pyplot as plt


from string import Template

line_template = """
set term post eps enhanced
set term post size 12,9
set xlabel 'Time(s)'
set ylabel 'Node'
set output "${output}"
plot "${data_file}" with lines
"""

points_template = """
set term post eps enhanced
set term post size 12,9
set xlabel 'Time(s)'
set ylabel 'Node'
set output "${output}"
plot "${data_file}" with points
"""


line_points_template = """
set term post eps enhanced color
set term post size 12,9
set xlabel 'Time(s)'
set ylabel 'Node'
# set style line 2 lc rgb 'red' pt 1
set xrange [350:352]
set output "${output}"
plot "${line_data}" with lines, "${point_data}" with points pt 13
"""


def main():
    # gnuplot(line_template, output="./gnuplot/figures/tmp.eps",
    #   data_file = "/home/yutao/tmp/output-log-ospf-eval-dumpdata2/dumpdata-multijet-log.dat")
    # gnuplot(line_template, output="./gnuplot/figures/tmp.eps",
    #         data_file="/home/yutao/tmp/output-log-replay-flood-10down-replay2/replay-flood-multijet-log.dat")
    # gnuplot(points_template, output="./gnuplot/figures/tmp.eps",
    #         data_file="/home/yutao/tmp/output-log-replay-flood-10down-replay2/replay-flood-update-point.dat")

    # method = 'flood'
    # suffix = '10down-replay5-1'
    # gnuplot(line_points_template, output="./gnuplot/figures/tmp6.eps",
    #         point_data="/home/yutao/tmp/output-log-replay-%s-%s/replay-%s-update-point.dat" % (method, suffix, method),
    #         line_data="/home/yutao/tmp/output-log-replay-%s-%s/replay-%s-multijet-log.dat" % (method, suffix, method))


    # gnuplot(points_template, output="./gnuplot/figures/tmp-dump-only6.eps",
    #         data_file="/home/yutao/tmp/output-log-ospf-eval-dump-only6/dump-only-update-point.dat")

    method = 'flood'
    suffix = 'dump-only-deltacom'
    gnuplot(line_points_template, output="./gnuplot/figures/tmp-%s-%s.eps" % (method, suffix),
            point_data="/home/yutao/tmp/output-log-replay-%s-%s/replay-%s-update-point.dat" % (method, suffix, method),
            line_data="/home/yutao/tmp/output-log-replay-%s-%s/replay-%s-multijet-log.dat" % (method, suffix, method))
    # gnuplot(points_template, output="./gnuplot/figures/tmp-ospf-%s.eps" % (suffix),
    #          data_file="/home/yutao/tmp/output-log-ospf-eval-%s/dump-only-update-point.dat" % suffix)

def load_data(log_path, fpm_history_path, interval = 60, groups = 100, start_point = 200):
    with open(log_path) as f:
        log = json.load(f)

    with open(fpm_history_path) as f:
        fpm = json.load(f)

    log_mn = min(values[0][0] for node, values in log.items())
    fpm_mn = min(values[0] for node, values in fpm.items())

    bar1 = []
    bar2 = []
    for i in range(start_point - 2, start_point -2 + interval * groups, interval):
        left = i
        right = i+ 10

        mn = float('inf')
        mx = float('-inf')
        for node, values in fpm.items():
            for t in values:
                t-=fpm_mn
                if left<t<right and t<mn:
                    mn = t
                if left<t<right and t>mx:
                    mx = t
        if mn == float('inf'):
            print("missing data between ", left, right)
            bar1.append(None)
            bar2.append(None)
            continue

        print(mx, mn)
        bar2.append(mx-mn)

        mn = float('inf')
        mx = float('-inf')
        for node, values in log.items():
            for s,e,c in values:
                s-=log_mn

                e-=log_mn
                if left<s<right and s<mn:
                    mn = s
                if left<e<right and e>mx and c:
                    mx = e
        print(mx, mn)
        bar1.append(mx-mn)

    print(bar1)
    print(bar2)
    return bar1, bar2


OUTPUT = "ignored/figures2/"


def main2():
    method = 'pp'
    suffix = 'dump-only-172'

    log_path = "/home/yutao/tmp/output-log-replay-%s-%s/replay-%s-multijet-log.json" % (method, suffix, method)
    fpm_history_path = "/home/yutao/tmp/output-log-replay-%s-%s/replay-%s-fpm_history.json" % (method, suffix, method)

    bar1, bar2 = load_data(log_path, fpm_history_path, interval=150, groups=20, start_point=200)

    bar1 = list(a if a is not None else 0 for a in bar1)
    bar2 = list(a if a is not None else 0 for a in bar2)

    # bar1 = list(a for a in bar1 if a is not None)
    # bar2 = list(a for a in bar2 if a is not None)

    # bar1 = bar1[1:]
    # bar2 = bar2[1:]

    x = list(range(1,1 + len(bar1)))

    if method == 'pp':
        plt.title("Carbide with hop-by-hop method")
    else:
        plt.title("Carbide wtih flood method")
    plt.bar(x, bar1, label='Carbide')
    plt.bar(x, bar2, label='OSPF')
    plt.xticks(x, [str(i) for i in x])
    plt.ylabel("time(s)")
    plt.legend()
    # plt.show()
    plt.savefig(OUTPUT + 'result-%s-%s.png' % (method, suffix), bbox_inches='tight')


def gnuplot(template, **kwargs):
    os.environ['PATH'] += ":/home/yutao/App/gnuplot/bin"

    t = Template(template)
    s = t.substitute(kwargs)
    with open('/tmp/tmp.gplt', 'w') as f:
        f.write(s)
    os.system('gnuplot /tmp/tmp.gplt')


if __name__=='__main__':
    main2()
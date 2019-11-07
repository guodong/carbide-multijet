#!/usr/bin/env python
import os
import re
import sys
import json
import argparse


def get_nodes(path='configs'):
    ret = []
    for i in range(0, 400):
        if os.path.exists(path + '/common/fpm-replay-%d.json' % i):
            ret.append(str(i))
    print('get_nodes', len(ret))
    return ret


def get_multijet_log(nodes, path='configs'):
    data = {}

    for node_id in nodes:
        with open(path + '/%s/multijet2.log' % node_id) as f:
            time_pair_list = []
            start = None
            while True:
                l = f.readline()
                if l is None or l == "":
                    break
                if 'handle one message' in l:
                    b = next(re.finditer(' (\d+\.\d+) ', l))
                    t_str = b.groups()[0]
                    t1 = float(t_str)
                    if 'start' in l:
                        assert start is None
                        start = t1
                    elif 'end' in l:
                        assert start is not None
                        if 'no_ecs_change' in l:
                            ecs_changed = False
                        else:
                            ecs_changed = True
                        time_pair_list.append((start, t1, ecs_changed))
                        start = None
            print('len(time_pair_list)=', len(time_pair_list))

            data[node_id] = time_pair_list

    return data


def get_fpm_history(nodes, dir='configs'):
    data = {}
    for node_id in nodes:
        path = dir + "/common/fpm-replay-%s.json" % node_id
        with open(path) as f:
            history = json.load(f)
        time_list = []
        for item in history:
            if str(item['type']) == 'replay_update':
                t1 = float(item['time'])
                time_list.append(t1)
        print(path, 'get_fpm_history length=', len(time_list))
        data[node_id] = time_list

    return data


def get_eval3_link_test_history(path='1.json'):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        history = json.load(f)

    data = []
    for item in history:
        data.append((item['pair'], str(item['op']), float(item['time'])))

    return data


def dump_data2(path='configs', history_file='', output='/tmp/output', prefix='data-flood', suffix=''):
    if not os.path.exists(output):
        os.system('mkdir -p ' + args.output)

    nodes = get_nodes(path)

    multijet_log = get_multijet_log(nodes, path)  # node_id :  [(start, end, ecs_changed)]
    multijet_log_start_min = min(l[0][0] for l in multijet_log.values())

    fpm_history = get_fpm_history(nodes, path)  # node_id : [update_times]

    time_min = min(l[0] for l in fpm_history.values())

    time_min = min(time_min, multijet_log_start_min)

    with open('%s/%s-multijet-log.dat' % (output, prefix), 'w') as f:
        y = 0
        for node_id in nodes:
            y += 1
            for start, end, ecs_changed in multijet_log[node_id]:
                f.write("%f %f\n" % (start - time_min, y))
                f.write("%f %f\n\n" % (end - time_min, y))

    with open('%s/%s-update-point.dat' % (output, prefix), 'w') as f:
        y = 0
        for node_id in nodes:
            y += 1
            for t in fpm_history[node_id]:
                f.write("%f %f\n" % (t - time_min, y))

    # test_history = get_eval3_link_test_history(history_file)  # [(pair, op, time)]
    # if test_history:
    #     line_x = [a[2] - time_min for a in test_history]
    #     with open('%s/%s-test-line.dat' % (output, prefix), 'w') as f:
    #         for x in line_x:
    #             f.write("%f %f\n" % (x, 0))
    #             f.write("%f %f\n\n" % (x, len(nodes) + 4))

    with open('%s/%s-multijet-log.json' % (output, prefix), 'w') as f:
        json.dump(multijet_log, f)

    with open('%s/%s-fpm_history.json' % (output, prefix), 'w') as f:
        json.dump(fpm_history, f)

    # with open('%s/%s-test_history.json' % (output, prefix), 'w') as f:
    #     json.dump(test_history, f)

    print('time_min', time_min)


def dump_data(path='configs', begin=200, interval=30):
    data = {}

    for i in range(100, 400):
        print(i)
        if not os.path.exists(path + '/%d' % i):
            continue

        time_list = []
        start = end = None
        last_t = None

        with open(path + '/%d/multijet2.log' % i) as f:
            while True:
                l = f.readline()
                if l is None or l == "":
                    break
                msg = None
                if 'handle one message' in l:
                    msg = 'event'
                elif 'install' in l:
                    msg = 'install'
                if msg:
                    b = next(re.finditer(' (\d+\.\d+) ', l))
                    t_str = b.groups()[0]
                    t1 = float(t_str)
                    if start is None:
                        start = t1
                    if last_t is not None:
                        if t1 - last_t > 2:
                            end = last_t
                            time_list.append((start, end))
                            start = t1
                    last_t = t1
            time_list.append((start, last_t))
            print('len(time_list)=', len(time_list))

        data[i] = time_list

    time_min = min(time_list[0][0] for time_list in data.values())
    time_max = max(time_list[-1][1] for time_list in data.values())

    wf = open('/tmp/data.txt', 'w')

    dump_line(wf, begin, interval, time_max - time_min)

    y = 0

    for i in range(100, 400):
        if i not in data:
            continue
        y += 1
        time_list = data[i]
        wf1 = open('/tmp/data-%d-%d' % (y, i), 'w')
        for start, end in time_list:
            wf.write("%f %f\n" % (start - time_min, y))
            wf.write("%f %f\n\n" % (end - time_min, y))
            wf1.write("%f %f\n" % (start - time_min, end - time_min))
        wf1.close()

    wf.close()


def dump_fpm_history(dir='configs', begin=200, interval=30):
    data = {}
    for i in range(100, 400):
        path = dir + "/common/fpm-history-%d.json" % i
        if not os.path.exists(path):
            continue

        with open(path) as f:
            history = json.load(f)

        time_list = []
        for item in history:
            if str(item['type']) == 'request_update':
                t1 = float(item['time'])
                time_list.append(t1)
        data[i] = time_list

    time_min = min(item[0] for item in data.values())
    time_max = max(item[-1] for item in data.values())

    with open('/tmp/data-fpm-line', 'w') as f:
        dump_line(f, begin, interval, time_max - time_min)

    wf = open('/tmp/data-fpm', 'w')

    y = 0
    for i in range(100, 400):
        if not i in data:
            continue
        print(i)

        y += 1
        for t in data[i]:
            wf.write("%f %f\n" % (t - time_min, y))

    wf.close()


def dump_line(f, begin, interval, total_time, y1=0, y2=180):
    while begin < total_time:
        f.write("%f %f\n" % (begin, y1))
        f.write("%f %f\n\n" % (begin, y2))
        begin += interval


def test(ttt='flood'):
    with open('/home/yutao/tmp/output2/data-%s-multijet-log.json'%ttt) as f:
        multijet_log = json.load(f)  # node_id :  [(start, end, ecs_changed)]
    multijet_log_start_min = min(l[0][0] for l in multijet_log.values())

    with open('/home/yutao/tmp/output2/data-%s-fpm_history.json' % ttt) as f:
        fpm_history = json.load(f)  # node_id : [update_times]

    time_min = min(l[0] for l in fpm_history.values())

    time_min = min(time_min, multijet_log_start_min)

    print(time_min)

    dd = {node_id: [(s-time_min, e-time_min, c) for s,e,c in tl]  for node_id,tl in multijet_log.items()}

    right_bound = [190]
    right = 190
    for i in range(10):
        right += 50
        right_bound.append(right)
        right += 40
        right_bound.append(right)
        right += 90
        right_bound.append(right)

    tmp_output = '/home/yutao/tmp/output2/tmp1'

    start=0

    time1_list = []
    time2_list = []

    for right in right_bound:
        ddd = {node_id: [t for t in tl if start<=t[0]<=right]  for node_id,tl in dd.items()}

        t1 = float('inf')
        t2 = float('-inf')
        t3 = None
        for tl in ddd.values():
            if len(tl)==0:
                continue
            if tl[0][0]<t1:
                t1 = tl[0][0]
            if tl[-1][1]>t2:
                t2 = tl[-1][1]
            for s,e,c in tl[::-1]:
                if c:
                    if t3 is None:
                        t3=e
                    elif t3<e:
                        t3=e
        time1_list.append(t2-t1)
        time2_list.append(t3-t1)


        start = right

        f= open('%s/log-changed-%d.dat' % (tmp_output, right), 'w')
        fc = open('%s/log-no-changed-%d.dat' % (tmp_output, right), 'w')

        y=0

        for i in range(400):
            if str(i) not in ddd:
                continue

            y+=1

            tl = ddd[str(i)]

            for s,e,c in tl:
                if c:
                    f.write("%f %f\n"%(s,y))
                    f.write("%f %f\n\n" % (e, y))
                else:
                    fc.write("%f %f\n"%(s,y))
                    fc.write("%f %f\n\n" % (e, y))

        f.close()
        fc.close()

    print(time1_list)
    print(time2_list)

    with open("%s/time_list"%(tmp_output), 'w') as f:
        json.dump({"t1l": time1_list, "t2l":time2_list}, f)




if __name__ == '__main__':

    # test('pp')
    # exit(0)

    parser = argparse.ArgumentParser(description="dump data")
    # parser.add_argument("-t", "--begin", type=int, default=200)
    # parser.add_argument("-i", "--interval", type=int, default=90)
    parser.add_argument("-o", "--output", type=str, default='/tmp/output')
    parser.add_argument("-s", "--suffix", type=str, default='')
    parser.add_argument("-p", "--prefix", type=str)
    parser.add_argument("-f", "--history", type=str)
    parser.add_argument("dir", type=str, help="data directory")
    args = parser.parse_args()

    dump_data2(args.dir, args.history, args.output, args.prefix, args.suffix)

    # dump_data(args.dir, args.begin, args.interval)
    # dump_fpm_history(args.dir, args.begin, args.interval)

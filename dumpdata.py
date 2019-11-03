#!/usr/bin/env python
import os
import re
import sys
import json
import argparse


def dump_data(path='configs',  begin=200, interval=30):
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

    dump_line(wf, begin, interval, time_max-time_min)

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
            wf1.write("%f %f\n"%(start-time_min, end-time_min))
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
            if str(item['type'])=='request_update':
                t1 = float(item['time'])
                time_list.append(t1)
        data[i]=time_list

    time_min = min(item[0] for item in data.values())
    time_max = max(item[-1] for item in data.values())

    with open('/tmp/data-fpm-line', 'w') as f:
        dump_line(f, begin, interval, time_max-time_min)

    wf = open('/tmp/data-fpm', 'w')

    y = 0
    for i in range(100, 400):
        if not i in data:
            continue
        print(i)

        y+=1
        for t in data[i]:
            wf.write("%f %f\n"%(t-time_min, y))

    wf.close()


def dump_line(f, begin, interval, total_time, y1=0, y2=180):
    while begin < total_time:
        f.write("%f %f\n"% (begin, y1))
        f.write("%f %f\n\n" % (begin, y2))
        begin += interval


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="dump data")
    parser.add_argument("-t", "--begin", type=int, default=200)
    parser.add_argument("-i", "--interval", type=int, default=30)
    parser.add_argument("dir", type=str, help="data directory")
    args = parser.parse_args()

    dump_data(args.dir, args.begin, args.interval)
    dump_fpm_history(args.dir, args.begin, args.interval)

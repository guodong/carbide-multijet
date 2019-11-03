import os
import re


def dump_data():
    data = {}

    for i in range(100, 400):
        print(i)
        if not os.path.exists('configs/%d'%i):
            continue

        time_list = []
        start = end = None
        last_t = None

        with open('configs/%d/multijet2.log'%i) as f:
            while True:
                l = f.readline()
                if l is None or l=="":
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
            print(time_list)

        data[i]=time_list

    g_start = min(time_list[0][0] for time_list in data.values())

    wf = open('/tmp/data.txt', 'w')

    for i in range(40):
        wf.write("%f %f\n" % (200 + i * 20, 0))
        wf.write("%f %f\n\n" % (200 + i * 20, 180))

    y=0

    for i in range(100, 400):
        if i not in data:
            continue
        y+=1
        time_list = data[i]
        for start,end in time_list:
            wf.write("%f %f\n" % (start-g_start, y))
            wf.write("%f %f\n\n" % (end - g_start, y))

    wf.close()


if __name__=='__main__':
    dump_data()
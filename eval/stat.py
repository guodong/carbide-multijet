import os, json
import numpy as np
import matplotlib.pyplot as plt


def total_time():
    min = 2548526188.642613
    max = 0
    min_id = 0
    max_id = 0
    for root, dirs, files in os.walk('results/configs'):
        for name in dirs:
            with open('results/configs/' + name + '/multijetlog', 'r') as f:
                first_line = f.readline()
                start = first_line.split()[1]

                for line in f:
                    if 'update' not in line:
                        pass
                last_line = line
                end = last_line.split()[1]

                # print name, start, end

                if float(start) < min:
                    min = float(start)
                    min_id = name

                if float(end) > max:
                    max = float(end)
                    max_id = name
    print min_id, max_id
    print min, max, max - min


def time_ec_count():
    time = []
    counts = []
    for root, dirs, files in os.walk('results/configs'):
        for name in dirs:
            with open('results/configs/' + name + '/multijetlog', 'r') as f:
                for line in f:
                    if 'updated' in line:
                        break
                    if 'count' in line:
                        time.append(float(line.split()[1]))
                        counts.append(int(line.split()[-1]))

    print len(time)
    mint = min(time)
    for i in range(len(time)):
        time[i] = time[i] - mint

    plt.scatter(time, counts, s=0.5, c='k', marker='x')
    plt.axis()
    plt.xlabel('time')
    plt.ylabel('EC Count')
    plt.savefig('eval/count1.png')
    print max(time) - min(time)


def ec_cdf():
    counts = []
    for root, dirs, files in os.walk('results/configs'):
        for name in dirs:
            with open('results/configs/' + name + '/multijetlog', 'r') as f:
                for line in f:
                    if 'updated' in line:
                        break
                    if 'count' in line:
                        counts.append(int(line.split()[-1]))

    fig, ax = plt.subplots(figsize=(8, 4))
    n, bins, patches = ax.hist(counts, 500, density=True, histtype='step',
                               cumulative=True, label='Empirical')

    plt.savefig('eval/ec-count-cdf.png')
    print max(counts), min(counts)


def ec_calc_time():
    durations = []
    timestemps = []
    for root, dirs, files in os.walk('results/configs'):
        for name in dirs:
            with open('results/configs/' + name + '/multijetlog', 'r') as f:
                start = 0
                for line in f:
                    if 'updated' in line:
                        break
                    if 'received' in line:
                        start = float(line.split()[1])
                    if 'ecs of' in line:
                        end = float(line.split()[1])
                        duration = end - start
                        durations.append(duration)
                        timestemps.append(start)
    mint = min(timestemps)
    for i in range(len(timestemps)):
        timestemps[i] = timestemps[i] - mint

    plt.scatter(timestemps, durations, s=0.5, c='k', marker='x')
    plt.axis()
    plt.xlabel('time')
    plt.ylabel('EC calculation time')
    plt.savefig('eval/ec-calc-time.png')


def ec_calc_time_cdf():
    durations = []
    for root, dirs, files in os.walk('results/configs'):
        for name in dirs:
            with open('results/configs/' + name + '/multijetlog', 'r') as f:
                start = 0
                for line in f:
                    if 'updated' in line:
                        break
                    if 'received' in line:
                        start = float(line.split()[1])
                    if 'ecs of' in line:
                        end = float(line.split()[1])
                        duration = end - start
                        durations.append(duration)

    fig, ax = plt.subplots(figsize=(8, 4))
    n, bins, patches = ax.hist(durations, 500, density=True, histtype='step',
                               cumulative=True, label='Empirical')

    plt.savefig('eval/ec-calc-time-cdf.png')
    print max(durations), min(durations)


def ec_update_time_calc_cdf():
    durations = []
    timestemps = []
    for root, dirs, files in os.walk('results/configs'):
        for name in dirs:
            with open('results/configs/' + name + '/multijetlog', 'r') as f:
                start = 0
                for line in f:
                    if 'flood finished' in line:
                        start = float(line.split()[1])
                    if 'updated' in line:
                        end = float(line.split()[1])
                        duration = (end - start) * 1000
                        durations.append(duration)
                        timestemps.append(start)

    fig, ax = plt.subplots(figsize=(8, 4))
    n, bins, patches = ax.hist(durations, 500, density=True, histtype='step',
                               cumulative=True, label='Empirical')

    plt.savefig('eval/ec-update-calc-time-cdf.png')
    print max(durations), min(durations)


def ec_update_time_cdf():
    start_time = 0
    durations = []
    with open('results/configs/201/multijetlog', 'r') as f:
        for line in f:
            if 'update_request' in line:

                start_time = float(line.split()[1])
                break
    start_time = 1548526306.879711 - 0.062508
    for root, dirs, files in os.walk('results/configs'):
        for name in dirs:
            with open('results/configs/' + name + '/multijetlog', 'r') as f:
                final_update_time = start_time

                for line in f:
                    if 'update' in line:
                        final_update_time = float(line.split()[1])
                        break
                    else:
                        pass
                for line in f:
                    pass
                last_line = line
                if final_update_time == start_time:
                    final_update_time = float(last_line.split()[1])
                duration = final_update_time - start_time
                durations.append(duration)

    fig, ax = plt.subplots(figsize=(8, 4))
    n, bins, patches = ax.hist(durations, 500, density=True, histtype='step',
                               cumulative=True, label='Empirical')

    plt.savefig('eval/ec-update-time-cdf.png')
    print max(durations), min(durations)


def test():
    longest = 0
    for root, dirs, files in os.walk('results/configs'):
        for name in dirs:
            with open('results/configs/' + name + '/multijetlog', 'r') as f:
                for line in f:
                    if 'u\'' in line:
                        str = '[' + line.split('[')[1]
                        str = str.replace('u','')
                        if str.count(',') + 1 > longest:
                            longest = str.count(',')
    print longest


if __name__ == '__main__':
    ec_update_time_cdf()

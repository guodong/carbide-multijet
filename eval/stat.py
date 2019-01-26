import os
import sys


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



if __name__ == '__main__':
    total_time()
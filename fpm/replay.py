#!/usr/bin/python
import socket
import struct
import os
import time
import logging
import platform
import json
import requests
import sys


def get_compress_time(start, t):
    a = t-start
    return a
    # if a < 190:
    #     return a
    #
    # m = int((a-190)/90.0)
    # n = 0 if 200+m*90+20 > a else 1
    #
    # return a - 70*m - n*40


def get_relative_time(relative, start, t):
    return relative+get_compress_time(start, t)


def main(relative_time):
    node_id = str(platform.node())
    with open('/common/replay/fpm-history-%s.json'%node_id) as f:
        history = json.load(f)

    replay_history = []

    g_start = 1572856762.222697
    for item in history:

        t1 = get_relative_time(relative_time, g_start, item['time'])

        while True:
            t = time.time()
            if t+0.00001 >= t1:
                break
            else:
                time.sleep(t1 - t - 0.00001)

        url = 'http://localhost:8080/install'
        diff_flows = item['diff_flows']
        requests.post(url, json=diff_flows)
        replay_history.append({
            'type': 'replay_update',
            'time': t,
            'diff_flows': diff_flows
        })

    with open('/common/replay/fpm-replay-%s.json' % node_id, 'w') as f:
        json.dump(replay_history, f, indent=2)


if __name__=='__main__':
    if len(sys.argv)<2:
        exit(0)
    relative_time = float(sys.argv[1])
    main(relative_time)
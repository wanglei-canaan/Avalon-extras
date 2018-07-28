# coding: utf-8

import os
import time
import json

import config


def get_valid_file():
    path = config.config['data_dir']
    if not os.path.exists(path):
        os.makedirs(path)
    files = os.listdir(path)
    cur_time = int(time.time() + 1)
    for file in files:
        if int(file) + config.config['time_delta'] > cur_time:
            return os.path.join(path, file)
    return os.path.join(path, str(cur_time))


def write_data(data):
    file = open(get_valid_file(), 'a')
    try:
        file.write(json.dumps(data) + '\n')
    except Exception as e:
        print("Exception: %s", repr(e))
    file.close()


def save_data(dna, ver, type, result):
    enter = raw_input("\033[1;33m如果正常请扫码，不正常请直接回车\033[0m")
    if len(enter) == 0:
        return
    data = {'dna': dna, 'qcode': enter, 'ver': ver, 'type': type, 'timestamp': int(time.time()), 'result': result}
    write_data(data)


if __name__ == '__main__':
    while True:
        save_data('123', '8C', 'PMU851', 1)
        time.sleep(2)

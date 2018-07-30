# coding: utf-8

import os
import time
import json

import config

result = {
    'success': 0,
    'burn_failed': -1,
    'burn_light_failed': -2,
    'test_failed': -3,
    'test_light_failed': -4,
}


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


def save_data(dna, qcode, chip, ver, type, result):
    data = {'dna': dna, 'qcode': qcode, 'chip': chip, 'ver': ver, 'type': type, 'timestamp': int(time.time()), 'result': result}
    write_data(data)


if __name__ == '__main__':
    while True:
        qcode = ''
        while len(qcode) != 13:
            qcode = raw_input("\033[1;33m请扫码\033[0m")
            print(len(qcode))
        save_data('123', qcode, 'mm', '8C', 'PMU851', 1)
        time.sleep(2)

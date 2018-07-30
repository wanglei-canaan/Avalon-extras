# coding: utf-8

import os
import time
import json
import urllib2

import config


def get_valid_files():
    path = config.config['data_dir']
    result = []
    if os.path.exists(path):
        files = os.listdir(path)
        cur_time = int(time.time())
        for file in files:
            if int(file) + config.config['time_delta'] < cur_time:
                result.append(os.path.join(path, file))
    return result


def get_data_from_file(f):
    res = []
    try:
        for line in f.readlines():  # 依次读取每行
            line = line.strip()  # 去掉每行头尾空白
            res.append(json.loads(line))
    except Exception as e:
        print(e)
    return res


def upload():
    files = get_valid_files()
    res = []
    for file in files:
        f = open(file, 'r')
        res.extend(get_data_from_file(f))
        f.close()

    if len(res) > 0:
        jdata = json.dumps(res)  # 对数据进行JSON格式化编码
        print(jdata)
        req = urllib2.Request('{}/api/chip_data'.format(config.config['log_server']), jdata)  # 生成页面请求的完整数据
        req.add_header('Content-Type', 'application/json')
        try:
            urllib2.urlopen(req)  # 发送页面请求
        except urllib2.URLError, e:
            print(e)
        else:
            for file in files:
                os.remove(file)



def check_run():
    res = os.popen('ps aux|grep upload_chip_data').read()
    if 'upload_chip_data.py' in res:
        return
    while True:
        upload()
        time.sleep(config.config['time_delta'])


if __name__ == '__main__':
    check_run()

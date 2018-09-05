# -*- coding: utf-8 -*-
import sys
import os
import tempfile
from datetime import datetime
import subprocess

import ipaddress
import requests

LOG_TS_FORMAT = "%d/%b/%Y:%H:%M:%S"

def load_aws_networks():
    try:
        r = requests.get('https://ip-ranges.amazonaws.com/ip-ranges.json')
    except Exception as e:
        print('Error making https request : {}'.format(e))
        sys.exit(1)
    if r.status_code != 200:
        return []
    return [ipaddress.ip_network(item.get('ip_prefix')) for item in r.json().get('prefixes')]

AWS_NETWORKS = load_aws_networks()

def from_aws(ip):
    is_aws = False
    for nw in AWS_NETWORKS:
        is_aws = is_aws or (ipaddress.ip_address(ip) in nw)
    return is_aws

def _scraped_off_part_not_i_need(origin_log):
    # *.gz と分ける
    cat_cmd = "gzcat" if os.path.splitext(origin_log)[1] == ".gz" else "cat"
    no_bot_no_assets = '| grep "GET /.*/ HTTP" | grep -v -i "bot"'
    i_need_column = '| cut -d " " -f 1,4,14-' #IP, 日時, User-Agentだけ
    tmp_path = tempfile.mkstemp(prefix='eachip', suffix='.log')[1]
    cmd = '{0} {1} {2} {3} > {4}'.format(
        cat_cmd,
        os.path.abspath(origin_log),
        no_bot_no_assets,
        i_need_column,
        tmp_path)
    print (cmd)
    subprocess.call(cmd, shell=True)
    return tmp_path

def open_log():
    if len(sys.argv) < 2:
        return []
    _, fname = tuple(sys.argv)
    return open(_scraped_off_part_not_i_need(fname))

def timedeltas_each_ip(stream):
    hits_each_ips = {}
    for line in stream:
        ip, ts = tuple(line.replace("[", "").split(" ")[0:2])
        # IP毎にtsの配列化を行う
        if ip not in hits_each_ips.keys():
            hits_each_ips[ip] = []
        hits_each_ips[ip].append(datetime.strptime(ts, LOG_TS_FORMAT))
    # IP毎のアクセスタイムスタンプが得られた
    # アクセスの間隔をIP毎に計算
    return [(ip, [end - begin for begin, end in zip(times[:-1], times[1:])])
                for ip, times in hits_each_ips.items()]

def list_of_ips(timedeltas_each_ip):
    for ip, deltas in timedeltas_each_ip:
        delta_seconds = [d.seconds for d in deltas]
        aws = 'AWS' if from_aws(ip) else ''
        if len(delta_seconds) > 5:
            yield ('{0} {1:.1f} {2} {3}'.format(
                ip,
                sum(delta_seconds)/len(delta_seconds),
                len(delta_seconds),
                aws))

def main():
    print ("ip_address | avg interval(sec) | counts | AWS?")
    print ("----------------------------------------------")
    for out in list_of_ips(timedeltas_each_ip(open_log())):
        print(out)

if __name__ == '__main__':
    main()

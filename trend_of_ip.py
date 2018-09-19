# -*- coding: utf-8 -*-
import sys
import os
import tempfile
from datetime import datetime
import subprocess
import statistics

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
    networks = (ipaddress.ip_network(item.get('ip_prefix')) for item in r.json().get('prefixes'))
    net_bin = {}
    for network in networks:
        first_octet, _, _, _ = tuple(str(network).split('.'))
        if not first_octet in net_bin:
            net_bin[first_octet] = []
        net_bin[first_octet].append(network)
    return net_bin

AWS_NETWORKS = load_aws_networks()

def from_aws(ip):
    test_address = ipaddress.ip_address(ip)
    first_octet, _, _, _ = tuple(ip.split('.'))
    if not first_octet in AWS_NETWORKS:
        return False
    for nw in AWS_NETWORKS[first_octet]:
        if (test_address in nw): return True
    return False

def _scraped_off_part_not_i_need(origin_log):
    from_file = ""
    if sys.stdin.isatty():
        decompress = " | gunzip " if os.path.splitext(origin_log)[1] == ".gz" else ""
        from_file = 'cat {0} {1} |'.format(
            os.path.abspath(origin_log),
            decompress)
    
    no_bot_no_assets = 'grep "GET /.*/ HTTP" | grep -v -i "bot"'
    i_need_column = 'cut -d " " -f 1,4,14-' #IP, 日時, User-Agentだけ
    tmp_path = tempfile.mkstemp(prefix='eachip', suffix='.log')[1]
    cmd = '{0} {1} | {2} > {3}'.format(
        from_file,
        no_bot_no_assets,
        i_need_column,
        tmp_path)
    # print (cmd)
    if sys.stdin.isatty():
        subprocess.run(cmd, shell=True)
    else:
        subprocess.run(cmd, stdin=sys.stdin, shell=True)
    
    return tmp_path

def open_log():
    fname = None
    if 1 < len(sys.argv) and sys.stdin.isatty():
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
    return sorted([(ip, [end - begin for begin, end in zip(times[:-1], times[1:])])
                for ip, times in hits_each_ips.items()], key=lambda x: int(len(x[1])))

def list_of_ips(timedeltas_each_ip):
    print (" {:^14} | {:^5} | {:^5} | {:^5} | {:^8} | {:^8} | {:^5} |".format('ipaddr', 'count', 'min', 'max', 'avg', 'mid', 'AWS?'))
    print ("-----------------------------------------------------------------------")
    for ip, deltas in timedeltas_each_ip:
        delta_seconds = [d.seconds for d in deltas]
        if not delta_seconds: continue
        aws = 'AWS' if from_aws(ip) else ''
        yield ('{0:>15} | {5:>5} | {1:>5} | {2:>5} | {3:>8.1f} | {4:>8.1f} | {6:^5} |'.format(
            ip,
            min(delta_seconds), max(delta_seconds),
            statistics.mean(delta_seconds),
            statistics.median(delta_seconds),
            len(delta_seconds),
            aws))

def main():
    for out in list_of_ips(timedeltas_each_ip(open_log())):
        print(out)

if __name__ == '__main__':
    main()

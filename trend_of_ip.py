# -*- coding: utf-8 -*-

import sys
import os, io
import gzip
from datetime import datetime
import re
import time
import statistics
import numpy as np

import ipaddress
import requests

LOG_TS_FORMAT = "%d/%b/%Y:%H:%M:%S"
REGEXP_I_AM_BOT = re.compile('bot', re.I)
REGEXP_GET_DOC = re.compile('GET /.*/ HTTP')

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

def scraped_off(line):
    if not REGEXP_GET_DOC.search(line) or REGEXP_I_AM_BOT.search(line):
        return (None, None)
    #IP, 日時だけ
    ip, _, _, ts = tuple(line.split(" ")[:4])
    ts = ts.replace("[", "")
    return (ip, datetime.strptime(ts, LOG_TS_FORMAT))

class FileTailer(object):
    def __init__(self, file, delay=0.1):
        self.file = file
        self.delay = delay
    def __iter__(self):
        while True:
            where = self.file.tell()
            line = self.file.readline()
            if line and line.endswith('\n'): # only emit full lines
                yield line
            else:                            # for a partial line, pause and back up
                time.sleep(self.delay)       # ...not actually a recommended approach.
                self.file.seek(where)

def open_log(args):
    if 1 < len(sys.argv) and sys.stdin.isatty():
        fname = args.infile
        decompress = (os.path.splitext(fname)[1] == ".gz")
        open_method = gzip.open if decompress else open
        reader = open_method(os.path.abspath(fname), 'rt')
        if args.follow_mode:
            reader = FileTailer(reader)
        return reader

    return sys.stdin

def hits_each_ips(ip, ts, hits_each_ips = {}):
    # IP毎にtsの配列化を行う
    if ip not in hits_each_ips.keys():
        hits_each_ips[ip] = []
    hits_each_ips[ip].append(ts)
    return hits_each_ips

def _timedeltas_each_ip(hits_each_ips):
    # IP毎のアクセスタイムスタンプが得られた
    # アクセスの間隔をIP毎に計算
    return sorted([(ip, [end - begin for begin, end in zip(times[:-1], times[1:])])
                for ip, times in hits_each_ips.items()], key=lambda x: int(len(x[1])))

def _stats_delta_seconds(delta_seconds):
    np_delta_seconds = np.array(delta_seconds)
    return (np.amin(np_delta_seconds), np.amax(np_delta_seconds),
            np.average(np_delta_seconds),
            np.mean(np_delta_seconds),
            len(delta_seconds))

def _count_per_timebox(delta_seconds, timebox = 1):
    same_count, time_count = (0, 0)
    count_per_timebox = []
    for proc_time in delta_seconds:
        time_count += proc_time
        if timebox < time_count:
            count_per_timebox.append(same_count)
            same_count = 0
            time_count = proc_time
        else:
            same_count += 1
    count_per_timebox.append(same_count)
    return count_per_timebox

def summary(hits_each_ips, top = 30):
    for ip, deltas in _timedeltas_each_ip(hits_each_ips)[top*-1:]:
        delta_seconds = [d.seconds for d in deltas]
        if not delta_seconds:
            continue
        aws = 'AWS' if from_aws(ip) else ''
        count_per_timebox = _count_per_timebox(delta_seconds)
        amin, amax, avg, mid, count = _stats_delta_seconds(delta_seconds)
        yield ('{:>15} | {:>5} | {:>5} | {:>5} | {:>5} | {:>8.1f} | {:>8.1f} | {:^5} |'
                   .format(ip, count, max(count_per_timebox), amin, amax, avg, mid, aws))

def _headers():
    return [
        " {:^14} | {:^5} | {:^5} | {:^5} | {:^5} | {:^8} | {:^8} | {:^5} |"
        .format('ipaddr', 'count', 'acc/s', 'min', 'max', 'avg', 'mid', 'AWS?'),
        "-------------------------------------------------------------------------------"
    ]

def report_to_scr(screen, data, header=True, top=30):
    if not screen: return
    if header:
        for idx, header in enumerate(_headers()):
            screen.print_at(header, 0, idx)
    for idx, out in enumerate(summary(data, top)):
        screen.print_at(out, 0, 2+idx)
    screen.refresh()

def report(data):
    print ("\n".join(_headers()))
    for out in summary(data, 0):
        print (out)

from asciimatics.screen import Screen
import argparse

def is_follow_mode():
    return False # ("-f" in sys.argv)

def main(screen, args):
    data = {}
    try:
        for line in open_log(args):
            ip, ts = scraped_off(line.strip())
            if not ip: continue
            data = hits_each_ips(ip, ts, data)
            report_to_scr(screen, data, True)
    except KeyboardInterrupt:
        pass
    finally:
        if screen: screen.close()
        report(data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Display trends by IP address from log file.')
    parser.add_argument('infile', metavar='logfile',
                        help='Log file to be analyzed.')
    parser.add_argument('-f', dest='follow_mode', action='store_const',
                        const=True, default=False,
                        help="Follow mode: like a 'tail -f'")
    args = parser.parse_args()
    if args.follow_mode:
        Screen.wrapper(main, arguments=[args])
    else:
        main(None, args)

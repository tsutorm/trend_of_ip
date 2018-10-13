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
import dns.resolver
import requests

def _gen_netbin(networks):
    net_bin = {}
    for network in networks:
        first_octet, _, _, _ = tuple(str(network).split('.'))
        if not first_octet in net_bin:
            net_bin[first_octet] = []
        net_bin[first_octet].append(network)
    return net_bin

def load_aws_networks():
    try:
        r = requests.get('https://ip-ranges.amazonaws.com/ip-ranges.json')
    except Exception as e:
        print('Error making https request : {}'.format(e))
        sys.exit(1)
    if r.status_code != 200:
        return []
    networks = (ipaddress.ip_network(item.get('ip_prefix')) for item in r.json().get('prefixes'))
    return _gen_netbin(networks)

def load_gcp_network():
    answers = dns.resolver.query('_cloud-netblocks.googleusercontent.com','TXT')
    maindnsrecord = answers[0].to_text()
    includes = [x for x in maindnsrecord.split() if x.startswith("include:")]

    networks = []
    for toprecord in includes:
        subrecords = (dns.resolver.query(toprecord.split(":")[1], "TXT"))[0].to_text()
        subrecords = subrecords.split(" ")
        subrecords = [x for x in subrecords if x.startswith("ip")]
        for ipblocks in subrecords:
            if ipblocks.startswith("ip4"):
                ip4range = ipaddress.ip_network(ipblocks[4:])
                networks.append(ip4range)
            if ipblocks.startswith("ip6"):
                ip6range = ipaddress.ip_network(ipblocks[4:])
    return _gen_netbin(networks)

CLOUD_NETWORKS = {
    'AWS': load_aws_networks(),
    'GCP': load_gcp_network()
    }

def what_cloud_came_from(ip):
    test_address = ipaddress.ip_address(ip)
    first_octet, _, _, _ = tuple(ip.split('.'))
    for where, network in CLOUD_NETWORKS.items():
        if not first_octet in network:
            continue
        for nw in network[first_octet]:
            if (test_address in nw):
                return where
    return ''

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

def isostrptime(raw_ts):
    return datetime(
        int(raw_ts[0:4]),
        int(raw_ts[5:7]),
        int(raw_ts[8:10]),
        int(raw_ts[11:13]),
        int(raw_ts[14:16]),
        int(raw_ts[17:19])
        )

class CLFParser(object):
    DEFAULT_FORMAT= '%h - %u %t  \"%v\" \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"'

    def __init__(self, file, format=None):
        import apache_log_parser
        self.file = self.rough_filter(file)
        if not format:
            # self.format = '%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"'
            self.format = CLFParser.DEFAULT_FORMAT
        else:
            self.format = format
        self.parser = apache_log_parser.make_parser(self.format)

    def __iter__(self):
        for line in self.file:
            data = self.parser(line)
            yield (data['remote_host'], isostrptime(data['time_received_isoformat']), data['request_url'], data['request_header_user_agent'])

    def rough_filter(self, itr):
        pattern = re.compile('GET (/.*) HTTP/1')
        for item in itr:
            m = pattern.search(item)
            if m:
                url, = m.groups()
                path, ext = os.path.splitext(url)
                if ext or 'bot' in item.lower():
                    continue
            yield item

class LTSVParser(object):
    def __init__(self, file):
        import ltsv
        self.file = file
        self.reader = ltsv.DictReader(self.rough_filter(self.file), ['remote_addr', 'time', 'request_uri', 'useragent'])

    def __iter__(self):
        return ((data['remote_addr'], isostrptime(data['time']), data['request_uri'], data['useragent']) for data in self.reader)

    def rough_filter(self, itr):
        pattern = re.compile('request_method:GET.+?request_uri:(/.+?)\t.+?useragent:(.+?)[\t]')
        for item in itr:
            m = pattern.search(item)
            if m:
                url, ua = m.groups()
                path, ext = os.path.splitext(url)
                if ext or 'bot' in ua.lower():
                    continue
            yield item

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
        cloud = what_cloud_came_from(ip)
        count_per_timebox = _count_per_timebox(delta_seconds)
        amin, amax, avg, mid, count = _stats_delta_seconds(delta_seconds)
        yield ('{:>15} | {:>5} | {:>5} | {:>5} | {:>5} | {:>8.1f} | {:>8.1f} | {:^5} |'
                   .format(ip, count, max(count_per_timebox), amin, amax, avg, mid, cloud))

def _headers():
    return [
        " {:^14} | {:^5} | {:^5} | {:^5} | {:^5} | {:^8} | {:^8} | {:^5} |"
        .format('ipaddr', 'count', 'acc/s', 'min', 'max', 'avg', 'mid', 'cloud'),
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

def gen_parser(args):
    if args.use_ltsv:
        return LTSVParser(open_log(args))
    return CLFParser(open_log(args), args.clf_format)

def main(screen, args):
    data = {}
    try:
        for ip, ts, url, ua in gen_parser(args):
            if os.path.splitext(url)[1] or "bot" in ua.lower():
                continue
            data = hits_each_ips(ip, ts, data)
            report_to_scr(screen, data, True)
    except KeyboardInterrupt:
        pass
    finally:
        if screen: screen.close()
        report(data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Display trends by IP address from log file.')
    parser.add_argument('infile', metavar='logfile', nargs='?',
                        help='Log file to be analyzed.')
    parser.add_argument('-f', dest='follow_mode', action='store_const',
                        const=True, default=False,
                        help="Follow mode: like a 'tail -f'")
    parser.add_argument('--clf', '-c', dest='clf_format', nargs='?',
                        const=CLFParser.DEFAULT_FORMAT, default=None,
                        help="use CLF parser")
    parser.add_argument('--ltsv', '-l', dest='use_ltsv', action='store_const',
                        const=True, default=False,
                        help="use LTSV parser")
    args = parser.parse_args()
    if args.follow_mode:
        Screen.wrapper(main, arguments=[args])
    else:
        main(None, args)

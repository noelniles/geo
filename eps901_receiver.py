#! /usr/bin/env python
"""Receive EPS 901 messages over UDP.
"""
import argparse
import pickle
import socket

from eps901 import PointingMsg


def cli():
    ap = argparse.ArgumentParser()
    ap.add_argument('-host', type=str, default='localhost')
    ap.add_argument('-port', type=int, default=10000)
    ap.add_argument('-save', type=str, help="filename for the packet dump")

    return ap.parse_args()


if __name__ == '__main__':
    args = cli()
    host = args.host
    port = args.port
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    addr = (host, port)
    sock.bind(addr)
    print(f'Listening for messages on {addr[0]}:{addr[1]}')

    if args.save:
        fd = open(args.save, 'wb')

    while True:
        data, rxaddr = sock.recvfrom(4096)
        #packet = pickle.loads(data)

        print(f'recieved {len(data)} bytes from {rxaddr}')
        print(data)
        #print(f'id={packet.msg_id}, time={packet.ts}, az={packet.az}, el={packet.el}')

        if args.save:
            fd.write(data)
import time
from ctypes import (Structure, c_uint8, c_uint16, c_uint32, c_int32)
from enum import Enum


class PointingMsg(Structure):
    _pack_ = 1

    _fields_ = [
        ('msg_id', c_uint16),
        ('track_id', c_uint16),
        (   'cmd', c_uint8),
        (    'az', c_uint32),
        (    'el', c_int32),
        ('follow', c_uint8),
        (    'ts', c_uint32),
        ( 'spare', c_uint32)
    ]
    def __repr__(self):
        return f'id: {self.msg_id}\ntrack_id: {self.track_id}\ncmd:{self.cmd}\naz: {self.az}\nel: {self.el}\nfollow; {self.follow}\ntime: {self.ts}'

class HeartbeatMsg(Structure):
    _fields_ = [
        ('following', c_uint8),
        (   'msg_id', c_uint16),
        (    'state', c_uint8),
        (    'bs_az', c_uint32),
        (    'bs_el', c_int32),
        (     'stat', c_uint8),
        (      'lat', c_int32),
        (      'lon', c_int32),
        (      'alt', c_int32),
        (    'spare', c_uint32)
    ]

if __name__ == '__main__':
    pm = PointingMsg(
        follow = 0,
        msg_id = 1,
        cm     = 254,
        az     = 1024,
        el     = 5000,
        tx     = int(time.time())
    )
    print(pm.ts)

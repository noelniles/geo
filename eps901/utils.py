from datetime import datetime


EPS901_MSG_ID = 0x385 # 901 in base 16

def time_since_midnight():
    """Return the time since midnight UTC in milliseconds."""
    now = datetime.utcnow()

    ms = (now.hour * 3.6e6) \
       + (now.minute * 60000) \
       + (now.second * 1000) \
       + (now.microsecond // 1000)

    return ms

def scale(lo, hi, min_measurement, max_measurement, measurement):
    """Scale the measurement to the range [lo, hi]."""
    return int((hi - lo) * (measurement / max_measurement - min_measurement) + min_measurement)
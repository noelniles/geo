"""WGS-84 Ellipsoid"""
import math



a = 6378137.0               # semi-major axis
e2 = 6.6943799901377997e-3  # first eccentricity
a1 = 4.2697672707157535e+4  # a*e2
a2 = 1.8230912546075455e+9  # a1*a1
a3 = 1.4291722289812413e+2  # a1 * e2/2
a4 = 4.5577281365188637e+9  # 2.5 * a2
a5 = 4.2840589930055659e+4  # a1 + a3
a6 = 9.9330562000986220e-1  # 1- e2

def ecef_to_geo(ecef):
    """Convert Earth-Centered Earth-Fixed to lat, lon, alt.

    Argument:
        ecef (list): a 3 elements containing x, y, z in meters
    
    Returns:
        a list containing lat and lon in radians and alt in meters
    """
    geo = [0]*3
    x, y, z = ecef

    zp = abs(z)
    w2 = x*x + y*y
    w  = math.sqrt(w2)
    r2 = w2 + z*z
    r  = math.sqrt(r2)
    geo[1] = math.atan2(y, x)   # Final Longitude
    s2 = z*z / r2
    c2 = w2 / r2
    u = a2 / r
    v = a3 - a4 / r

    if c2 > 0.3:
        s = (zp / r) * (1.0 - s2 * (a5 - u - c2 * v) / r)
        geo[0] = math.asin(s)
        ss = 1.0 - s * s
        s = math.sqrt(ss)
    else:
        c = (w / r) * (1.0 - s2 * (a5 - c2 * v) / r)
        geo[0] = math.acos(c)
        ss = 1.0 - c * c
        s = math.sqrt(ss)

    g = 1.0 - e2 * ss
    rg = a / math.sqrt(g)
    rf = a6 * rg
    u = w - rg * c
    v = zp - rf * s
    f = c * u - s * u
    m = c * v - s * u
    p = m / (rf / g + f)
    geo[0] = geo[0] + p      # Latitude
    geo[2] = f + m * p/2.0   # Altitude

    if z < 0.0:
        geo[0] *= -1.0

    return geo

def geo_to_ecef(geo):
    """Convert lat, lon, alt to ECEF.

    Argument:
        geo (list): 3 elements [lat, lon (rad), alt (m)]
    ecef = [0]*3
    lat, lon, alt = geo
    n = a / math.sqrt(1 - e2 * math.sin(lat) * math.sin(lat))
    ecef[0] = (n + alt) * math.cos(lat) * math.cos(lon)
    ecef[1] = (n + alt) * math.cos(lat) * math.sin(lon)
    ecef[2] = (n * (1 - e2) + alt) * math.sin(lat)

    return ecef
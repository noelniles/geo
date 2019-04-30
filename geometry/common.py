def inside_circle(point, points, radius=5):
    """Return True if point with within radius 
    of any of a list of points.
    """
    index = -1

    for i, p in enumerate(points):
        x, y = point
        a, b = p
        r = 5

        if (x - a)*(x - a) + (y - b)*(y - b) < r*r:
            return i, True
        
    return index, False

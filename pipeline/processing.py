import math

def ndvi(red, nir, scale, offset):
    if not math.isfinite(red) or not math.isfinite(nir) or red <= 0 or nir <= 0:
        return None
    r, n = red * scale + offset, nir * scale + offset
    if r < 0 or n < 0 or n + r <= 0:
        return None
    value = (n-r)/(n+r)
    return value if -1 <= value <= 1 else None

def temperature_c(dn):
    return dn * .00341802 + 149 - 273.15 if math.isfinite(dn) and dn > 0 else None

def clear_landsat(qa, saturation):
    return (int(qa) & 63) == 0 and int(saturation) == 0

def aggregate(values):
    valid = [v for v in values if v is not None and math.isfinite(v)]
    return round(sum(valid)/len(valid), 4) if values and len(valid)/len(values) >= .5 else None

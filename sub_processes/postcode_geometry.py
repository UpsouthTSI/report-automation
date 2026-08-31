import json
import os
import pandas as pd
import shapefile
import numpy as np
from scipy.spatial import KDTree
from shapely.geometry import Point, Polygon
from pyproj import CRS, Transformer


def postcode_coordinates(geodata_file, memory_dir=None, regional_geodata_file=None):
    """
    Get the coordinates for a given postcode.

    Args:
        postcode (str): The postcode to look up.

    Returns:
        tuple or None: A tuple containing the latitude and longitude of the postcode, or None if the postcode is not found.
    """

    df_postcode = pd.DataFrame(columns=['Postcode', 'X', 'Y', 'Region', 'IsRural'])
    if memory_dir:
        memory_file = os.path.join(memory_dir, 'postcode_coordinates.json')
        if os.path.exists(memory_file):
            with open(memory_file, 'r') as f:
                postcode_memory = json.load(f)
            for postcode, values in postcode_memory.items():
                df_postcode.loc[len(df_postcode)] = [postcode, values[0], values[1], values[2], None]
            return df_postcode
    if not geodata_file:
        raise FileNotFoundError(
            'Postcode boundaries are required when no cached postcode coordinates are available. '
            'Select postcode_boundaries.zip or retain postcode_coordinates.json in the memory folder.'
        )
    postcode_memory = {}
    sf = shapefile.Reader(geodata_file)
    for i in range(len(sf.shapes())):
        postcode = sf.record(i)[0]
        coordinates = centroid(sf.shape(i))
        postcode_memory[postcode] = coordinates
        df_postcode.loc[i] = [postcode, coordinates[0], coordinates[1], None, None]

    if regional_geodata_file:
        postcode_region(postcode_memory, regional_geodata_file)
    if memory_dir:
        with open(memory_file, 'w') as f:
            json.dump(postcode_memory, f, indent=4)
    df_postcode = pd.DataFrame(
        [(k, v[0], v[1], v[2] if len(v) > 2 else None, v[3] if len(v) > 3 else None) for k, v in postcode_memory.items()],
        columns=['Postcode', 'X', 'Y', 'Region', 'IsRural']
    )
    return df_postcode

def postcode_region(postcode_memory, regional_geodata_file):
    """
    Get the region for a given postcode.

    Args:
        postcode (str): The postcode to look up.

    Returns:
        str or None: The region of the postcode, or None if the postcode is not found.
    """
    print(f"Getting region for postcodes using {regional_geodata_file}")
    sf = shapefile.Reader(regional_geodata_file)
    print(sf.fields)
    regions = {}
    for i in range(len(sf.shapes())):
        shape = sf.shape(i)
        #need to convert from 
        # Convert from NZTM to WGS84
        nztm_crs = CRS.from_epsg(2193)  # NZTM
        wgs84_crs = CRS.from_epsg(4326)  # WGS84
        transformer = Transformer.from_crs(nztm_crs, wgs84_crs, always_xy=True)
        shape_points_wgs84 = [transformer.transform(x, y) for x, y in shape.points]
        region = sf.record(i)[1]
        regions[region] = Polygon(shape_points_wgs84)
    print(regions)

    for keys, point in postcode_memory.items():
        for key in regions.keys():
            if regions[key].contains(Point(point)):
                region = key
                print(f"Postcode {keys} is in region {region}")
                postcode_memory[keys] = (point[0], point[1], region)
                break

    points_not_in_region = [keys for keys, point in postcode_memory.items() if len(point) == 2]

    if len(points_not_in_region) > 0:
        print(f"Postcodes not in any region: {points_not_in_region}")
        print(f"These postcodes will be assigned to the region of the nearest postcode")
        tree = KDTree([postcode_memory[key][:2] for key in postcode_memory if len(postcode_memory[key]) == 3])
        for postcode in points_not_in_region:
            point = postcode_memory[postcode][:2]
            _, index = tree.query(point)
            nearest_postcode = [key for key in postcode_memory if len(postcode_memory[key]) == 3][index]
            region = postcode_memory[nearest_postcode][2]
            print(f"Assigning postcode {postcode} to nearest region {region}")
            postcode_memory[postcode] = (point[0], point[1], region)

    return None

def centroid(shape):
    x, y = 0, 0
    vertices = shape.points
    n = len(vertices)
    signed_area = 0
    for i in range(len(vertices)):
        x0, y0 = vertices[i]
        x1, y1 = vertices[(i + 1) % n]
        # shoelace formula
        area = (x0 * y1) - (x1 * y0)
        signed_area += area
        x += (x0 + x1) * area
        y += (y0 + y1) * area
    signed_area *= 0.5
    x /= 6 * signed_area
    y /= 6 * signed_area
    return x, y

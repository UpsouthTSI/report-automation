import json
import os
import pandas as pd
import shapefile
import numpy as np


def postcode_coordinates(geodata_file, memory_dir=None):
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
            for postcode, coordinates in postcode_memory.items():
                df_postcode.loc[len(df_postcode)] = [postcode, coordinates[0], coordinates[1], None, None]
            return df_postcode
    postcode_memory = {}
    sf = shapefile.Reader(geodata_file)
    for i in range(len(sf.shapes())):
        postcode = sf.record(i)[0]
        coordinates = centroid(sf.shape(i))
        postcode_memory[postcode] = coordinates
        df_postcode.loc[i] = [postcode, coordinates[0], coordinates[1], None, None]
    if memory_dir:
        with open(memory_file, 'w') as f:
            json.dump(postcode_memory, f, indent=4)
    df_postcode = pd.DataFrame(list(postcode_memory.items()), columns=['Postcode', 'Coordinates'])
    return df_postcode

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

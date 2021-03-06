#!/usr/bin/env python3

from skyfield import api
from skyfield.api import Loader

import sys
import math
import json 
from collections import defaultdict

from typing import List, Dict, DefaultDict, Set

import s2sphere

import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.io.img_tiles as cimgt
import shapely.geometry
from shapely.geometry import Polygon
import geog
import h3

TLE_URL = 'https://celestrak.com/NORAD/elements/starlink.txt'
R_MEAN = 6378.1 #km
H3_RESOLUTION_LEVEL = 4
process = int(sys.argv[1])

def to_deg(radians: float) -> float:
    return radians * (180 / math.pi)

def to_rads(degrees: float) -> float:
    return degrees * (math.pi / 180)

RIGHT_ANGLE = to_rads(90)

def load_sats() -> List:
    load = Loader('./tle_cache')
    sats = load.tle_file(url=TLE_URL)
    return sats

# Calculates the area of a Starlink satellite using the
# spherical earth model, a satellite (for altitude), and
# minimum terminal angle (elevation angle)
def calcAreaSpherical(altitude: float, term_angle:float) -> float:
    epsilon = to_rads(term_angle)

    eta_FOV = math.asin( (math.sin(epsilon + RIGHT_ANGLE) * R_MEAN) / (R_MEAN + altitude) )

    lambda_FOV = 2 * (math.pi - (epsilon + RIGHT_ANGLE + eta_FOV))

    area = 2 * math.pi * (R_MEAN ** 2) * ( 1 - math.cos(lambda_FOV / 2))

    return area

# Returns the cap angle (lambda_FOV/2) in radians
def calcCapAngle(altitude: float, term_angle: float) -> float:
    epsilon = to_rads(term_angle)

    eta_FOV = math.asin( (math.sin(epsilon + RIGHT_ANGLE) * R_MEAN) / (R_MEAN + altitude) )

    lambda_FOV = 2 * (math.pi - (epsilon + RIGHT_ANGLE + eta_FOV))

    # area = 2 * math.pi * (R_MEAN ** 2) * ( 1 - math.cos(lambda_FOV / 2))

    return (lambda_FOV / 2)

# angle in degrees, is theta (the cap opening angle)
def get_cell_ids(lat, lng, angle):
    region = s2sphere.Cap.from_axis_angle(s2sphere.LatLng.from_degrees(lat, lng).to_point(), s2sphere.Angle.from_radians(angle))
    coverer = s2sphere.RegionCoverer()
    coverer.min_level = 9
    coverer.max_level = 9
    cells = coverer.get_covering(region)
    return cells
    # return sorted([x.id() for x in cells]) 

def plotFootprint(sat):
    angle = calcCapAngle(sat.elevation.km, 35)
    cells = get_cell_ids(sat.latitude.degrees, sat.longitude.degrees, angle)
    print(len(cells))

    proj = cimgt.Stamen('terrain-background')
    plt.figure(figsize=(6,6), dpi=400)
    ax = plt.axes(projection=proj.crs)
    ax.add_image(proj, 6)
    # ax.coastlines()
    ax.set_extent([sat.longitude.degrees-10., sat.longitude.degrees+10.,  sat.latitude.degrees-10,  sat.latitude.degrees+10.], crs=ccrs.Geodetic())
    ax.background_patch.set_visible(False)


    geoms = []
    for cellid in cells:
        new_cell = s2sphere.Cell(cellid)
        vertices = []
        for i in range(0, 4):
            vertex = new_cell.get_vertex(i)
            latlng = s2sphere.LatLng.from_point(vertex)
            vertices.append((latlng.lng().degrees,
                            latlng.lat().degrees))
        geo = Polygon(vertices)
        geoms.append(geo)

    ax.add_geometries(geoms, crs=ccrs.Geodetic(), facecolor='red',
                    edgecolor='black', alpha=0.4)
    ax.plot(sat.longitude.degrees, sat.latitude.degrees, marker='o', color='red', markersize=4,
                alpha=0.7, transform=ccrs.Geodetic())
    plt.savefig('test.png')

def get_cell_ids_h3(lat:float, lng:float, angle: float) -> List: 
    p = shapely.geometry.Point([lng, lat])
    # so to more accurately match projections maybe arc length of a sphere woulde be best?
    arc_length = R_MEAN * angle # in km

    n_points = 20
    #arc_length should be the radius in kilometers so convert to diameter in meters
    d = arc_length * 1000 # meters
    angles = np.linspace(0, 360, n_points)
    polygon = geog.propagate(p, angles, d)
    try:
        mapping = shapely.geometry.mapping(shapely.geometry.Polygon(polygon))
    except ValueError as e:
        print(f"lat:{lat}, lng:{lng}")
        print(polygon)
    

    cells = h3.polyfill(mapping, H3_RESOLUTION_LEVEL, True)
    
    return cells

def plotFootprintH3(sat, h3_cells):
    angle = calcCapAngle(sat.elevation.km, 35)
    # cells = get_cell_ids_h3(sat.latitude.degrees, sat.longitude.degrees, angle)
    # print(len(list(cells)))

    proj = cimgt.Stamen('terrain-background')
    plt.figure(figsize=(6,6), dpi=400)
    ax = plt.axes(projection=proj.crs)
    ax.add_image(proj, 6)
    # ax.coastlines()
    ax.set_extent([sat.longitude.degrees-10., sat.longitude.degrees+10.,  sat.latitude.degrees-10,  sat.latitude.degrees+10.], crs=ccrs.Geodetic())
    ax.background_patch.set_visible(False)


    geoms = []
    for cellid in h3_cells:
        # new_cell = s2sphere.Cell(cellid)
        vertices = []
        bounds = h3.h3_to_geo_boundary(cellid) # arrays of [lat, lng] 
        coords = [[lng, lat] for [lat,lng] in bounds]
        geo = Polygon(coords) 
        geoms.append(geo)

    ax.add_geometries(geoms, crs=ccrs.Geodetic(), facecolor='red',
                    edgecolor='black', alpha=0.4)
    ax.plot(sat.longitude.degrees, sat.latitude.degrees, marker='o', color='red', markersize=4,
                alpha=0.7, transform=ccrs.Geodetic())
    plt.savefig('test_h3.png')

sats = load_sats()
print(f"Loaded {len(sats)} satellites")

ts = api.load.timescale()
now = ts.now()
# print(now)
# now = ts.tt_jd(2459013.763217299)
subpoints = {sat.name : sat.at(now).subpoint() for sat in sats}

sat1 = subpoints['STARLINK-1284']
angle = calcCapAngle(sat1.elevation.km, 35)
# print(f"center: {sat1.latitude.degrees}, {sat1.longitude.degrees} angle: {angle}")
# plotFootprint(sat1)
# plotFootprintH3(sat1, get_cell_ids_h3(sat1.latitude.degrees, sat1.longitude.degrees, angle))

# exit()

# Can I specify the whole sphere to S2? Docs say an angle >= 180 is the whole sphere
# region = s2sphere.Cap.from_axis_angle(s2sphere.LatLng.from_degrees(0,0).to_point(), s2sphere.Angle.from_degrees(181))
# print(region.area())
# prints 12.566370614359172 which is 4*pi, so yes
# cells = get_cell_ids(0.,0.,181.)
# print(len(cells)) # prints 1572864, so yes that should be the whole sphere

coverage: DefaultDict[str,int] = defaultdict(int)
def readTokens():
    with open('cell_ids.txt', 'r') as fd:
        lines = fd.readlines()
        for line in lines:
            tok = line.strip()
            # cell_id = s2sphere.CellId.from_token(tok)
            coverage[tok] = 0

def readH3Indices() -> List[str]:
    with open('h3_5_index.txt', 'r') as fd:
        lines = [line.strip() for line in fd.readlines()]
    return lines

#readTokens()
TIME_PER_PROCESS = 1440 // 4 # 360 minutes, a quarter of a day
START_TIME = process * TIME_PER_PROCESS

for i in range(TIME_PER_PROCESS):
    time = ts.utc(2020,6,20,0,START_TIME+i,0)
    if i % 30 == 0:
        print(time.utc_iso())
    subpoints = {sat.name : sat.at(time).subpoint() for sat in sats}
    coverage_set: Set[str] = set()
    for sat_name, sat in subpoints.items():
        angle = calcCapAngle(sat.elevation.km, 35)
        cells = get_cell_ids_h3(sat.latitude.degrees, sat.longitude.degrees, angle)
        if len(cells) == 0:
            Exception("empty region returned")
        for cell in cells:
            coverage_set.add(cell)
    for cell in coverage_set:
        coverage[cell] += 1

with open(f"h3_{H3_RESOLUTION_LEVEL}_cov_{process}.txt", "w") as fd:
    for cell, cov in coverage.items():
        fd.write(f"{cell},{cov}\n")
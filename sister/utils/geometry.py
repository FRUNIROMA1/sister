#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SISTER
Space-based Imaging Spectroscopy and Thermal PathfindER
Author: Adam Chlus

"""
import os
import logging
import numpy as np
from rtree import index
from scipy.spatial import cKDTree
import gdal
from numba import jit
import statsmodels.api as sm
import ray
import pyproj
from skimage.util import view_as_blocks

class Projector():
    """Projector class"""

    def __init__(self):
        self.tree = None
        self.indices = None
        self.pixel_size = None
        self.input_shape = None
        self.inter_shape = None
        self.output_shape = None

        self.mask = None

    def create_tree(self,coords,input_shape):
        self.input_shape = input_shape
        self.tree = cKDTree(coords,balanced_tree= False)

    def query_tree(self,ulx,uly,pixel_size):
        half_pix = pixel_size/2
        self.pixel_size = pixel_size

        lines = (uly-self.tree.mins[1])//half_pix
        if lines%2 !=0:
            lines+=1

        columns = (self.tree.maxes[0]-ulx)//half_pix
        if columns%2 !=0:
            columns+=1

        self.inter_shape = (int(lines),int(columns))
        int_north,int_east = np.indices(self.inter_shape)
        int_east = (int_east*half_pix + ulx).flatten()
        int_north = (uly-int_north*half_pix).flatten()
        int_north= np.expand_dims(int_north,axis=1)
        int_east= np.expand_dims(int_east,axis=1)
        dest_points = np.concatenate([int_east,int_north],axis=1)

        distances,self.indices =  self.tree.query(dest_points,k=1)
        self.indices = np.unravel_index(self.indices,self.input_shape)
        distances =  distances.reshape(self.inter_shape)
        self.mask = distances > 2*pixel_size
        self.output_shape = (int(lines/2),int(columns/2))

    def project_band(self,band,no_data):
        band = np.copy(band[self.indices[0],self.indices[1]].reshape(self.inter_shape))
        band[self.mask] = np.nan
        band = np.nanmean(view_as_blocks(band, (2,2)),axis=(2,3))
        band[np.isnan(band)] = no_data
        return band


def utm_zone(longitude, latitude):
    ''' Returns UTM zone and direction
    '''
    zone = int(np.ceil((longitude.min()+180)/6))
    if latitude.mean() >0:
        direction = 'N'
    else:
        direction = 'S'
    return zone,direction


def dd2utm(longitude,latitude):
    '''Convert coordinates in decimal degrees int
    UTM eastings and northings
    '''
    zone,direction = utm_zone(longitude, latitude)

    if direction == 'N':
        epsg_dir = 6
    else:
        epsg_dir = 7

    out_crs = pyproj.Proj("+init=EPSG:32%s%02d" % (epsg_dir,zone))
    in_crs= pyproj.Proj("+init=EPSG:4326")

    # Convert to easting and northing,
    easting,northing = pyproj.transform(in_crs,out_crs,longitude,latitude)
    return easting,northing


def utm2dd(easting,northing,zone,direction):
    '''Convert coordinates in UTM eastings and northings into
        decimal degrees
    '''
    if direction == 'N':
        epsg_dir = 6
    else:
        epsg_dir = 7

    in_crs = pyproj.Proj("+init=EPSG:32%s%02d" % (epsg_dir,zone))
    out_crs= pyproj.Proj("+init=EPSG:4326")

    # Convert to easting and northing,
    longitude,latitude= pyproj.transform(in_crs,out_crs,easting,northing)
    return longitude,latitude


@jit(nopython=True)
def optimal_shift(indices,offset_x,offset_y,warp_band,ref_band,shift_max):
    '''Calculate optimal X and Y shift based on correlation between
    reference and warp bands. Use numba to speed up processing.
    '''

    sx,sy,px1,px2,py1,py2 = indices
    warp_sub = warp_band[py1:py2,px1:px2]
    mask = warp_sub.flatten() != -9999
    x = warp_sub.flatten()[mask]
    x_error = x-x.mean()
    x_error_sqr_sum = np.sum(x_error**2)

    opt_y,opt_x = 0,0
    opt_corr = -100

    for y_shift in range(-shift_max,shift_max):
        for x_shift in range(-shift_max,shift_max):
            lx1,lx2,ly1,ly2 = px1+offset_x+x_shift,px2+offset_x+x_shift,py1+offset_y+y_shift,py2+offset_y+y_shift
            ref_sub = ref_band[ly1:ly2,lx1:lx2]
            y = ref_sub.flatten()[mask]
            num  = np.sum(x_error*(y-y.mean()))
            denom = np.sqrt(x_error_sqr_sum*np.sum((y-y.mean())**2))
            if denom !=0:
                corr_coeff= num/denom
            else:
                corr_coeff= 0
            if corr_coeff > opt_corr:
                opt_corr = corr_coeff
                opt_y,opt_x = y_shift,x_shift
    return [sy,sx,opt_y,opt_x,opt_corr]

@ray.remote
def ray_optimal_shift(indices,offset_x,offset_y,warp_band,ref_band,shift_max):
    '''Wrapper around numba shift optimizer
    '''
    return optimal_shift(indices,offset_x,offset_y,warp_band,ref_band,shift_max)


def image_match(ref_file,warp_band,ulx,uly,sensor_zn_prj,sensor_az_prj,elevation_prj,shift_max=15):
    ''' This function takes as input a single landsat band 5 (850 nm) image
    and an image to be warped and calculates the offset surface in the X and Y
    direction as a function of the sensor zenith, sensor azimuth and ground elevation.

    Args:
        ref_file (str): Landsat B5 (850nm) pathanem.
        warp_band (np.array): Projected band to be warped.
        map_info (list): Map info list for warp band.
        sensor_zn_prj (np.array): Projected sensor zennith array.
        sensor_az_prj (np.array): Projected sensor azimuth array.
        elevation_prj_prj (np.array): Projected elevation array.
        shift_max (int): Maximum pixel shift to test.

    Returns:
        Y and X offset model coefficients.

    '''

    logging.info('Image matching')

    if ray.is_initialized():
        ray.shutdown()
    ray.init(num_cpus = 8)

    reference = gdal.Open(ref_file)
    east_min,pixel,a,north_max,b,c =reference.GetGeoTransform()

    ref_band =reference.GetRasterBand(1).ReadAsArray()
    ref_band =  ref_band.astype(np.int)

    offset_x = int((ulx-east_min)//30)
    offset_y = int((north_max-uly)//30)

    # Share arrays
    warp_band_r = ray.put(warp_band)
    ref_band_r = ray.put(ref_band)

    window = 25
    step = 5

    covar_surf = np.zeros((1+warp_band.shape[0]//step,1+warp_band.shape[1]//step,3))

    # Run correlation matching, use numba and ray to speed up
    results = []
    for sy,py1 in enumerate(range(0,warp_band.shape[0],step)):
        py2 = min(py1+window,warp_band.shape[0])
        for sx,px1 in enumerate(range(0,warp_band.shape[1],step)):
            px2 = min(px1+window,warp_band.shape[1])
            warp_sub = warp_band[py1:py2,px1:px2]
            mask = warp_sub.flatten() != -9999
            elev_sub =  elevation_prj[py1:py2,px1:px2].flatten()
            zn_sub =  sensor_zn_prj[py1:py2,px1:px2].flatten()
            az_sub =  sensor_az_prj[py1:py2,px1:px2].flatten()
            if np.sum(mask)> 100:
                covar_surf[sy,sx,:] = [zn_sub[mask].mean(),az_sub[mask].mean(),elev_sub[mask].mean()]
                indices = [sx,sy,px1,px2,py1,py2]
                results.append(ray_optimal_shift.remote(indices,
                                                        offset_x,offset_y,
                                                        warp_band_r,ref_band_r,
                                                        shift_max))
    results = ray.get(results)

    # Put results into arrays
    shift_surf = np.zeros((1+warp_band.shape[0]//step,1+warp_band.shape[1]//step,2))
    corr_surf = np.zeros((1+warp_band.shape[0]//step,1+warp_band.shape[1]//step))
    for sy,sx,opt_y,opt_x,opt_corr in results:
        shift_surf[int(sy),int(sx),:] = opt_y,opt_x
        corr_surf[int(sy),int(sx)] = opt_corr

    ray.shutdown()

    #Calculate shift slopes
    px, py = np.gradient(shift_surf[:,:,0])
    slope_y = np.sqrt(px ** 2 + py ** 2)

    px, py = np.gradient(shift_surf[:,:,1])
    slope_x = np.sqrt(px ** 2 + py ** 2)

    #Mask
    corr_thres = .4
    mask = (slope_y==0) & (corr_surf  > corr_thres) & (slope_x==0)

    # Fit X and Y offset linear models
    X = covar_surf[mask]
    y = shift_surf[:,:,1][mask]
    model_x = sm.OLS(y,sm.add_constant(X)).fit()
    logging.info('X offset model')
    logging.info(model_x.summary())

    y = shift_surf[:,:,0][mask]
    model_y = sm.OLS(y,sm.add_constant(X)).fit()
    logging.info('Y offset model')
    logging.info(model_y.summary())

    return (model_y.params,model_x.params)
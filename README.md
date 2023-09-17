# SISTER
## Space-based Imaging Spectroscopy and Thermal pathfindER

This repository contains code for implementing prototype algorithm workflows
for the Space-based Imaging Spectroscopy and Thermal pathfindER (SISTER).

This repository is under active development and currently contains
code for preprocessing imaging spectroscopy data from airborne and spaceborne
sensors for input into higher level algorithms including atmospheric, topographic
and BRDF correction algorithms.

### Installation
We recommend installing the libary and its dependencies in a conda environment.

To create and activate a new environment run:
```bash
conda create -n sister python=3.8
source activate sister
```

Next install gdal:
```bash
#conda install gdal=3.4.1
conda install gdal=3.6.2
conda install h5py 
conda install numba 
conda install git
conda install numpy=1.22.4 #(< 1.24.0) for the numpy float problem
```

To install the library, clone:
```bash
git clone https://github.com/EnSpec/sister.git
```
and install with pip:
```bash
pip install -e ./sister
```
If you are having this Error:
ERROR 1: ZIPDecode:Decoding error at scanline 0
ERROR 1: TIFFReadEncodedTile() failed.
there may be so me problem with gdal or Google Earth Engine
For Google Earth Engine pkease check your Earth Engine autentication.
For Gdal sems t be somting wrong with the conda installation (17/09/2023):
 conda uninstall gdal
 go to https://www.lfd.uci.edu/~gohlke/pythonlibs/#gdal and dounload a gdal version compatyble with your python version
 pip install "path_to_the_.whl_downloaded_file"
 conda uninstall numpy
 pip install numpy==1.21

### Examples

#### PRISMA HDF to ENVI

The following code takes as input a PRISMA L1 radiance image along with ESA Copernicus DEM tiles and exports
three ENVI formated files:
1. Merged VNIR+SWIR radiance datacube
2. Location datacube (longitude, latitude, altitude)
3. Observables datacube (sensor, solar geometry......)

[PRISMA Algorithm Workflow](https://raw.githubusercontent.com/EnSpec/sister/sister-dev/figures/prisma_workflow.svg)

```python

import os
from sister.sensors import prisma

l1_zip  = '/data/prisma/PRS_L1_STD_OFFL_ 20200621003500_20200621003505_0001.zip'
out_dir = '/data/prisma/rad/'
temp_dir =  '/data/temp/'
elev_dir = 'https://copernicus-dem-30m.s3.amazonaws.com/'

prisma.he5_to_envi(l1_zip,
			out_dir,
			temp_dir,
			elev_dir,
			shift = './data/prisma/PRISMA_Mali1_wavelength_shift_surface_smooth.npz',
			rad_coeff = './data/prisma/PRS_Mali1_radcoeff_surface.npz',
			match= True,
			proj = True)

```

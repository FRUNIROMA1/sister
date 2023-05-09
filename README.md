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
conda create -n sister python=3.8.16
conda activate sister
conda config --add channels conda-forge
```

Next install gdal:
```bash
#conda install gdal=3.4.1
conda install gdal=3.6.2
conda install h5py 
conda install numba 
conda install git
```

To install the library, clone:
```bash
git clone .....
```
and install with pip:
```bash
pip install -e ./sister
```
and install spyder:
```bash
conda install spyder
```
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

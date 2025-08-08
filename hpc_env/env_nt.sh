#!/bin/bash
# Auto-generated environment setup script

# Clean up
module purge

# Load modules

module load gcc/12.3.0

module load openmpi/4.1.5

module load cmake/3.26.3

module load ninja/1.11.1

module load hdf5/1.14.0

module load python/3.10.8


# Activate Python venv
source <add python virtual environment path here>


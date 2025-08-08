#!/bin/bash

# Clean up
module purge

# Load modules

module load pbs 
module load gcc/11.1.0 
module load openmpi/4.1.4 
module load cuda/11.7.0 
module load python3/3.11.0 
module load hdf5/1.10.7


# Activate Python venv
source <add python virtual environment path here>


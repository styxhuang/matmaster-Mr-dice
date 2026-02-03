#!/bin/bash

ORIG_DIR=$(pwd)

# Go to home directory
cd ~

# Delete .curlrc and .wgetrc
rm -f .curlrc .wgetrc

# Export proxy settings
export http_proxy='http://ga.dp.tech:8118'
export https_proxy='http://ga.dp.tech:8118'

# Activate conda environment
source /root/.bashrc  # Adjust path if needed
conda activate optimade

cd $ORIG_DIR

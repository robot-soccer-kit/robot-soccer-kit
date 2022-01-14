#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

sudo cp ${SCRIPT_DIR}/*.bin /lib/firmware/rtl_bt/

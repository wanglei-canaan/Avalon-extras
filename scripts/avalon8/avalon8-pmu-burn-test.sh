#!/bin/bash
cd /home/factory/Avalon-extras/scripts/avalon8/
python upload_chip_data.py & python avalon8-pmu-burn-test.py $1
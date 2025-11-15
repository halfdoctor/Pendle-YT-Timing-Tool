#!/bin/bash
# python3 -m venv ./venv
# source ./venv/bin/activate
# pip install -r requirements.txt
# chmod +x /root/powerloom/run_pendle.sh
# * * * * * /root/powerloom/run_pendle.sh


cd /home/nemin/pendle
source venv/bin/activate
python -u pendle_market_analysis_optimized.py 2>&1 | awk '{print strftime("%Y-%m-%d %H:%M:%S"), $0}' >> pendle.log

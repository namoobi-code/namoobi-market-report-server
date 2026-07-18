#!/bin/bash
# 3.1.9 대시보드 이미지 — docx와 같은 스크립트·같은 DB로 서버에서 생성 (픽셀 일치)
cd /home/ubuntu/namoobi/genwork
/home/ubuntu/namoobi/venv/bin/python /home/ubuntu/namoobi/scripts/gen_hbm_dashboard.py /home/ubuntu/namoobi/genwork
cp -f charts/hbm_dashboard.png /home/ubuntu/namoobi/data/charts/ 2>/dev/null

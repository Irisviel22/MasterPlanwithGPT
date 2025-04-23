#!/usr/bin/env bash
source /home/yu/Documents/01Project/MA_RL/venv/bin/activate
plan=$(python /home/yu/Documents/01Project/MA_RL/gpt_plan.py)
notify-send "GPT · 今日任务" "$plan"


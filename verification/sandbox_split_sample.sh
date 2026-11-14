#!/bin/bash
# samples pressure and memory every 5 s until the stop file exists
out=$1; stop=$2
while [ ! -e "$stop" ]; do
  echo "$(date +%T) cpu:$(grep some /proc/pressure/cpu) mem:$(grep some /proc/pressure/memory | cut -d' ' -f2-3) avail_mb:$(free -m | awk '/Mem:/{print $7}') ctrs:$(docker ps -q | wc -l)" >> "$out"
  sleep 5
done

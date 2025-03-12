#!/usr/bin/env bash
if git pull; then
    ps -ef | grep diet-record | grep -v grep | awk '{print $2}' | xargs kill -HUP
    exit $?
else
    echo "git pull 失败"
    exit 1
fi
#!/bin/bash
rm -rf dist && rm lambda.zip
pip3 install --target ./dist upstash-ratelimit-a
cp main.py ./dist/lambda_function.py
cd dist && zip -r lambda.zip . && cd -
mv ./dist/lambda.zip ./
# rm -rf dist
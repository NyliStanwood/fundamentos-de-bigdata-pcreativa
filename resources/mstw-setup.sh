#!/usr/bin/env bash
export PROJECT_HOME=/home/ibdn/practica_creativa

cd $PROJECT_HOME
python3 -m venv env
source env/bin/activate
cd $PROJECT_HOME/resources/web
python3 predict_flask.py



PWSHll

python -m venv env    # or python3 if that’s your command
.\env\Scripts\Activate.ps1
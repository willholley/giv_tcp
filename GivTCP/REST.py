# -*- coding: utf-8 -*-
# version 2021.12.22
from os.path import exists
from flask import Flask, request, send_from_directory, render_template
from flask_cors import CORS
import read as rd       #grab passthrough functions from main read file
import write as wr      #grab passthrough functions from main write file
import evc as evc
from GivLUT import GivLUT
import os
import json
from settings import GiV_Settings

logger = GivLUT.logger

#set-up Flask details
giv_api = Flask(__name__)
CORS(giv_api)

#Proxy Read Functions

#@giv_api.route('/', methods=['GET', 'POST'])
#def root():
#  return send_from_directory('/app/config_frontend/dist', 'index.html')

#@giv_api.route('/config')
#def get_config_page():
#  return send_from_directory('/app/config_frontend/dist', 'index.html')

#Read from Invertor put in cache and publish

@giv_api.route("/showdata")
def index():
    output=rd.getCache()
    return render_template('showdata.html', title="page", jsonfile=json.dumps(output))

@giv_api.route('/settings', methods=['POST'])
def savesetts():
    SFILE="/config/GivTCP/allsettings.json"
    setts = request.get_json()
    with open(SFILE, 'w') as f:
        f.write(json.dumps(setts,indent=4))
    return "Settings Updated"

@giv_api.route('/settings', methods=['GET'])
def returnsetts():
    SFILE="/config/GivTCP/allsettings.json"
    with open(SFILE, 'r') as f1:
        setts=json.load(f1)
        return setts

@giv_api.route('/runAll', methods=['GET'])
def getAll():
    # We need a safe way to do this for REST... just sending cache for now
    #logger.critical("runAll called via REST")
    output=rd.getCache()
    if output == None:
        return "{'Result':'Error, no data available'}"
    else:
        return output

@giv_api.route('/reboot', methods=['GET'])
def reboot():
    output=wr.rebootinverter()
    if output == None:
        return "{'Result':'Error, no data available'}"
    else:
        return output

@giv_api.route('/restart', methods=['GET'])
def restart():
    output=wr.rebootAddon()
    if output == None:
        return "{'Result':'Error, no data available'}"
    else:
        return "{'Success':'Container restarting...'}"

#Publish last cached Invertor Data
@giv_api.route('/readData', methods=['GET'])
def rdData():
    #logger.critical("readData called via REST")
    output=rd.pubFromPickle()
    if output == None:
        return "{'Result':'Error, no data available'}"
    else:
        return output

#Publish last cached Invertor Data
@giv_api.route('/getCache', methods=['GET'])
def gtCache():
    #logger.critical("getCache called via REST")
    output=rd.getCache()
    if output == None:
        return "{'Result':'Error, no data available'}"
    else:
        return output

# Read from Invertor put in cache
#@giv_api.route('/getData', methods=['GET'])
#def gtData():
#    return GivQueue.q.enqueue(rd.getData,True)

#Proxy Write Functions
@giv_api.route('/enableChargeTarget', methods=['POST'])
def enChargeTrgt():
    payload = request.get_json(silent=True, force=True)
    return wr.enableChargeTarget(payload)

@giv_api.route('/enableChargeSchedule', methods=['POST'])
def enableChrgSchedule():
    payload = request.get_json(silent=True, force=True)
    return wr.enableChargeSchedule(payload)

@giv_api.route('/enableDischargeSchedule', methods=['POST'])
def enableDischrgSchedule():
    payload = request.get_json(silent=True, force=True)
    return wr.enableDischargeSchedule(payload)

@giv_api.route('/enableDischarge', methods=['POST'])
def enableBatDisharge():
    payload = request.get_json(silent=True, force=True)
    return wr.enableDischarge(payload)

### Should this include a slot number and use setChargeTarget2 ###

@giv_api.route('/setChargeTarget', methods=['POST'])
def setChrgTarget():
    payload = request.get_json(silent=True, force=True)
    return wr.setChargeTarget(payload)

@giv_api.route('/setExportTarget', methods=['POST'])
def setExpTarget():
    payload = request.get_json(silent=True, force=True)
    return wr.setExportTarget(payload)

@giv_api.route('/setDischargeTarget', methods=['POST'])
def setDischrgTarget():
    payload = request.get_json(silent=True, force=True)
    return wr.setDischargeTarget(payload)

@giv_api.route('/setBatteryReserve', methods=['POST'])
def setBattReserve():
    payload = request.get_json(silent=True, force=True)
    return wr.setBatteryReserve(payload)

@giv_api.route('/setChargeRate', methods=['POST'])
def setChrgeRate():
    payload = request.get_json(silent=True, force=True)
    return wr.setChargeRate(payload)

@giv_api.route('/setCarChargeBoost', methods=['POST'])
def setCarBoost():
    payload = request.get_json(silent=True, force=True)
    return wr.setCarChargeBoost(payload)

@giv_api.route('/setExportLimit', methods=['POST'])
def setExpLim():
    payload = request.get_json(silent=True, force=True)
    return wr.setExportLimit(payload)

@giv_api.route('/setDischargeRate', methods=['POST'])
def setDischrgeRate():
    payload = request.get_json(silent=True, force=True)
    return wr.setDischargeRate(payload)

@giv_api.route('/setPauseSlot', methods=['POST'])
def setPausSlot():
    payload = request.get_json(silent=True, force=True)
    return wr.setPauseSlot(payload)

### Should these now include a slot number as the input? ###

@giv_api.route('/setChargeSlot', methods=['POST'])
def setChrgSlot():
    payload = request.get_json(silent=True, force=True)
    return wr.setChargeSlot(payload)

@giv_api.route('/setChargeSlot1', methods=['POST'])
def setChrgSlot1():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=1
    return wr.setChargeSlot(payload)

@giv_api.route('/setChargeSlot2', methods=['POST'])
def setChrgSlot2():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=2
    return wr.setChargeSlot(payload)

@giv_api.route('/setChargeSlot3', methods=['POST'])
def setChrgSlot3():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=3
    return wr.setChargeSlot(payload)

@giv_api.route('/setDischargeSlot1', methods=['POST'])
def setDischrgSlot1():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=1
    return wr.setDischargeSlot(payload)

@giv_api.route('/setDischargeSlot2', methods=['POST'])
def setDischrgSlot2():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=2
    return wr.setDischargeSlot(payload)

@giv_api.route('/setDischargeSlot3', methods=['POST'])
def setDischrgSlot3():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=3
    return wr.setDischargeSlot(payload)

@giv_api.route('/setExportSlot1', methods=['POST'])
def setExpSlot1():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=1
    return wr.setExportSlot(payload)
@giv_api.route('/setExportSlot2', methods=['POST'])
def setExpSlot2():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=2
    return wr.setExportSlot(payload)
@giv_api.route('/setExportSlot3', methods=['POST'])
def setExpSlot3():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=3
    return wr.setExportSlot(payload)

@giv_api.route('/tempPauseDischarge', methods=['POST'])
def tmpPauseDischrg():
    payload = request.get_json(silent=True, force=True)
    if payload['duration'] == "Cancel" or payload['duration'] == "0":
        if exists(".tpdRunning"):
            jobid= str(open(".tpdRunning","r").readline())
            logger.critical("Retrieved jobID to cancel Temp Pause Discharge: "+ str(jobid))
            return wr.cancelJob(jobid)
        else:
            logger.error("Temp Pause Discharge is not currently running")
    else:
        return wr.tempPauseDischarge(int(payload['duration']))

@giv_api.route('/tempPauseCharge', methods=['POST'])
def tmpPauseChrg():
    payload = request.get_json(silent=True, force=True)
    if payload['duration'] == "Cancel" or payload['duration'] == "0":
        if exists(".tpcRunning"):
            jobid= str(open(".tpcRunning","r").readline())
            logger.debug("Retrieved jobID to cancel Temp Pause Charge: "+ str(jobid))
            return wr.cancelJob(jobid)
        else:
            logger.error("Temp Pause Charge is not currently running")
    else:
        return wr.tempPauseCharge(int(payload['duration']))

@giv_api.route('/forceCharge', methods=['POST'])
def frceChrg():
    payload = request.get_json(silent=True, force=True)
    #Check if Cancel then return the right function
    if payload['duration'] == "Cancel" or payload['duration'] == "0":
        if exists(".FCRunning"):
            jobid= str(open(".FCRunning","r").readline())
            logger.debug("Retrieved jobID to cancel Force Charge: "+ str(jobid))
            return wr.cancelJob(jobid)
        else:
            logger.error("Force Charge is not currently running")
    else:
        return wr.forceCharge(int(payload['duration']))

@giv_api.route('/forceExport', methods=['POST'])
def frceExprt():
    payload = request.get_json(silent=True, force=True)
    if payload['duration'] == "Cancel" or payload['duration'] == "0":
        if exists(".FERunning"):
            jobid= str(open(".FERunning","r").readline())
            logger.debug("Retrieved jobID to cancel Force Export: "+ str(jobid))
            return wr.cancelJob(jobid)
        else:
            logger.error("Force Charge is not currently running")
    else:
        return wr.forceExport(int(payload['duration']))

@giv_api.route('/setBatteryMode', methods=['POST'])
def setBattMode():
    payload = request.get_json(silent=True, force=True)
    return wr.setBatteryMode(payload)

@giv_api.route('/setBatteryPauseMode', methods=['POST'])
def setBattPausMode():
    payload = request.get_json(silent=True, force=True)
    return wr.setBatteryPauseMode(payload)

@giv_api.route('/setDateTime', methods=['POST'])
def setDate():
    payload = request.get_json(silent=True, force=True)
    return wr.setDateTime(payload)

@giv_api.route('/switchRate', methods=['POST'])
def swRates():
    payload = request.get_json(silent=True, force=True)
    return wr.switchRate(payload['rate'])

@giv_api.route('/setImportCap', methods=['POST'])
def impCap():
    payload = request.get_json(silent=True, force=True)
    return evc.setImportCap(payload)

@giv_api.route('/setCurrentLimit', methods=['POST'])
def currLimit():
    payload = request.get_json(silent=True, force=True)
    return evc.setCurrentLimit(payload)

@giv_api.route('/setChargeControl', methods=['POST'])
def chrgeControl():
    payload = request.get_json(silent=True, force=True)
    return evc.setChargeControl(payload)

@giv_api.route('/setChargeMode', methods=['POST'])
def chrgMode():
    payload = request.get_json(silent=True, force=True)
    return evc.setChargeMode(payload)

@giv_api.route('/setChargingMode', methods=['POST'])
def chrgingMode():
    payload = request.get_json(silent=True, force=True)
    return evc.setChargingMode(payload)

@giv_api.route('/setMaxSessionEnergy', methods=['POST'])
def maxSession():
    payload = request.get_json(silent=True, force=True)
    return evc.setMaxSessionEnergy(payload)

@giv_api.route('/getEVCCache', methods=['GET'])
def gtEVCChce():
    payload = request.get_json(silent=True, force=True)
    return evc.getEVCCache()



if __name__ == "__main__":
    giv_api.run()

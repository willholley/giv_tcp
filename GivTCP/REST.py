# -*- coding: utf-8 -*-
# version 2021.12.22
from os.path import exists
from flask import Flask, request, send_from_directory
from flask_cors import CORS
import read as rd       #grab passthrough functions from main read file
import write as wr      #grab passthrough functions from main write file
import evc as evc
import config_dash as cfdash
from GivLUT import GivQueue, GivLUT
import os
import json
from settings import GiV_Settings

logger = GivLUT.logger

#set-up Flask details
giv_api = Flask(__name__)
CORS(giv_api)

jsonResponseType = { 'Content-Type': 'application/json; charset=utf-8' }

#Proxy Read Functions

@giv_api.route('/', methods=['GET', 'POST'])
def root():
  return send_from_directory('/app/config_frontend/dist', 'index.html')

@giv_api.route('/config')
def get_config_page():
  return send_from_directory('/app/config_frontend/dist', 'index.html')
#    if request.method=="GET":
#        return cfdash.get_config()
#    if request.method=="POST":
#        return cfdash.set_config(request.form)

#Read from Invertor put in cache and publish
@giv_api.route('/runAll', methods=['GET'])
def getAll():
    return rd.runAll(True), 200, jsonResponseType

@giv_api.route('/reboot', methods=['GET'])
def reboot():
    return wr.rebootinverter(), 200, jsonResponseType

@giv_api.route('/restart', methods=['GET'])
def restart():
    return wr.rebootAddon(), 200, jsonResponseType

#Publish last cached Invertor Data
@giv_api.route('/readData', methods=['GET'])
def rdData():
    return rd.pubFromPickle(), 200, jsonResponseType

#Publish last cached Invertor Data
@giv_api.route('/getCache', methods=['GET'])
def gtCache():
    return rd.getCache(), 200, jsonResponseType

# Read from Invertor put in cache
@giv_api.route('/getData', methods=['GET'])
def gtData():
    return GivQueue.q.enqueue(rd.getData,True), 200, jsonResponseType

#Proxy Write Functions
@giv_api.route('/enableChargeTarget', methods=['POST'])
def enChargeTrgt():
    payload = request.get_json(silent=True, force=True)
    return wr.enableChargeTarget(payload), 200, jsonResponseType

@giv_api.route('/enableChargeSchedule', methods=['POST'])
def enableChrgSchedule():
    payload = request.get_json(silent=True, force=True)
    return wr.enableChargeSchedule(payload), 200, jsonResponseType

@giv_api.route('/enableDischargeSchedule', methods=['POST'])
def enableDischrgSchedule():
    payload = request.get_json(silent=True, force=True)
    return wr.enableDischargeSchedule(payload), 200, jsonResponseType

@giv_api.route('/enableDischarge', methods=['POST'])
def enableBatDisharge():
    payload = request.get_json(silent=True, force=True)
    return wr.enableDischarge(payload), 200, jsonResponseType

@giv_api.route('/setChargeTarget', methods=['POST'])
def setChrgTarget():
    payload = request.get_json(silent=True, force=True)
    return wr.setChargeTarget(payload), 200, jsonResponseType

@giv_api.route('/setBatteryReserve', methods=['POST'])
def setBattReserve():
    payload = request.get_json(silent=True, force=True)
    return wr.setBatteryReserve(payload), 200, jsonResponseType

@giv_api.route('/setChargeRate', methods=['POST'])
def setChrgeRate():
    payload = request.get_json(silent=True, force=True)
    return wr.setChargeRate(payload), 200, jsonResponseType

@giv_api.route('/setDischargeRate', methods=['POST'])
def setDischrgeRate():
    payload = request.get_json(silent=True, force=True)
    return wr.setDischargeRate(payload), 200, jsonResponseType

@giv_api.route('/setChargeSlot1', methods=['POST'])
def setChrgSlot1():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=1
    return wr.setChargeSlot(payload), 200, jsonResponseType

@giv_api.route('/setChargeSlot2', methods=['POST'])
def setChrgSlot2():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=2
    return wr.setChargeSlot(payload), 200, jsonResponseType

@giv_api.route('/setDischargeSlot1', methods=['POST'])
def setDischrgSlot1():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=1
    return wr.setDischargeSlot(payload), 200, jsonResponseType

@giv_api.route('/setDischargeSlot2', methods=['POST'])
def setDischrgSlot2():
    payload = request.get_json(silent=True, force=True)
    payload['slot']=2
    return wr.setDischargeSlot(payload), 200, jsonResponseType

@giv_api.route('/tempPauseDischarge', methods=['POST'])
def tmpPauseDischrg():
    payload = request.get_json(silent=True, force=True)
    if payload == "Cancel":
        if exists(".tpdRunning"):
            jobid= str(open(".tpdRunning","r").readline())
            logger.critical("Retrieved jobID to cancel Temp Pause Discharge: "+ str(jobid))
            return wr.cancelJob(jobid), 200, jsonResponseType
        else:
            logger.error("Force Charge is not currently running")
    else:
        return wr.tempPauseDischarge(payload), 200, jsonResponseType

@giv_api.route('/tempPauseCharge', methods=['POST'])
def tmpPauseChrg():
    payload = request.get_json(silent=True, force=True)
    if payload == "Cancel":
        if exists(".tpcRunning"):
            jobid= str(open(".tpcRunning","r").readline())
            logger.debug("Retrieved jobID to cancel Temp Pause Charge: "+ str(jobid))
            return wr.cancelJob(jobid), 200, jsonResponseType
        else:
            logger.error("Force Charge is not currently running")
    else:
        return wr.tempPauseCharge(payload), 200, jsonResponseType

@giv_api.route('/forceCharge', methods=['POST'])
def frceChrg():
    payload = request.get_json(silent=True, force=True)
    #Check if Cancel then return the right function
    if payload == "Cancel":
        if exists(".FCRunning"):
            jobid= str(open(".FCRunning","r").readline())
            logger.debug("Retrieved jobID to cancel Force Charge: "+ str(jobid))
            return wr.cancelJob(jobid), 200, jsonResponseType
        else:
            logger.error("Force Charge is not currently running")
    return wr.forceCharge(payload), 200, jsonResponseType

@giv_api.route('/forceExport', methods=['POST'])
def frceExprt():
    payload = request.get_json(silent=True, force=True)
    if payload == "Cancel":
        if exists(".FERunning"):
            jobid= str(open(".FERunning","r").readline())
            logger.debug("Retrieved jobID to cancel Force Export: "+ str(jobid))
            return wr.cancelJob(jobid), 200, jsonResponseType
        else:
            logger.error("Force Charge is not currently running")
    return wr.forceExport(payload), 200, jsonResponseType

@giv_api.route('/setBatteryMode', methods=['POST'])
def setBattMode():
    payload = request.get_json(silent=True, force=True)
    return wr.setBatteryMode(payload), 200, jsonResponseType

@giv_api.route('/setDateTime', methods=['POST'])
def setDate():
    payload = request.get_json(silent=True, force=True)
    return wr.setDateTime(payload), 200, jsonResponseType

@giv_api.route('/switchRate', methods=['POST'])
def swRates():
    payload = request.get_json(silent=True, force=True)
    return wr.switchRate(payload), 200, jsonResponseType

@giv_api.route('/settings', methods=['GET'])
def getFileData():
    file = open('/config/GivTCP/settings'+str(GiV_Settings.givtcp_instance)+'.json', 'r')
    #file = open(os.path.dirname(__file__) + '/settings.json', 'r')
    data = json.load(file)
    file.close()
    return data

@giv_api.route('/settings', methods=['POST'])
def editFileData():
    file = open('/config/GivTCP/settings'+str(GiV_Settings.givtcp_instance)+'.json', 'r')
    data = json.load(file)
    file.close()
    data.update(request.get_json(silent=True, force=True))
    file = open('/config/GivTCP/settings'+str(GiV_Settings.givtcp_instance)+'.json', 'w')
    json.dump(data, file,indent=4)
    file.close()
    return data

@giv_api.route('/setImportCap', methods=['POST'])
def impCap():
    payload = request.get_json(silent=True, force=True)
    return evc.setImportCap(payload), 200, jsonResponseType

@giv_api.route('/setCurrentLimit', methods=['POST'])
def currLimit():
    payload = request.get_json(silent=True, force=True)
    return evc.setCurrentLimit(payload), 200, jsonResponseType

@giv_api.route('/setChargeControl', methods=['POST'])
def chrgeControl():
    payload = request.get_json(silent=True, force=True)
    return evc.setChargeControl(payload), 200, jsonResponseType

@giv_api.route('/setChargeMode', methods=['POST'])
def chrgMode():
    payload = request.get_json(silent=True, force=True)
    return evc.setChargeMode(payload), 200, jsonResponseType

@giv_api.route('/setChargingMode', methods=['POST'])
def chrgingMode():
    payload = request.get_json(silent=True, force=True)
    return evc.setChargingMode(payload), 200, jsonResponseType

@giv_api.route('/setMaxSessionEnergy', methods=['POST'])
def maxSession():
    payload = request.get_json(silent=True, force=True)
    return evc.setMaxSessionEnergy(payload), 200, jsonResponseType

@giv_api.route('/getEVCCache', methods=['GET'])
def gtEVCChce():
    payload = request.get_json(silent=True, force=True)
    return evc.getEVCCache(), 200, jsonResponseType



if __name__ == "__main__":
    giv_api.run()

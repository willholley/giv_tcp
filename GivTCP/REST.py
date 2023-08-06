"""Provides endpoints for reading and control of GivTCP via REST"""
# -*- coding: utf-8 -*-
# version 2021.12.22
from os.path import exists
from flask import Flask, request
from flask_cors import CORS
import read as rd       #grab passthrough functions from main read file
import write as wr      #grab passthrough functions from main write file
import config_dash as cfdash
from GivLUT import GivQueue, GivLUT

logger = GivLUT.logger

#set-up Flask details
giv_api = Flask(__name__)
CORS(giv_api)

#Proxy Read Functions
@giv_api.route('/config', methods=['GET', 'POST'])
def get_config_page():
    """Simple Config Page via web"""
    if request.method=="GET":
        return cfdash.get_config()
    elif request.method=="POST":
        return cfdash.set_config(request.form)
    return "No GET or POST recieved"

#Read from Invertor put in cache and publish
@giv_api.route('/runAll', methods=['GET'])
def getAll():
    """Calls the runALL function from read.py via REST"""
    return rd.runAll(True)

@giv_api.route('/reboot', methods=['GET'])
def reboot():
    """Calls the rebootinverter function from write.py via REST"""
    return wr.rebootinverter()

#Publish last cached Invertor Data
@giv_api.route('/readData', methods=['GET'])
def rdData():
    """Calls the pubFromPickle function from read.py via REST"""
    return rd.pubFromPickle()

#Publish last cached Invertor Data
@giv_api.route('/getCache', methods=['GET'])
def gtCache():
    """Calls the getCache function from read.py via REST"""
    return rd.getCache()

#Read from Invertor put in cache
@giv_api.route('/getData', methods=['GET'])
def gtData():
    """Calls the getData function from read.py via REST"""
    return GivQueue.q.enqueue(rd.getData,True)

#Proxy Write Functions
@giv_api.route('/enableChargeTarget', methods=['POST'])
def enChargeTrgt():
    """Calls the enableChargeTarget function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return wr.enableChargeTarget(payload)

@giv_api.route('/enableChargeSchedule', methods=['POST'])
def enableChrgSchedule():
    """Calls the enableChargeSchedule function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return wr.enableChargeSchedule(payload)

@giv_api.route('/enableDischargeSchedule', methods=['POST'])
def enableDischrgSchedule():
    """Calls the enableDischargeSchedule function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return wr.enableDischargeSchedule(payload)

@giv_api.route('/enableDischarge', methods=['POST'])
def enableBatDisharge():
    """Calls the enableDischarge function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return wr.enableDischarge(payload)

@giv_api.route('/setChargeTarget', methods=['POST'])
def setChrgTarget():
    """Calls the setChargeTarget function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return wr.setChargeTarget(payload)

@giv_api.route('/setBatteryReserve', methods=['POST'])
def setBattReserve():
    """Calls the setBatteryReserve function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return wr.setBatteryReserve(payload)

@giv_api.route('/setChargeRate', methods=['POST'])
def setChrgeRate():
    """Calls the setChargeRate function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return wr.setChargeRate(payload)

@giv_api.route('/setDischargeRate', methods=['POST'])
def setDischrgeRate():
    """Calls the setDischargeRate function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return wr.setDischargeRate(payload)

@giv_api.route('/setChargeSlot1', methods=['POST'])
def setChrgSlot1():
    """Calls the setChargeSlot function for slot 1 from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    payload['slot']=1
    return wr.setChargeSlot(payload)

@giv_api.route('/setChargeSlot2', methods=['POST'])
def setChrgSlot2():
    """Calls the setChargeSlot function for slot 2 from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    payload['slot']=2
    return wr.setChargeSlot(payload)

@giv_api.route('/setDischargeSlot1', methods=['POST'])
def setDischrgSlot1():
    """Calls the setDischargeSlot function for slot 1 from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    payload['slot']=1
    return wr.setDischargeSlot(payload)

@giv_api.route('/setDischargeSlot2', methods=['POST'])
def setDischrgSlot2():
    """Calls the setDischargeSlot function for slot 2 from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    payload['slot']=2
    return wr.setDischargeSlot(payload)

@giv_api.route('/tempPauseDischarge', methods=['POST'])
def tmpPauseDischrg():
    """Calls the tempPauseCharge function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    if payload == "Cancel":
        if exists(".tpdRunning"):
            jobid= str(open(".tpdRunning","r", encoding='ascii').readline())
            logger.critical("Retrieved jobID to cancel Temp Pause Discharge: "+ str(jobid))
            return wr.cancelJob(jobid)
        else:
            logger.error("Force Charge is not currently running")
    else:
        return wr.tempPauseDischarge(payload)

@giv_api.route('/tempPauseCharge', methods=['POST'])
def tmpPauseChrg():
    """Calls the tempPauseCharge function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    if payload == "Cancel":
        if exists(".tpcRunning"):
            jobid= str(open(".tpcRunning","r", encoding='ascii').readline())
            logger.debug("Retrieved jobID to cancel Temp Pause Charge: "+ str(jobid))
            return wr.cancelJob(jobid)
        else:
            logger.error("Force Charge is not currently running")
    else:
        return wr.tempPauseCharge(payload)

@giv_api.route('/forceCharge', methods=['POST'])
def frceChrg():
    """Calls the forceCharge function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    #Check if Cancel then return the right function
    if payload == "Cancel":
        if exists(".FCRunning"):
            jobid= str(open(".FCRunning","r", encoding='ascii').readline())
            logger.debug("Retrieved jobID to cancel Force Charge: "+ str(jobid))
            return wr.cancelJob(jobid)
        else:
            logger.error("Force Charge is not currently running")
    else:
        return wr.forceCharge(payload)

@giv_api.route('/forceExport', methods=['POST'])
def frceExprt():
    """Calls the forceExport function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    if payload == "Cancel":
        if exists(".FERunning"):
            jobid= str(open(".FERunning","r", encoding='ascii').readline())
            logger.debug("Retrieved jobID to cancel Force Export: "+ str(jobid))
            return wr.cancelJob(jobid)
        else:
            logger.error("Force Charge is not currently running")
    else:
        return wr.forceExport(payload)

@giv_api.route('/setBatteryMode', methods=['POST'])
def setBattMode():
    """Calls the setBatteryMode function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return wr.setBatteryMode(payload)

@giv_api.route('/setDateTime', methods=['POST'])
def setDate():
    """Calls the setDateTime function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return wr.setDateTime(payload)

@giv_api.route('/switchRate', methods=['POST'])
def swRates():
    """Calls the switchRate function from write.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return wr.switchRate(payload)

if __name__ == "__main__":
    giv_api.run()
    
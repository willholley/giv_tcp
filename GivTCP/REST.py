"""Provides endpoints for reading and control of GivTCP via REST"""
# -*- coding: utf-8 -*-
# version 2021.12.22
from os.path import exists
from flask import Flask, request
from flask_cors import CORS
from . import read       #grab passthrough functions from main read file
from . import write      #grab passthrough functions from main write file
import config_dash as cfdash
from .giv_lut import GivQueue, GivLUT

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
def get_all():
    """Calls the runALL function from read.py via REST"""
    return read.runAll(True)

@giv_api.route('/reboot', methods=['GET'])
def reboot():
    """Calls the rebootinverter function from writeite.py via REST"""
    return write.rebootinverter()

#Publish last cached Invertor Data
@giv_api.route('/readData', methods=['GET'])
def read_data():
    """Calls the pubFromPickle function from read.py via REST"""
    return read.pub_from_pickle()

#Publish last cached Invertor Data
@giv_api.route('/getCache', methods=['GET'])
def gt_cache():
    """Calls the getCache function from read.py via REST"""
    return read.get_cache()

#Read from Invertor put in cache
@giv_api.route('/getData', methods=['GET'])
def gt_data():
    """Calls the getData function from read.py via REST"""
    return GivQueue.q.enqueue(read.get_data,True)

#Proxy Write Functions
@giv_api.route('/enableChargeTarget', methods=['POST'])
def en_charge_trgt():
    """Calls the enableChargeTarget function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return write.enableChargeTarget(payload)

@giv_api.route('/enableChargeSchedule', methods=['POST'])
def enable_chrg_schedule():
    """Calls the enableChargeSchedule function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return write.enableChargeSchedule(payload)

@giv_api.route('/enableDischargeSchedule', methods=['POST'])
def enable_dischrg_schedule():
    """Calls the enableDischargeSchedule function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return write.enableDischargeSchedule(payload)

@giv_api.route('/enableDischarge', methods=['POST'])
def enable_bat_disharge():
    """Calls the enableDischarge function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return write.enableDischarge(payload)

@giv_api.route('/setChargeTarget', methods=['POST'])
def set_chrg_target():
    """Calls the setChargeTarget function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return write.setChargeTarget(payload)

@giv_api.route('/setBatteryReserve', methods=['POST'])
def set_batt_reserve():
    """Calls the setBatteryReserve function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return write.setBatteryReserve(payload)

@giv_api.route('/setChargeRate', methods=['POST'])
def set_chrge_rate():
    """Calls the setChargeRate function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return write.setChargeRate(payload)

@giv_api.route('/setDischargeRate', methods=['POST'])
def set_dischrge_rate():
    """Calls the setDischargeRate function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return write.setDischargeRate(payload)

@giv_api.route('/setChargeSlot1', methods=['POST'])
def set_chrg_slot1():
    """Calls the setChargeSlot function for slot 1 from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    payload['slot']=1
    return write.setChargeSlot(payload)

@giv_api.route('/setChargeSlot2', methods=['POST'])
def set_chrg_slot2():
    """Calls the setChargeSlot function for slot 2 from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    payload['slot']=2
    return write.setChargeSlot(payload)

@giv_api.route('/setDischargeSlot1', methods=['POST'])
def set_dischrg_slot1():
    """Calls the setDischargeSlot function for slot 1 from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    payload['slot']=1
    return write.setDischargeSlot(payload)

@giv_api.route('/setDischargeSlot2', methods=['POST'])
def set_dischrg_slot2():
    """Calls the setDischargeSlot function for slot 2 from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    payload['slot']=2
    return write.setDischargeSlot(payload)

@giv_api.route('/tempPauseDischarge', methods=['POST'])
def tmp_pause_dischrg():
    """Calls the tempPauseCharge function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    if payload == "Cancel":
        if exists(".tpdRunning"):
            jobid= str(open(".tpdRunning","r", encoding='ascii').readline())
            logger.critical("Retrieved jobID to cancel Temp Pause Discharge: %s", str(jobid))
            return write.cancelJob(jobid)
        else:
            logger.error("Force Charge is not currently running")
    else:
        return write.tempPauseDischarge(payload)

@giv_api.route('/tempPauseCharge', methods=['POST'])
def tmp_pause_chrg():
    """Calls the tempPauseCharge function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    if payload == "Cancel":
        if exists(".tpcRunning"):
            jobid= str(open(".tpcRunning","r", encoding='ascii').readline())
            logger.debug("Retrieved jobID to cancel Temp Pause Charge: %s", str(jobid))
            return write.cancelJob(jobid)
        else:
            logger.error("Force Charge is not currently running")
    else:
        return write.tempPauseCharge(payload)

@giv_api.route('/forceCharge', methods=['POST'])
def frce_chrg():
    """Calls the forceCharge function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    #Check if Cancel then return the right function
    if payload == "Cancel":
        if exists(".FCRunning"):
            jobid= str(open(".FCRunning","r", encoding='ascii').readline())
            logger.debug("Retrieved jobID to cancel Force Charge: %s", str(jobid))
            return write.cancelJob(jobid)
        else:
            logger.error("Force Charge is not currently running")
    else:
        return write.forceCharge(payload)

@giv_api.route('/forceExport', methods=['POST'])
def frce_exprt():
    """Calls the forceExport function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    if payload == "Cancel":
        if exists(".FERunning"):
            jobid= str(open(".FERunning","r", encoding='ascii').readline())
            logger.debug("Retrieved jobID to cancel Force Export: %s", str(jobid))
            return write.cancelJob(jobid)
        else:
            logger.error("Force Charge is not currently running")
    else:
        return write.forceExport(payload)

@giv_api.route('/setBatteryMode', methods=['POST'])
def set_batt_mode():
    """Calls the setBatteryMode function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return write.setBatteryMode(payload)

@giv_api.route('/setDateTime', methods=['POST'])
def set_date():
    """Calls the setDateTime function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return write.setDateTime(payload)

@giv_api.route('/switchRate', methods=['POST'])
def sw_rates():
    """Calls the switchRate function from writeite.py via REST"""
    payload = request.get_json(silent=True, force=True)
    return write.switchRate(payload)

if __name__ == "__main__":
    giv_api.run()
    
"""Module which holds all Inverter write functions"""
# pylint: disable=line-too-long
import sys
import json
import logging
import datetime
from datetime import datetime, timedelta
import time
from os.path import exists
import pickle
import os
import importlib
from rq import Retry
import requests
from givenergy_modbus.client import GivEnergyClient
from .giv_lut import GivLUT, GivQueue
from .mqtt import GivMQTT
from . import settings
from .settings import GivSettings

logging.getLogger("givenergy_modbus").setLevel(logging.CRITICAL)
client=GivEnergyClient(host=GivSettings.invertorIP)

logger = GivLUT.logger

def update_control_mqtt(entity,value):
    """ immediately update broker on success of control áction"""
    importlib.reload(settings)
    from .settings import GivSettings
    if GivSettings.MQTT_Topic == "":
        GivSettings.MQTT_Topic = "GivEnergy"
    topic=str(GivSettings.MQTT_Topic+"/"+GivSettings.serial_number+"/Control/")+str(entity)
    GivMQTT.single_mqtt_publish(topic,str(value))
    return


def sct(target):
    """Helper function"""
    temp={}
    try:
        client.enable_charge_target(target)
        update_control_mqtt("Target_SOC",target)
        temp['result']="Setting Charge Target "+str(target)+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Target "+str(target)+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def sct2(target,slot):
    """Helper function"""
    temp={}
    try:
        client.enable_charge_target_2(target,slot)
        update_control_mqtt("Charge_Target_SOC_"+str(slot),target)
        temp['result']="Setting Charge Target "+str(slot) + " was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Target "+str(slot) + " failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def ect():
    """Helper function"""
    temp={}
    try:
        client.enable_charge_target(100)
        temp['result']="Setting Charge Enable was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Enable failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def dct():
    """Helper function"""
    temp={}
    try:
        client.disable_charge_target()
        update_control_mqtt("Target_SOC","100")
        temp['result']="Setting Discharge Disable was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Discharge Disable failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def ed():
    """Helper function"""
    temp={}
    try:
        client.enable_discharge()
        update_control_mqtt("Enable_Discharge_Schedule","enable")
        temp['result']="Enabling Discharge was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Enabling Discharge failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def dd():
    """Helper function"""
    temp={}
    try:
        client.disable_discharge()
        update_control_mqtt("Enable_Discharge_Schedule","disable")
        temp['result']="Disabling discharge was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Disabling discharge failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def ec():
    """Helper function"""
    temp={}
    try:
        client.enable_charge()
        update_control_mqtt("Enable_Charge_Schedule","enable")
        temp['result']="Setting Charge Enable was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Enable failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def dc():
    """Helper function"""
    temp={}
    try:
        client.disable_charge()
        update_control_mqtt("Enable_Charge_Schedule","disable")
        temp['result']="Disabling Charge was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Disabling Charge failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)

def slcm(val):
    """Helper function"""
    temp={}
    try:
        client.set_local_control_mode(val)
        update_control_mqtt("Local_control_mode",str(GivLUT.local_control_mode[int(val)]))
        temp['result']="Setting Local Control Mode to " +str(GivLUT.local_control_mode[val])+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Local Control Mode to " +str(GivLUT.local_control_mode[val])+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)

def sbpm(val):
    """Helper function"""
    temp={}
    try:
        client.set_battery_pause_mode(val)
        update_control_mqtt("Battery_pause_mode",str(GivLUT.battery_pause_mode[int(val)]))
        temp['result']="Setting Battery Pause Mode to " +str(GivLUT.battery_pause_mode[val])+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Battery Pause Mode to " +str(GivLUT.battery_pause_mode[val])+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
    #return temp

def ssc(target):
    """Helper function"""
    temp={}
    try:
        client.set_shallow_charge(target)
        update_control_mqtt("Battery_Power_Reserve",str(target))
        temp['result']="Setting shallow charge "+str(target)+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting shallow charge "+str(target)+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def sbpr(target):
    """Helper function"""
    temp={}
    try:
        client.set_battery_power_reserve(target)
        update_control_mqtt("Battery_Power_Cutoff",str(target))
        temp['result']="Setting battery power reserve to "+str(target)+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting battery power reserve "+str(target)+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def ri():
    """Helper function"""
    temp={}
    try:
        client.reboot_inverter()
        temp['result']="Rebooting Inverter was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Rebooting Inverter failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def sapr(target):
    """Helper function"""
    temp={}
    try:
        client.set_active_power_rate(target)
        update_control_mqtt("Active_Power_Rate",str(target))
        temp['result']="Setting active power rate "+str(target)+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting active power rate "+str(target)+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def sbcl(target):
    """Helper function"""
    temp={}
    try:
        client.set_battery_charge_limit(target)
        # Get cache and work out rate
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                reg_cache_stack = pickle.load(inp)
                multi_output_old = reg_cache_stack[4]
                batteryCapacity=int(multi_output_old["Invertor_Details"]['Battery_Capacity_kWh'])*1000
                batmaxrate=int(multi_output_old["Invertor_Details"]['Invertor_Max_Bat_Rate'])
            val=int(min((target/100)*(batteryCapacity), batmaxrate))
            update_control_mqtt("Battery_Charge_Rate",str(val))
        temp['result']="Setting battery charge rate "+str(target)+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting battery charge rate "+str(target)+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def sbdl(target):
    """Helper function"""
    temp={}
    try:
        # Get cache and work out rate
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                reg_cache_stack = pickle.load(inp)
                multi_output_old = reg_cache_stack[4]
                battery_capacity=int(multi_output_old["Invertor_Details"]['Battery_Capacity_kWh'])*1000
                batmaxrate=int(multi_output_old["Invertor_Details"]['Invertor_Max_Bat_Rate'])
            val=int(min((target/100)*(battery_capacity), batmaxrate))
        client.set_battery_discharge_limit(val)
        temp['result']="Setting battery discharge limit "+str(target)+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting battery discharge limit "+str(target)+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def smd():
    """Helper function"""
    temp={}
    try:
        client.set_mode_dynamic()
        #update_control_mqtt("Mode","Eco")
        temp['result']="Setting dynamic mode was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting dynamic mode failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def sms(target):
    """Helper function"""
    temp={}
    try:
        client.set_mode_storage(target)
        temp['result']="Setting storage mode "+str(target)+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting storage mode "+str(target)+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def sbdmd():
    """Helper function"""
    temp={}
    try:
        client.set_battery_discharge_mode_demand()
        #update_control_mqtt("Mode","Timed Demand")
        temp['result']="Setting demand mode was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting demand mode failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def sbdmmp():
    """Helper function"""
    temp={}
    try:
        client.set_battery_discharge_mode_max_power()
        #update_control_mqtt("Mode","Timed Export")
        temp['result']="Setting export mode was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting export mode failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)

def spvim(val):
    """Helper function"""
    temp={}
    try:
        client.set_pv_input_mode(val)
        update_control_mqtt("PV_input_mode",str(GivLUT.pv_input_mode[int(val)]))
        temp['result']="Setting PV Input mode to "+str(GivLUT.pv_input_mode[val])+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting PV Input mode to "+str(GivLUT.pv_input_mode[val])+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)

def sdt(idateTime):
    """Helper function"""
    temp={}
    try:
        client.set_datetime(idateTime)
        temp['result']="Setting inverter time was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting inverter time failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def sds(payload):
    """Helper function"""
    temp={}
    try:
        client.set_discharge_slot(int(payload['slot']),[datetime.strptime(payload['start'],"%H:%M"),datetime.strptime(payload['finish'],"%H:%M")])
        update_control_mqtt("Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")))
        update_control_mqtt("Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")))
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def sdss(payload):
    """Helper function"""
    temp={}
    try:
        client.set_discharge_slot_start(int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"))
        update_control_mqtt("Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")))
        temp['result']="Setting Discharge Slot Start "+str(payload['slot'])+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Discharge Slot Start "+str(payload['slot'])+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)

def sdse(payload):
    """Helper function"""
    temp={}
    try:
        client.set_discharge_slot_end(int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"))
        update_control_mqtt("Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")))
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)

def sps(payload):
    """Helper function"""
    temp={}
    try:
        client.set_pause_slot_start(datetime.strptime(payload['start'],"%H:%M"))
        update_control_mqtt("Battery_pause_end_time_slot"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")))
        temp['result']="Setting Pause Slot Start was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Pause Slot Start failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)

def spe(payload):
    """Helper function"""
    temp={}
    try:
        client.set_pause_slot_end(datetime.strptime(payload['finish'],"%H:%M"))
        update_control_mqtt("Battery_pause_end_time_slot"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")))
        temp['result']="Setting Pause Slot End was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Pause Slot End failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)

def scs(payload):
    """Helper function"""
    temp={}
    try:
        client.set_charge_slot(int(payload['slot']),[datetime.strptime(payload['start'],"%H:%M"),datetime.strptime(payload['finish'],"%H:%M")])
        update_control_mqtt("Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")))
        update_control_mqtt("Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")))
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
def scss(payload):
    """Helper function"""
    temp={}
    try:
        client.set_charge_slot_start(int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"))
        update_control_mqtt("Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")))
        temp['result']="Setting Charge Slot Start "+str(payload['slot'])+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Slot Start "+str(payload['slot'])+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)

def scse(payload):
    """Helper function"""
    temp={}
    try:
        client.set_charge_slot_end(int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"))
        update_control_mqtt("Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")))
        temp['result']="Setting Charge Slot End "+str(payload['slot'])+" was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Slot End "+str(payload['slot'])+" failed: " + str(error)
    logger.info(temp['result'])
    return json.dumps(temp)
    
def enable_charge_schedule(payload):
    """Enable the charge schedule"""
    temp={}
    try:
        if payload['state']=="enable":
            logger.info("Enabling Charge Schedule")
            from .write import ec
            GivQueue.q.enqueue(ec,retry=Retry(max=GivSettings.queue_retries, interval=2))
        elif payload['state']=="disable":
            logger.info("Disabling Charge Schedule")
            from .write import dc
            GivQueue.q.enqueue(dc,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting charge schedule "+str(payload['state'])+" failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def enable_charge_target(payload):
    """Allow AC charge Target to function """
    temp={}
    try:
        if payload['state']=="enable":
            logger.info("Enabling Charge Target")
            from .write import ect
            GivQueue.q.enqueue(ect,retry=Retry(max=GivSettings.queue_retries, interval=2))
        elif payload['state']=="disable":
            logger.info("Disabling Charge Target")
            from .write import dct
            GivQueue.q.enqueue(dct,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Target failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def enable_discharge(payload):
    """Mimic an Enable battery discharge by setting reserve to 100% or not (Legacy)"""
    temp={}
    saved_battery_reserve = get_saved_battery_reserve_percentage()
    try:
        if payload['state']=="enable":
            logger.info("Enabling Discharge")
            from .write import ssc
            GivQueue.q.enqueue(ssc,saved_battery_reserve,retry=Retry(max=GivSettings.queue_retries, interval=2))
        elif payload['state']=="disable":
            logger.info("Disabling Discharge")
            from .write import ssc
            GivQueue.q.enqueue(ssc,100,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Discharge Enable failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def enable_discharge_schedule(payload):
    """Enable the discharge schedule"""
    temp={}
    try:
        if payload['state']=="enable":
            logger.info("Enabling Disharge Schedule")
            from .write import ed
            GivQueue.q.enqueue(ed,retry=Retry(max=GivSettings.queue_retries, interval=2))
        elif payload['state']=="disable":
            logger.info("Disabling Discharge Schedule")
            from .write import dd
            GivQueue.q.enqueue(dd,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Enable failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_shallow_charge(payload):
    """Set the shallow charge register (Legacy)"""
    temp={}
    try:
        logger.info("Setting Shallow Charge to: "+ str(payload['val']))
        from .write import ssc
        GivQueue.q.enqueue(ssc,int(payload['val']),retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting shallow charge failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_charge_target(payload):
    """Set the SOC target for AC charge during defined timeslot"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    target=int(payload['chargeToPercent'])
    try:
        logger.info("Setting Charge Target to: "+str(target))
        from .write import sct
        GivQueue.q.enqueue(sct,target,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Target failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_charge_target_2(payload):
    """Set the SOC target for AC charge during timeslot 2"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    target=int(payload['chargeToPercent'])
    slot=int(payload['slot'])
    try:
        logger.info("Setting Charge Target "+str(slot) + " to: "+str(target))
        from .write import sct2
        GivQueue.q.enqueue(sct2,target,slot,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Target "+str(slot) + " failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_battery_reserve(payload):
    """Set the battery reserve value for SOC"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    target=int(payload['reservePercent'])
    if target<4: target=4
    logger.info ("Setting battery reserve target to: " + str(target))
    try:
        from .write import ssc
        GivQueue.q.enqueue(ssc,target,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Battery Reserve failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_battery_cutoff(payload):
    """Set the battery cut-off value for SOC"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    target=int(payload['dischargeToPercent'])
    #Only allow minimum of 4%
    if target<4: target=4
    logger.info ("Setting battery cutoff target to: " + str(target))
    try:
        logger.info("Setting Battery Cutoff to: "+str(target))
        from .write import sbpr
        GivQueue.q.enqueue(sbpr,target,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Battery Cutoff failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def reboot_inverter():
    """Trigger a reboot of the inverter"""
    temp={}
    try:
        logger.info("Rebooting inverter...")
        from .write import ri
        GivQueue.q.enqueue(ri,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Reboot inverter failed: " + str(error)
        logger.error (temp['result'])
        #raise Exception
    return json.dumps(temp)

def set_active_power_rate(payload):
    """Set the active power rate for the inverter"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    target=int(payload['activePowerRate'])
    try:
        logger.info("Setting Active Power Rate to "+str(target))
        from .write import sapr
        GivQueue.q.enqueue(sapr,target,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Active Power Rate failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_charge_rate(payload):
    """Set the power limit for battery charge rate"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    # Get inverter max bat power
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        with open(GivLUT.regcache, 'rb') as inp:
            reg_cache_stack = pickle.load(inp)
            multi_output_old = reg_cache_stack[4]
        invmaxrate=multi_output_old['Invertor_Details']['Invertor_Max_Bat_Rate']
        batcap=float(multi_output_old['Invertor_Details']['Battery_Capacity_kWh'])*1000
        if int(payload['chargeRate']) < int(invmaxrate):
            target=int(min((int(payload['chargeRate'])/(batcap/2))*50,50))
        else:
            target=50
        logger.info ("Setting battery charge rate to: " + str(payload['chargeRate'])+" ("+str(target)+")")
        try:
            from .write import sbcl
            GivQueue.q.enqueue(sbcl,target,retry=Retry(max=GivSettings.queue_retries, interval=2))
        except Exception:
            error = sys.exc_info()
            temp['result']="Setting Charge Rate failed: " + str(error)
            logger.error (temp['result'])
            #raise Exception
    else:
        temp['result']="Setting Charge Rate failed: No charge rate limit available"
        logger.error (temp['result'])
    return json.dumps(temp)

def set_discharge_rate(payload):
    """Set the power limit for battery discharge rate"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    # Get inverter max bat power
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        with open(GivLUT.regcache, 'rb') as inp:
            reg_cache_stack = pickle.load(inp)
            multi_output_old = reg_cache_stack[4]
        invmaxrate=multi_output_old['Invertor_Details']['Invertor_Max_Bat_Rate']
        batcap=float(multi_output_old['Invertor_Details']['Battery_Capacity_kWh'])*1000

        if int(payload['dischargeRate']) < int(invmaxrate):
            target=int(min((int(payload['dischargeRate'])/(batcap/2))*50,50))
        else:
            target=50
        logger.info ("Setting battery discharge rate to: " + str(payload['dischargeRate'])+" ("+str(target)+")")
        try:
            from .write import sbdl
            GivQueue.q.enqueue(sbdl,target,retry=Retry(max=GivSettings.queue_retries, interval=2))
        except Exception:
            error = sys.exc_info()
            temp['result']="Setting Discharge Rate failed: " + str(error)
            logger.error (temp['result'])
    else:
        temp['result']="Setting Discharge Rate failed: No discharge rate limit available"
        logger.error (temp['result'])        
    return json.dumps(temp)

def set_charge_slot(payload):
    """Set the start and end time for a charge timeslot"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    if 'chargeToPercent' in payload.keys():
        target=int(payload['chargeToPercent'])
        from .write import sct
        GivQueue.q.enqueue(sct,target,retry=Retry(max=GivSettings.queue_retries, interval=2))
    try:
        logger.info("Setting Charge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        from .write import scs
        GivQueue.q.enqueue(scs,payload,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_charge_slot_start(payload):
    """Set the start time for a charge timeslot"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    try:
        logger.info("Setting Charge Slot "+str(payload['slot'])+" Start to: "+str(payload['start']))
        from .write import scss
        GivQueue.q.enqueue(scss,payload,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_charge_slot_end(payload):
    """Set the end time for a charge timeslot"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    try:
        logger.info("Setting Charge Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        from .write import scse
        GivQueue.q.enqueue(scse,payload,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_discharge_slot(payload):
    """Set the sat and end time for a discharge timeslot"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    if 'dischargeToPercent' in payload.keys():
        set_battery_reserve(payload)
    try:
        #strt=datetime.strptime(payload['start'],"%H:%M")
        #fnsh=datetime.strptime(payload['finish'],"%H:%M")
        logger.info("Setting Discharge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        from .write import sds
        GivQueue.q.enqueue(sds,payload,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_discharge_slot_start(payload):
    """Set the start time for a discharge timeslot"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    try:
        logger.info("Setting Discharge Slot start "+str(payload['slot'])+" Start to: "+str(payload['start']))
        from .write import sdss
        GivQueue.q.enqueue(sdss,payload,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Discharge Slot start "+str(payload['slot'])+" failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_discharge_slot_end(payload):
    """Set the end time for a discharge timeslot"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    try:
        logger.info("Setting Discharge Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        from .write import sdse
        GivQueue.q.enqueue(sdse,payload,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_pause_start(payload):
    """Set the start time for the battery Pause timeslot"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    try:
        logger.info("Setting Pause Slot Start to: "+str(payload['start']))
        from .write import sps
        GivQueue.q.enqueue(sps,payload,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Pause Slot Start failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_pause_end(payload):
    """Set the end time for the battery Pause timeslot"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    try:
        logger.info("Setting Pause Slot End to: "+str(payload['finish']))
        from .write import spe
        GivQueue.q.enqueue(spe,payload,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Pause Slot End failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)



def force_export_resume(revert):
    """Restores settings after Force Export"""
    if not isinstance(revert, dict):
        payload=json.loads(revert)
    temp={}
    try:
        payload={}
        logger.info("Reverting Force Export settings:")   
        payload['dischargeRate']=revert["dischargeRate"]
        set_discharge_rate(payload)
        payload={}
        payload['start']=revert["start_time"]
        payload['finish']=revert["end_time"]
        payload['slot']=2
        set_discharge_slot(payload)
        payoad={}
        payload['state']=revert['discharge_schedule']
        enable_discharge_schedule(payload)
        payload={}
        payload['reservePercent']=revert["reservePercent"]
        set_battery_reserve(payload)
        payload={}
        payload["mode"]=revert["mode"]
        set_battery_mode(payload)
        os.remove(".FERunning")
        update_control_mqtt("Force_Export","Normal")
    except Exception:
        error = sys.exc_info()
        temp['result']="Force Export Revert failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def force_export(export_time):
    """Temporarily forces full battery discharge for defined time"""
    temp={}
    logger.info("Forcing Export for "+str(export_time)+" minutes")
    try:
        export_time=int(export_time)
        revert={}
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                reg_cache_stack= pickle.load(inp)
            revert["dischargeRate"]=reg_cache_stack[4]["Control"]["Battery_Discharge_Rate"]
            revert["start_time"]=reg_cache_stack[4]["Timeslots"]["Discharge_start_time_slot_2"][:5]
            revert["end_time"]=reg_cache_stack[4]["Timeslots"]["Discharge_end_time_slot_2"][:5]
            revert["reservePercent"]=reg_cache_stack[4]["Control"]["Battery_Power_Reserve"]
            revert["mode"]=reg_cache_stack[4]["Control"]["Mode"]
            revert['discharge_schedule']=reg_cache_stack[4]["Control"]["Enable_Discharge_Schedule"]
        max_discharge_rate=int(reg_cache_stack[4]["Invertor_Details"]["Invertor_Max_Bat_Rate"])
        #In case somebody has set a high reserve value set the reserve rate to the default value to allow the battery to discharge
        try:
            payload={}
            payload['reservePercent']=4
            set_battery_reserve(payload) 
        except Exception:
            logger.debug("Error Setting Reserve to 4%")
        payload={}
        payload['state']="enable"
        enable_discharge_schedule(payload)
        payload={}
        payload['start']=GivLUT.get_time(datetime.now())
        payload['finish']=GivLUT.get_time(datetime.now()+timedelta(minutes=export_time))
        payload['slot']=2
        set_discharge_slot(payload)
        payload={}
        payload['mode']="Timed Export"
        set_battery_mode(payload)
        payload={}
        logger.debug("Max discharge rate for inverter is: %s", str(max_discharge_rate))
        payload['dischargeRate']=max_discharge_rate
        set_discharge_rate(payload)
        if exists(".FERunning"):    # If a forcecharge is already running, change time of revert job to new end time
            logger.info("Force Export already running, changing end time")
            revert=get_fe_args()[0]   # set new revert object and cancel old revert job
            logger.critical("new revert= %s", str(revert))
        fejob=GivQueue.q.enqueue_in(timedelta(minutes=export_time),force_export_resume,revert)
        f=open(".FERunning", 'w',encoding='ascii')
        f.write(str(fejob.id))
        f.close()
        logger.info("Force Export revert jobid is: %s",fejob.id)
        temp['result']="Export successfully forced for "+str(export_time)+" minutes"
        update_control_mqtt("Force_Export","Running")
        logger.info(temp['result'])
    except Exception:
        error = sys.exc_info()
        temp['result']="Force Export failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def force_charge_resume(revert):
    """Restores settings after Force charge"""
    if not isinstance(revert, dict):
        payload=json.loads(revert)
    payload={}
    logger.info("Reverting Force Charge Settings:")
    payload['chargeRate']=revert["chargeRate"]
    set_charge_rate(payload)
    payload={}
    payload['state']=revert["chargeScheduleEnable"]
    enable_charge_schedule(payload)
    payload={}
    payload['start']=revert["start_time"]
    payload['finish']=revert["end_time"]
    payload['chargeToPercent']=revert["targetSOC"]
    payload['slot']=1
    set_charge_slot(payload)
    os.remove(".FCRunning")
    update_control_mqtt("Force_Charge","Normal")

def cancel_job(jobid):
    """Cancels a curenty queued job in the Redis queue"""
    if jobid in GivQueue.q.scheduled_job_registry:
        GivQueue.q.scheduled_job_registry.requeue(jobid, at_front=True)
        logger.info("Cancelling scheduled task as requested")
    else:
        logger.error("Job ID: %s not found in redis queue", str(jobid))

def get_fc_args():
    """Grabs currently running Force Charge revert job arguments"""
    from rq.job import Job
    # getjobid
    f=open(".FCRunning", 'r',encoding='ascii')
    jobid=f.readline()
    f.close()
    # get the revert details from the old job
    job=Job.fetch(jobid,GivQueue.redis_connection)
    details=job.args
    logger.debug("Previous args= %s",str(details))
    GivQueue.q.scheduled_job_registry.remove(jobid) # Remove the job from the schedule
    return (details)

def get_fe_args():
    """Grabs currently running Force Export revert job arguments"""
    from rq.job import Job
    # getjobid
    f=open(".FERunning", 'r',encoding='ascii')
    jobid=f.readline()
    f.close()
    # get the revert details from the old job
    job=Job.fetch(jobid,GivQueue.redis_connection)
    details=job.args
    logger.debug("Previous args= %s",str(details))
    GivQueue.q.scheduled_job_registry.remove(jobid) # Remove the job from the schedule
    return (details)

def force_charge(chargeTime):
    """Temporarily forces Charging for a set time"""
    temp={}
    logger.info("Forcing Charge for %s minutes",str(chargeTime))
    try:
        chargeTime=int(chargeTime)
        payload={}
        revert={}
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                reg_cache_stack= pickle.load(inp)
            revert["start_time"]=reg_cache_stack[4]["Timeslots"]["Charge_start_time_slot_1"][:5]
            revert["end_time"]=reg_cache_stack[4]["Timeslots"]["Charge_end_time_slot_1"][:5]
            revert["chargeRate"]=reg_cache_stack[4]["Control"]["Battery_Charge_Rate"]
            revert["targetSOC"]=reg_cache_stack[4]["Control"]["Target_SOC"]
            revert["chargeScheduleEnable"]=reg_cache_stack[4]["Control"]["Enable_Charge_Schedule"]
        maxChargeRate=int(reg_cache_stack[4]["Invertor_Details"]["Invertor_Max_Bat_Rate"])

        payload['chargeRate']=maxChargeRate
        set_charge_rate(payload)
        payload={}
        payload['state']="enable"
        enable_charge_schedule(payload)
        payload={}
        payload['start']=GivLUT.get_time(datetime.now())
        payload['finish']=GivLUT.get_time(datetime.now()+timedelta(minutes=chargeTime))
        payload['chargeToPercent']=100
        payload['slot']=1
        set_charge_slot(payload)
        if exists(".FCRunning"):    # If a forcecharge is already running, change time of revert job to new end time
            logger.info("Force Charge already running, changing end time")
            revert=get_fc_args()[0]   # set new revert object and cancel old revert job
            logger.critical("New revert= %s", str(revert))
        fcjob=GivQueue.q.enqueue_in(timedelta(minutes=chargeTime),force_charge_resume,revert)
        f=open(".FCRunning", 'w',encoding='ascii')
        f.write(str(fcjob.id))
        f.close()
        logger.info("Force Charge revert jobid is: %s",fcjob.id)
        temp['result']="Charge successfully forced for %s minutes",str(chargeTime)
        update_control_mqtt("Force_Charge","Running")
        logger.info(temp['result'])
    except Exception:
        error = sys.exc_info()
        temp['result']="Force charge failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def tmp_pd_resume(payload):
    """Restores setings at end of temporarily pausing Discharging for a set time"""
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    temp={}
    try:
        logger.info("Reverting Temp Pause Discharge")
        set_discharge_rate(payload)
        if exists(".tpdRunning"):
            os.remove(".tpdRunning")
        temp['result']="Temp Pause Discharge Reverted"
        update_control_mqtt("Temp_Pause_Discharge","Normal")
        logger.info(temp['result'])
    except Exception:
        error = sys.exc_info()
        temp['result']="Temp Pause Discharge Resume failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def temp_pause_discharge(pauseTime):
    """Temporarily pauses Discharging for a set time"""
    temp={}
    try:
        pauseTime=int(pauseTime)
        logger.info("Pausing Discharge for %s minutes",str(pauseTime))
        payload={}
        payload['dischargeRate']=0
        set_discharge_rate(payload)
        #Update read data via pickle
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                reg_cache_stack= pickle.load(inp)
            revert_rate=reg_cache_stack[4]["Control"]["Battery_Discharge_Rate"]
        else:
            revert_rate=2600
        payload['dischargeRate']=revert_rate
        delay=float(pauseTime*60)
        tpdjob=GivQueue.q.enqueue_in(timedelta(seconds=delay),tmp_pd_resume,payload)
        with open(".tpdRunning", 'w',encoding='ascii') as f:
            f.write(str(tpdjob.id))
        logger.info("Temp Pause Discharge revert jobid is: %s",tpdjob.id)
        temp['result']="Discharge paused for %s seconds",str(delay)
        update_control_mqtt("Temp_Pause_Discharge","Running")
        logger.info(temp['result'])
    except Exception:
        error = sys.exc_info()
        temp['result']="Pausing Discharge failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def tmp_pc_resume(payload):
    """Restores setings at end of temporarily pausing Charging for a set time"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    try:
        logger.info("Reverting Temp Pause Charge...")
        set_charge_rate(payload)
        if exists(".tpcRunning"):
            os.remove(".tpcRunning")
        temp['result']="Temp Pause Charge Reverted"
        update_control_mqtt("Temp_Pause_Charge","Normal")
        logger.info(temp['result'])
    except Exception:
        error = sys.exc_info()
        temp['result']="Temp Pause Charge Resume failed: "+ str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def temp_pause_charge(pauseTime):
    """Temporarily pauses Charging for a set time"""
    temp={}
    try:
        logger.info("Pausing Charge for %s minutes",str(pauseTime))
        payload={}
        payload['chargeRate']=0
        set_charge_rate(payload)
        #Update read data via pickle
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                reg_cache_stack= pickle.load(inp)
            revert_rate=reg_cache_stack[4]["Control"]["Battery_Charge_Rate"]
        else:
            revert_rate=2600
        payload['chargeRate']=revert_rate
        delay=float(pauseTime*60)
        tpcjob=GivQueue.q.enqueue_in(timedelta(seconds=delay),tmp_pc_resume,payload)
        with open(".tpcRunning", 'w',encoding='ascii') as f:
            f.write(str(tpcjob.id))
        logger.info("Temp Pause Charge revert jobid is: %s",tpcjob.id)
        temp['result']="Charge paused for "+str(delay)+" seconds"
        update_control_mqtt("Temp_Pause_Charge","Running")
        logger.info(temp['result'])
        logger.debug("Result is: %s",temp['result'])
    except Exception:
        error = sys.exc_info()
        temp['result']="Pausing Charge failed: " + str(error)
        logger.error(temp['result'])
    return json.dumps(temp)

def set_battery_power_mode(payload):
    """Toggles the Eco mode to mimic the portal control"""
    temp={}
    logger.info("Setting Battery Power Mode to: %s",str(payload['state']))
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    if payload['state']=="enable":
        from .write import sbdmd
        GivQueue.q.enqueue(sbdmd,retry=Retry(max=GivSettings.queue_retries, interval=2))
    else:
        from .write import sbdmmp
        GivQueue.q.enqueue(sbdmmp,retry=Retry(max=GivSettings.queue_retries, interval=2))
    temp['result']="Setting Battery Power Mode to "+str(payload['state'])+" was a success"
    
    return json.dumps(temp)

def set_battery_pause_mode(payload):
    """Toggle the "Forbid" flag to pause charge/discharge/both"""
    temp={}
    logger.info("Setting Battery Pause Mode to: %s",str(payload['state']))
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    if payload['state'] in GivLUT.battery_pause_mode:
        val=GivLUT.battery_pause_mode.index(payload['state'])
        from .write import sbpm
        GivQueue.q.enqueue(sbpm,val,retry=Retry(max=GivSettings.queue_retries, interval=2))
        temp['result']="Setting Battery Pause Mode to "+str(payload['state'])+" was a success"    
    else:
        logger.error ("Invalid Mode requested: %s", payload['state'])
        temp['result']="Invalid Mode requested"
    return json.dumps(temp)

def set_local_control_mode(payload):
    """Sets the priority for PV destination"""
    temp={}
    logger.info("Setting Local Control Mode to: %s",str(payload['state']))
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    if payload['state'] in GivLUT.local_control_mode:
        val=GivLUT.local_control_mode.index(payload['state'])
        from .write import slcm
        GivQueue.q.enqueue(slcm,val,retry=Retry(max=GivSettings.queue_retries, interval=2))
    else:
        logger.error ("Invalid Mode requested: %s", payload['state'])
        temp['result']="Invalid Mode requested"
    return json.dumps(temp)

def set_battery_mode(payload):
    """Sets the Battery mode to replicate the portal 'modes'"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    logger.info("Setting Battery Mode to: %s",str(payload['mode']))
    #Update read data via pickle
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        with open(GivLUT.regcache, 'rb') as inp:
            reg_cache_stack= pickle.load(inp)
    logger.debug("Current battery mode from pickle is: %s", str(reg_cache_stack[4]["Control"]["Mode"] ))
    try:
        if payload['mode']=="Eco":
            from .write import smd
            GivQueue.q.enqueue(smd,retry=Retry(max=GivSettings.queue_retries, interval=2))
            from .write import ssc
            saved_battery_reserve = get_saved_battery_reserve_percentage()
            GivQueue.q.enqueue(ssc,saved_battery_reserve,retry=Retry(max=GivSettings.queue_retries, interval=2))
        elif payload['mode']=="Eco (Paused)":
            from .write import smd
            GivQueue.q.enqueue(smd,retry=Retry(max=GivSettings.queue_retries, interval=2))
            from .write import ssc
            GivQueue.q.enqueue(ssc,100,retry=Retry(max=GivSettings.queue_retries, interval=2))
        elif payload['mode']=="Timed Demand":
            from .write import sbdmd, ed
            GivQueue.q.enqueue(sbdmd,retry=Retry(max=GivSettings.queue_retries, interval=2))
            GivQueue.q.enqueue(ed,retry=Retry(max=GivSettings.queue_retries, interval=2))
        elif payload['mode']=="Timed Export":
            from .write import sbdmmp,ed
            GivQueue.q.enqueue(sbdmmp,retry=Retry(max=GivSettings.queue_retries, interval=2))
            GivQueue.q.enqueue(ed,retry=Retry(max=GivSettings.queue_retries, interval=2))
        else:
            logger.error ("Invalid Mode requested: %s", payload['mode'])
            temp['result']="Invalid Mode requested"
            return json.dumps(temp)
        temp['result']="Setting Battery Mode was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Battery Mode failed: %s", str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_pv_input_mode(payload):
    """Sets the PV MPPT mode"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    logger.info("Setting PV Input mode to: %s", str(payload['state']))
    try:
        if payload['state'] in GivLUT.pv_input_mode:
            from .write import spvim
            GivQueue.q.enqueue(spvim,GivLUT.pv_input_mode.index(payload['state']),retry=Retry(max=GivSettings.queue_retries, interval=2))
        else:
            logger.error ("Invalid Mode requested: %s", payload['state'])
            temp['result']="Invalid Mode requested"
        temp['result']="Setting PV Input Mode was a success"
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting PV Input Mode failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def set_date_time(payload):
    """Sets Inverter time"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    #convert payload to dateTime components
    try:
        iDateTime=datetime.strptime(payload['dateTime'],"%d/%m/%Y %H:%M:%S")   #format '12/11/2021 09:15:32'
        logger.info("Setting inverter time to: %s",iDateTime)
        #Set Date and Time on inverter
        from .write import sdt
        GivQueue.q.enqueue(sdt,iDateTime,retry=Retry(max=GivSettings.queue_retries, interval=2))
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting inverter DateTime failed: " + str(error) 
        logger.error (temp['result'])
    return json.dumps(temp)

def switch_rate(payload):
    """Switches tarriff rate between day and night"""
    temp={}
    if not isinstance(payload, dict):
        payload=json.loads(payload)
    if GivSettings.dynamic_tariff is False:     # Only allow this control if Dynamic control is enabled
        temp['result']="External rate setting not allowed. Enable Dynamic Tariff in settings"
        logger.error(temp['result'])
        return json.dumps(temp)
    try:
        if payload.lower()=="day":
            open(GivLUT.dayRateRequest, 'w',encoding='ascii').close()
            logger.info ("Setting dayRate via external trigger")
        else:
            open(GivLUT.nightRateRequest, 'w',encoding='ascii').close()
            logger.info ("Setting nightRate via external trigger")
    except Exception:
        error = sys.exc_info()
        temp['result']="Setting Rate failed: " + str(error)
        logger.error (temp['result'])
    return json.dumps(temp)

def reboot_addon():
    """Reboots the entire Addon if in HA"""
    logger.critical("Restarting the GivTCP Addon in 5s...")
    time.sleep(5)
    access_token = os.getenv("SUPERVISOR_TOKEN")
    url="http://supervisor/addons/self/restart"
    result = requests.post(url,
          headers={'Content-Type':'application/json',
                   'Authorization': 'Bearer {}'.format(access_token)},timeout=10)

def get_saved_battery_reserve_percentage():
    """grab the stored battery reserve level"""
    saved_battery_reserve=4
    if exists(GivLUT.reservepkl):
        with open(GivLUT.reservepkl, 'rb') as inp:
            saved_battery_reserve= pickle.load(inp)
    return saved_battery_reserve

if __name__ == '__main__':
    if len(sys.argv)==2:
        globals()[sys.argv[1]]()
    elif len(sys.argv)==3:
        globals()[sys.argv[1]](sys.argv[2])

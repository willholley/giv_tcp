# -*- coding: utf-8 -*-
# version 2022.01.31
import sys
import json
import logging
import datetime
from datetime import datetime, timedelta
from settings import GiV_Settings
import settings
import time
from os.path import exists
import pickle,os
from GivLUT import GivLUT, GivQueue
from read import finditem
from givenergy_modbus_async.client.client import Client
from givenergy_modbus_async.client import commands
from givenergy_modbus_async.model import TimeSlot
from givenergy_modbus.client import GivEnergyClient
from givenergy_modbus_async.pdu import WriteHoldingRegisterResponse
from rq import Retry
from mqtt import GivMQTT
import requests
import importlib
import asyncio

logging.getLogger("givenergy_modbus_async").setLevel(logging.CRITICAL)
client=GivEnergyClient(host=GiV_Settings.invertorIP)

logger = GivLUT.logger

def frtouch():
    with open(".fullrefresh",'w') as fp:
        pass

def updateControlCache(entity,value,isTime: bool=False):
    # immediately update broker on success of control áction
    importlib.reload(settings)
    from settings import GiV_Settings
    if GiV_Settings.MQTT_Topic == "":
        GiV_Settings.MQTT_Topic = "GivEnergy"
    if isTime:
        Topic=str(GiV_Settings.MQTT_Topic+"/"+GiV_Settings.serial_number+"/Timeslots/")+str(entity)
        value=value.split(" ")[1]
    else:
        Topic=str(GiV_Settings.MQTT_Topic+"/"+GiV_Settings.serial_number+"/Control/")+str(entity)
    logger.debug("Pushing control update to mqtt: "+Topic+" - "+str(value))
    GivMQTT.single_MQTT_publish(Topic,str(value))

    # now update the pkl cache file
    with GivLUT.cachelock:
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack = pickle.load(inp)
            #find right object
            if isTime:
                regCacheStack[4]['Timeslots'][entity]=value
            else:
                regCacheStack[4]['Control'][entity]=value
            with open(GivLUT.regcache, 'wb') as outp:
                pickle.dump(regCacheStack, outp, pickle.HIGHEST_PROTOCOL)
            logger.debug("Pushing control update to pkl cache: "+entity+" - "+str(value))
    return

async def sendAsyncCommand(reqs):
    output={}
    asyncclient=Client(host=GiV_Settings.invertorIP,port=8899)
    await asyncclient.connect()
    result= await asyncclient.execute(reqs,timeout=3,retries=10, return_exceptions=True)
    for req in result:
        if not isinstance(req,WriteHoldingRegisterResponse):
            output['error']="Error in write command"
            output['error_type']=type(req).__name__
            break
    await asyncclient.close()
    return output

async def sct(target):
    """ Not suitable for AIO, use sst()"""
    temp={}
    try:
        #client.enable_charge_target(target)
        reqs=commands.set_charge_target(int(target))
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Target_SOC",target)
        temp['result']="Setting Charge Target "+str(target)+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Charge Target "+str(target)+" failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)


async def sst(target,slot,EMS):
    temp={}
    try:
        reqs=commands.set_soc_target(False,slot,int(target),EMS)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        if EMS:
            updateControlCache("EMS_Charge_Target_SOC_"+str(slot),target)
        else:
            updateControlCache("Charge_Target_SOC_"+str(slot),target)
        temp['result']="Setting Charge Target "+str(slot) + " was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Charge Target "+str(slot) + " failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def sest(target,slot):
    temp={}
    try:
        reqs=commands.set_export_soc_target(False,slot,int(target))
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Export_Target_SOC_"+str(slot),target)
        temp['result']="Setting Export Target "+str(slot) + " was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Export Target "+str(slot) + " failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def sdct(target,slot,EMS):
    temp={}
    try:
        reqs=commands.set_soc_target(True,slot,int(target),EMS)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        if EMS:
            updateControlCache("EMS_Discharge_Target_SOC_"+str(slot),target)
        else:
            updateControlCache("Discharge_Target_SOC_"+str(slot),target)
        temp['result']="Setting Discharge Target "+str(slot) + " was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Discharge Target "+str(slot) + " failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def ect():
    temp={}
    try:
        reqs=commands.enable_charge_target()
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception           
        temp['result']="Enabling Charge Target was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Enabling Charge Target failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def dct():
    temp={}
    try:
        reqs=commands.disable_charge_target()
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception   
        updateControlCache("Target_SOC",100)
        temp['result']="Disabling Charge Target was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Disabling Charge Target failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def ed():
    temp={}
    try:
        reqs=commands.set_enable_discharge(True)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception   
        updateControlCache("Enable_Discharge_Schedule","enable")
        temp['result']="Enabling Discharge Schedule was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Enabling Discharge Schedule failed"+str(result['error_type'])
        logger.error(temp['result'])   
    return json.dumps(temp)

async def dd():
    temp={}
    try:
        reqs=commands.set_enable_discharge(False)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception   
        updateControlCache("Enable_Discharge_Schedule","disable")
        temp['result']="Disabling Discharge Schedule was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Disabling Discharge Schedule failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def ec():
    temp={}
    try:
        reqs=commands.set_enable_charge(True)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception        
        updateControlCache("Enable_Charge_Schedule","enable")
        temp['result']="Enabling Charge Schedule was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Enabling Charge Schedule failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def dc():
    temp={}
    try:
        reqs=commands.set_enable_charge(False)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception 
        updateControlCache("Enable_Charge_Schedule","disable")
        temp['result']="Disabling Charge Schedule was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Disabling Charge Schedule failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

def slcm(val):
    temp={}
    try:
        client.set_local_control_mode(val)
        updateControlCache("Local_control_mode",str(GivLUT.local_control_mode[int(val)]))
        temp['result']="Setting Local Control Mode to " +str(GivLUT.local_control_mode[val])+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Local Control Mode to " +str(GivLUT.local_control_mode[val])+" failed"
        logger.error(temp['result'])
    return json.dumps(temp)

async def sbpm(val):
    temp={}
    try:
        
        reqs=commands.set_battery_pause_mode(val)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception 
        updateControlCache("Battery_pause_mode",str(GivLUT.battery_pause_mode[int(val)]))
        temp['result']="Setting Battery Pause Mode to " +str(GivLUT.battery_pause_mode[val])+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Battery Pause Mode to " +str(GivLUT.battery_pause_mode[val])+" failed"
        logger.error(temp['result'])
    return json.dumps(temp)
    #return temp

async def ssc(target):
    temp={}
    try:
        
        reqs=commands.set_battery_soc_reserve(target)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Power_Reserve",target)
        temp['result']="Setting shallow charge "+str(target)+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting shallow charge "+str(target)+" failed"
        logger.error(temp['result'])
    return json.dumps(temp)
async def sbpr(target):
    temp={}
    try:
        
        reqs=commands.set_battery_power_reserve(target)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Power_Cutoff",target)
        temp['result']="Setting battery power reserve to "+str(target)+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting battery power reserve "+str(target)+" failed"
        logger.error(temp['result'])
    return json.dumps(temp)
async def ri():
    temp={}
    try:
        
        reqs=commands.set_inverter_reboot()
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        temp['result']="Rebooting Inverter was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Rebooting Inverter failed"
        logger.error(temp['result'])
    return json.dumps(temp)

async def sapr(target):
    temp={}
    try:
        
        reqs=commands.set_active_power_rate(target)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Active_Power_Rate",target)
        temp['result']="Setting active power rate "+str(target)+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting active power rate "+str(target)+" failed"
        logger.error(temp['result'])
    return json.dumps(temp)
async def sbcl(target):
    temp={}
    try:
        reqs=commands.set_battery_charge_limit(target)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        # Get cache and work out rate
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack = pickle.load(inp)
                multi_output_old = regCacheStack[4]
                batteryCapacity=int(multi_output_old[finditem(multi_output_old,"Invertor_Serial_Number")]['Battery_Capacity_kWh'])*1000
                batmaxrate=int(multi_output_old[finditem(multi_output_old,"Invertor_Serial_Number")]['Invertor_Max_Bat_Rate'])
            val=int(min((target/100)*(batteryCapacity), batmaxrate))
            updateControlCache("Battery_Charge_Rate",val)
        temp['result']="Setting battery charge rate "+str(target)+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting battery charge rate "+str(target)+" failed"
        logger.error(temp['result'])
    return json.dumps(temp)
async def sbcla(target):
    temp={}
    try:
        reqs=commands.set_battery_charge_limit_ac(target)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Charge_Rate_AC",target)
        temp['result']="Setting battery charge rate AC to "+str(target)+"% was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting battery charge rate "+str(target)+" failed"
        logger.error(temp['result'])
    return json.dumps(temp)

async def sbdl(target):
    temp={}
    try:
        reqs=commands.set_battery_discharge_limit(target)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        # Get cache and work out rate
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack = pickle.load(inp)
                multi_output_old = regCacheStack[4]
                batteryCapacity=int(multi_output_old[finditem(multi_output_old,'Invertor_Serial_Number')]['Battery_Capacity_kWh'])*1000
                batmaxrate=int(multi_output_old[finditem(multi_output_old,'Invertor_Serial_Number')]['Invertor_Max_Bat_Rate'])
            val=int(min((target/100)*(batteryCapacity), batmaxrate))
            updateControlCache("Battery_Discharge_Rate",val)
        temp['result']="Setting battery discharge limit "+str(target)+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting battery discharge limit "+str(target)+" failed"
        logger.error(temp['result'])   
    return json.dumps(temp)

async def sbdla(target):
    temp={}
    try:
        
        reqs=commands.set_battery_discharge_limit_ac(target)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Discharge_Rate_AC",target)
        temp['result']="Setting battery discharge rate AC to "+str(target)+"% was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting battery discharge rate "+str(target)+" failed"
        logger.error(temp['result'])
    return json.dumps(temp)
async def smd(paused):
    temp={}
    try:
        
        reqs=commands.set_mode_dynamic(paused)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        #updateControlCache("Mode","Eco")
        temp['result']="Setting dynamic mode was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting dynamic mode failed"
        logger.error(temp['result'])
    return json.dumps(temp)
async def sms(target):
    temp={}
    try:
        
        reqs=commands.set_mode_storage(discharge_for_export=False)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        temp['result']="Setting storage mode "+str(target)+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting storage mode "+str(target)+" failed"
        logger.error(temp['result'])
    return json.dumps(temp)
async def sbdmd():
    temp={}
    try:
        
        reqs=commands.set_mode_storage(discharge_for_export=False)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Mode","Timed Demand")
        temp['result']="Setting demand mode was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting demand mode failed"
        logger.error(temp['result'])
    return json.dumps(temp)
async def sbdmmp():
    temp={}
    try:
        
        reqs=commands.set_mode_storage(discharge_for_export=True)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Mode","Timed Export")
        temp['result']="Setting export mode was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting export mode failed"
        logger.error(temp['result'])   
    return json.dumps(temp)

def spvim(val):
    temp={}
    try:
        client.set_pv_input_mode(val)
        updateControlCache("PV_input_mode",str(GivLUT.pv_input_mode[int(val)]))
        temp['result']="Setting PV Input mode to "+str(GivLUT.pv_input_mode[val])+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting PV Input mode to "+str(GivLUT.pv_input_mode[val])+" failed"
        logger.error(temp['result'])  
    return json.dumps(temp)

async def sccb(val):
    temp={}
    try:
        reqs=commands.set_car_charge_boost(discharge_for_export=True)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Car_Charge_Boost",val)
        temp['result']="Setting Car Charge Boost to "+str(val)+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Car Charge Boost to "+str(val)+" failed"+str(result['error_type'])
        logger.error(temp['result'])  
    return json.dumps(temp)

async def sel(val):
    temp={}
    try:
        reqs=commands.set_export_limit(discharge_for_export=True)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Export_Power_Limit",val)
        temp['result']="Setting Car Charge Boost to "+str(val)+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Car Charge Boost to "+str(val)+" failed"+str(result['error_type'])
        logger.error(temp['result'])  
    return json.dumps(temp)

async def sdt(idateTime):
    temp={}
    try:
        
        reqs=commands.set_system_date_time(idateTime)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        temp['result']="Setting inverter time was a success"
        updateControlCache("Invertor_Time",idateTime)
        logger.info(temp['result'])
    except:
        temp['result']="Setting inverter time failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def sds(payload):
    temp={}
    try:
        # create Timeslot object forslot in func
        slot=TimeSlot
        slot.start=datetime.strptime(payload['start'],"%H:%M")
        slot.end=datetime.strptime(payload['finish'],"%H:%M")
        if "EMS" in payload:
            EMS=payload['EMS']
        else:
            EMS=False
        reqs=commands._set_charge_slot(True,int(payload['slot']),slot,EMS)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        if EMS:
            updateControlCache("EMS_Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("EMS_Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def sbc(val):
    temp={}
    try:
        reqs=commands.set_calibrate_battery_soc(int(val))
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Calibration",str(GivLUT.battery_calibration[val]))
        temp['result']="Setting Battery Calibration "+str(val)+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Battery Calibration "+str(val)+" failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def ses(payload):
    temp={}
    try:
        # create Timeslot object forslot in func
        slot=TimeSlot
        slot.start=datetime.strptime(payload['start'],"%H:%M")
        slot.end=datetime.strptime(payload['finish'],"%H:%M")
        reqs=commands.set_export_slot(int(payload['slot']),slot)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Export_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        updateControlCache("Export_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Export Slot "+str(payload['slot'])+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def sdss(payload):
    temp={}
    try:
        if "EMS" in payload:
            EMS=payload['EMS']
        else:
            EMS=False
        reqs=commands.set_charge_slot_start(True,int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"),EMS)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        if EMS:
            updateControlCache("EMS_Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        else:
            updateControlCache("Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Discharge Slot Start "+str(payload['slot'])+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Discharge Slot Start "+str(payload['slot'])+" failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def sdse(payload):
    temp={}
    try:
        if "EMS" in payload:
            EMS=payload['EMS']
        else:
            EMS=False
        reqs=commands.set_charge_slot_end(True,int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"),EMS)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        if EMS:
            updateControlCache("EMS_Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def sps(payload):
    temp={}
    try:
        slot=TimeSlot
        slot.start=datetime.strptime(payload['start'],"%H:%M")
        slot.end=datetime.strptime(payload['finish'],"%H:%M")
        
        reqs=commands.set_pause_slot(slot)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_pause_start_time_slot",str(datetime.strptime(payload['start'],"%H:%M")))
        updateControlCache("Battery_pause_end_time_slot",str(datetime.strptime(payload['finish'],"%H:%M")))
        temp['result']="Setting Battery Pause Slot was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Battery Pause Slot failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def spss(payload):
    temp={}
    try:
        
        reqs=commands.set_pause_slot_start(datetime.strptime(payload['start'],"%H:%M"))
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_pause_start_time_slot",str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Pause Slot Start was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Pause Slot Start failed: " + str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def spse(payload):
    temp={}
    try:
        reqs=commands.set_pause_slot_end(datetime.strptime(payload['finish'],"%H:%M"))
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_pause_end_time_slot",str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Pause Slot End was a success"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Pause Slot End failed: " + str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def scs(payload):
    temp={}
    try:
        slot=TimeSlot
        slot.start=datetime.strptime(payload['start'],"%H:%M")
        slot.end=datetime.strptime(payload['finish'],"%H:%M")
        if "EMS" in payload:
            EMS=payload['EMS']
        else:
            EMS=False
        reqs=commands._set_charge_slot(False,int(payload['slot']),slot,EMS)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        if EMS:
            updateControlCache("EMS_Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("EMS_Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed"+str(result['error_type'])
        logger.error(temp['result'])   
    return json.dumps(temp)

async def sess(payload):
    temp={}
    try:
        reqs=commands.set_export_slot_start(int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"))
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception        
        updateControlCache("Export_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Export Slot Start "+str(payload['slot'])+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Export Slot Start "+str(payload['slot'])+" failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def sese(payload):
    temp={}
    try:
        
        reqs=commands.set_export_slot_end(int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"))
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception         
        updateControlCache("Export_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Export Slot End "+str(payload['slot'])+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Export Slot End "+str(payload['slot'])+" failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def scss(payload):
    temp={}
    try:
        if "EMS" in payload:
            EMS=payload['EMS']
        else:
            EMS=False
        reqs=commands.set_charge_slot_start(False,int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"),EMS)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        if EMS:
            updateControlCache("EMS_Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        else:
            updateControlCache("Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Charge Slot Start "+str(payload['slot'])+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Charge Slot Start "+str(payload['slot'])+" failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)

async def scse(payload):
    temp={}
    try:
        if "EMS" in payload:
            EMS=payload['EMS']
        else:
            EMS=False
        reqs=commands.set_charge_slot_end(False,int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"),EMS)
        result= await sendAsyncCommand(reqs)
        if 'error' in result:
            raise Exception
        if EMS:
            updateControlCache("EMS_Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Charge Slot End "+str(payload['slot'])+" was a success"
        logger.info(temp['result'])
    except:
        temp['result']="Setting Charge Slot End "+str(payload['slot'])+" failed"+str(result['error_type'])
        logger.error(temp['result'])
    return json.dumps(temp)
    
def enableChargeSchedule(payload):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Charge Schedule")
            temp= asyncio.run(ec())
        elif payload['state']=="disable":
            logger.debug("Disabling Charge Schedule")
            temp= asyncio.run(dc())
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting charge schedule "+str(payload['state'])+" failed" + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def enableChargeTarget(payload):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Charge Target")
            temp= asyncio.run(ect())
        elif payload['state']=="disable":
            logger.debug("Disabling Charge Target")
            temp= asyncio.run(dct())
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Target failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def enableDischarge(payload):
    temp={}
    saved_battery_reserve = getSavedBatteryReservePercentage()
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Discharge")
            temp= asyncio.run(ssc(saved_battery_reserve))
        elif payload['state']=="disable":
            logger.debug("Disabling Discharge")
            temp= asyncio.run(ssc(100))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Enable failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def enableDischargeSchedule(payload):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Disharge Schedule")
            temp= asyncio.run(ed())
        elif payload['state']=="disable":
            logger.debug("Disabling Discharge Schedule")
            temp= asyncio.run(dd())
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Enable failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setShallowCharge(payload):
    temp={}
    try:
        logger.debug("Setting Shallow Charge to: "+ str(payload['val']))
        temp= asyncio.run(ssc(int(payload['val'])))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting shallow charge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setChargeTarget(payload):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['chargeToPercent'])
        logger.debug("Setting Charge Target to: "+str(target))
        temp= asyncio.run(sct(target))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Target failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setChargeTarget2(payload):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['chargeToPercent'])
        slot=int(payload['slot'])
        EMS=bool(payload['EMS'])
        logger.debug("Setting Charge Target "+str(slot) + " to: "+str(target))
        temp= asyncio.run(sst(target,slot,EMS))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Target "+str(slot) + " failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setExportTarget(payload):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['exportToPercent'])
        slot=int(payload['slot'])
        logger.debug("Setting Export Target "+str(slot) + " to: "+str(target))
        temp= asyncio.run(sest(target,slot))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Target "+str(slot) + " failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setDischargeTarget(payload):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['dischargeToPercent'])
        slot=int(payload['slot'])
        EMS=bool(payload['EMS'])
        logger.debug("Setting Discharge Target "+str(slot) + " to: "+str(target))
        temp= asyncio.run(sdct(target,slot,EMS))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Target "+str(slot) + " failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setBatteryReserve(payload):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        #target=int(payload['dischargeToPercent'])
        target=int(payload['reservePercent'])
        #Only allow minimum of 4%
        if target<4: target=4
        logger.debug ("Setting battery reserve target to: " + str(target))
        temp= asyncio.run(ssc(target))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Reserve failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setBatteryCutoff(payload):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['dischargeToPercent'])
        #Only allow minimum of 4%
        if target<4: target=4
        logger.debug ("Setting battery cutoff target to: " + str(target))
        temp= asyncio.run(sbpr(target))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Cutoff failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def rebootinverter():
    temp={}
    try:
        logger.debug("Rebooting inverter...")
        temp= asyncio.run(ri())
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Reboot inverter failed: " + str(e)
        logger.error (temp['result'])
        #raise Exception
    return json.dumps(temp)

def setActivePowerRate(payload):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['activePowerRate'])
        logger.debug("Setting Active Power Rate to "+str(target))
        temp= asyncio.run(sapr(target))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Active Power Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setChargeRate(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)

    # Get inverter max bat power
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        with open(GivLUT.regcache, 'rb') as inp:
            regCacheStack = pickle.load(inp)
            multi_output_old = regCacheStack[4]
        invmaxrate=finditem(multi_output_old,'Invertor_Max_Bat_Rate')
        batcap=float(finditem(multi_output_old,'Battery_Capacity_kWh'))*1000
        try:
            if int(payload['chargeRate']) < int(invmaxrate):
                target=int(min((int(payload['chargeRate'])/(batcap/2))*50,50))
            else:
                target=50
            logger.debug ("Setting battery charge rate to: " + str(payload['chargeRate'])+" ("+str(target)+")")
            temp= asyncio.run(sbcl(target))
        except:
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            temp['result']="Setting Charge Rate failed: " + str(e)
            logger.error (temp['result'])
            #raise Exception
    else:
        temp['result']="Setting Charge Rate failed: No charge rate limit available"
        logger.error (temp['result'])
    return json.dumps(temp)
####################################

def setChargeRateAC(payload):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['chargeRate'])
        logger.debug ("Setting AC battery charge rate to: " + str(target))
        temp= asyncio.run(sbcla(target))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting AC Battery Charge Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setDischargeRate(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    # Get inverter max bat power
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        with open(GivLUT.regcache, 'rb') as inp:
            regCacheStack = pickle.load(inp)
            multi_output_old = regCacheStack[4]
        invmaxrate=int(finditem(multi_output_old,"Invertor_Max_Bat_Rate"))
        batcap=float(finditem(multi_output_old,'Battery_Capacity_kWh'))*1000
        try:
            if int(payload['dischargeRate']) < int(invmaxrate):
                target=int(min((int(payload['dischargeRate'])/(batcap/2))*50,50))
            else:
                target=50
            logger.debug ("Setting battery discharge rate to: " + str(payload['dischargeRate'])+" ("+str(target)+")")
            temp= asyncio.run(sbdl(target))
        except:
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            temp['result']="Setting Discharge Rate failed: " + str(e)
            logger.error (temp['result'])
    else:
        temp['result']="Setting Discharge Rate failed: No discharge rate limit available"
        logger.error (temp['result'])        
    return json.dumps(temp)

def setDischargeRateAC(payload):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['dischargeRate'])
        logger.debug ("Setting AC battery discharge rate to: " + str(target))
        temp= asyncio.run(sbdla(target))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting AC battery discharge Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setChargeSlot(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    if 'chargeToPercent' in payload.keys():
        target=int(payload['chargeToPercent'])
        temp= asyncio.run(sct(target))
    try:
        logger.debug("Setting Charge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        temp= asyncio.run(scs(payload))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setPauseSlot(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Battery Pause slot to: "+str(payload['start'])+" - "+str(payload['finish']))
        temp= asyncio.run(sps(payload))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Pause Slot failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setChargeSlotStart(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Charge Slot "+str(payload['slot'])+" Start to: "+str(payload['start']))
        temp= asyncio.run(scss(payload))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setChargeSlotEnd(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Charge Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        temp= asyncio.run(scse(payload))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setExportSlotStart(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Export Slot "+str(payload['slot'])+" Start to: "+str(payload['start']))
        temp= asyncio.run(sess(payload))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setExportSlotEnd(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Export Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        temp= asyncio.run(sese(payload))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setDischargeSlot(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    # Should this include DischargePercent, or drop?
    if 'dischargeToPercent' in payload.keys():
        pload={}
        pload['reservePercent']=payload['dischargeToPercent']
        result=setBatteryReserve(pload)
    try:
        strt=datetime.strptime(payload['start'],"%H:%M")
        fnsh=datetime.strptime(payload['finish'],"%H:%M")
        logger.debug("Setting Discharge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        temp= asyncio.run(sds(payload))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setExportSlot(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        strt=datetime.strptime(payload['start'],"%H:%M")
        fnsh=datetime.strptime(payload['finish'],"%H:%M")
        logger.debug("Setting Export Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        temp= asyncio.run(ses(payload))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setDischargeSlotStart(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Discharge Slot start "+str(payload['slot'])+" Start to: "+str(payload['start']))
        temp= asyncio.run(sdss(payload))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Slot start "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setDischargeSlotEnd(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Discharge Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        temp= asyncio.run(sdse(payload))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setPauseStart(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Pause Slot Start to: "+str(payload['start']))
        temp= asyncio.run(sps(payload))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Pause Slot Start failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setPauseEnd(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Pause Slot End to: "+str(payload['finish']))
        temp= asyncio.run(spse(payload))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Pause Slot End failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def FEResume(revert):
    temp={}
    try:
        payload={}
        logger.debug("Reverting Force Export settings:")   
        payload['dischargeRate']=revert["dischargeRate"]
        result=setDischargeRate(payload)
        payload={}
        payload['start']=revert["start_time"]
        payload['finish']=revert["end_time"]
        payload['slot']=2
        result=setDischargeSlot(payload)
        payoad={}
        payload['state']=revert['discharge_schedule']
        result=enableDischargeSchedule(payload)
        payload={}
        payload['reservePercent']=revert["reservePercent"]
        result=setBatteryReserve(payload)
        payload={}
        payload["mode"]=revert["mode"]
        result=setBatteryMode(payload)
        payload={}
        payload["state"]=revert["batteryPauseMode"]
        result=setBatteryPauseMode(payload)
        os.remove(".FERunning")
        updateControlCache("Force_Export","Normal")
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Force Export Revert failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def forceExport(exportTime):
    temp={}
    logger.debug("Forcing Export for "+str(exportTime)+" minutes")
    try:
        exportTime=int(exportTime)
        result={}
        revert={}
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            revert["dischargeRate"]=regCacheStack[4]["Control"]["Battery_Discharge_Rate"]
            revert["start_time"]=regCacheStack[4]["Timeslots"]["Discharge_start_time_slot_2"][:5]
            revert["end_time"]=regCacheStack[4]["Timeslots"]["Discharge_end_time_slot_2"][:5]
            revert["reservePercent"]=regCacheStack[4]["Control"]["Battery_Power_Reserve"]
            revert["mode"]=regCacheStack[4]["Control"]["Mode"]
            revert['discharge_schedule']=regCacheStack[4]["Control"]["Enable_Discharge_Schedule"]
            revert["batteryPauseMode"]=regCacheStack[4]["Control"]["Battery_pause_mode"]
        maxDischargeRate=int(finditem(regCacheStack[4],"Invertor_Max_Bat_Rate"))
        
        #In case somebody has set a high reserve value set the reserve rate to the default value to allow the battery to discharge
        try:
            payload={}
            payload['reservePercent']=4
            result=setBatteryReserve(payload) 
        except:
            logger.debug("Error Setting Reserve to 4%")

        payload={}
        payload['start']=GivLUT.getTime(datetime.now())
        finish=GivLUT.getTime(datetime.now()+timedelta(minutes=exportTime))
        payload['finish']=finish
        payload['slot']=2
        result=setDischargeSlot(payload)
        payload={}
        payload['state']="enable"
        result=enableDischargeSchedule(payload)
        payload={}
        payload['mode']="Timed Export"
        result=setBatteryMode(payload)
        payload={}
        logger.debug("Max discharge rate for inverter is: " + str(maxDischargeRate))
        payload['dischargeRate']=maxDischargeRate
        result=setDischargeRate(payload)
        # Set Battery Pause Mode
        payload={}
        payload['state']="Disabled"
        result=setBatteryPauseMode(payload)
        
        if exists(".FERunning"):    # If a forcecharge is already running, change time of revert job to new end time.
            logger.info("Force Export already running, changing end time")
            revert=getFEArgs()[0]   # set new revert object and cancel old revert job
            logger.debug("new revert= "+ str(revert))
        fejob=GivQueue.q.enqueue_in(timedelta(minutes=exportTime),FEResume,revert)
        with open(".FERunning", 'w') as f:
            f.write('\n'.join([str(fejob.id),str(finish)]))
        logger.debug("Force Export revert jobid is: "+fejob.id)
        temp['result']="Export successfully forced for "+str(exportTime)+" minutes"
        updateControlCache("Force_Export","Running")
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Force Export failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def FCResume(revert):
    payload={}
    try:
        logger.info("Reverting Force Charge Settings:")
        payload['chargeRate']=revert["chargeRate"]
        setChargeRate(payload)
        payload={}
        payload['state']=revert["chargeScheduleEnable"]
        enableChargeSchedule(payload)
        payload={}
        payload['start']=revert["start_time"]
        payload['finish']=revert["end_time"]
        payload['chargeToPercent']=revert["targetSOC"]
        payload['slot']=1
        setChargeSlot(payload)
        payload={}
        payload["state"]=revert["batteryPauseMode"]
        result=setBatteryPauseMode(payload)
        os.remove(".FCRunning")
        updateControlCache("Force_Charge","Normal")
    except:
        e=sys.exc_info()
        logger.error("Error in FCResume"+str(e))

def cancelJob(jobid):
    if jobid in GivQueue.q.scheduled_job_registry:
        GivQueue.q.scheduled_job_registry.requeue(jobid, at_front=True)
        logger.info("Cancelling scheduled task as requested")
    else:
        logger.error("Job ID: " + str(jobid) + " not found in redis queue")

def getFCArgs():
    from rq.job import Job
    # getjobid
    f=open(".FCRunning", 'r')
    jobid=f.readline().strip('\n')
    f.close()
    # get the revert details from the old job
    job=Job.fetch(jobid,GivQueue.redis_connection)
    details=job.args
    logger.debug("Previous args= "+str(details))
    GivQueue.q.scheduled_job_registry.remove(jobid) # Remove the job from the schedule
    return (details)

def getFEArgs():
    from rq.job import Job
    # getjobid
    f=open(".FERunning", 'r')
    jobid=f.readline().strip('\n')
    f.close()
    # get the revert details from the old job
    job=Job.fetch(jobid,GivQueue.redis_connection)
    details=job.args
    logger.debug("Previous args= "+str(details))
    GivQueue.q.scheduled_job_registry.remove(jobid) # Remove the job from the schedule
    return (details)

def forceCharge(chargeTime):
    temp={}
    logger.debug("Forcing Charge for "+str(chargeTime)+" minutes")
    try:
        chargeTime=int(chargeTime)
        payload={}
        result={}
        revert={}
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            revert["start_time"]=regCacheStack[4]["Timeslots"]["Charge_start_time_slot_1"][:5]
            revert["end_time"]=regCacheStack[4]["Timeslots"]["Charge_end_time_slot_1"][:5]
            revert["chargeRate"]=regCacheStack[4]["Control"]["Battery_Charge_Rate"]
            revert["targetSOC"]=regCacheStack[4]["Control"]["Target_SOC"]
            revert["chargeScheduleEnable"]=regCacheStack[4]["Control"]["Enable_Charge_Schedule"]
            revert["batteryPauseMode"]=regCacheStack[4]["Control"]["Battery_pause_mode"]
            maxChargeRate=int(finditem(regCacheStack[4],"Invertor_Max_Bat_Rate"))
        else:
            maxChargeRate=2500

        payload['chargeRate']=maxChargeRate
        result=setChargeRate(payload)
        payload={}
        payload['start']=GivLUT.getTime(datetime.now())
        finish=GivLUT.getTime(datetime.now()+timedelta(minutes=chargeTime))
        payload['finish']=finish
        payload['chargeToPercent']=100
        payload['slot']=1
        result=setChargeSlot(payload)
        payload={}
        payload['state']="enable"
        result=enableChargeSchedule(payload)
        # Set Battery Pause Mode
        payload={}
        payload['state']="Disabled"
        result=setBatteryPauseMode(payload)
        if exists(".FCRunning"):    # If a forcecharge is already running, change time of revert job to new end time
            logger.info("Force Charge already running, changing end time")
            revert=getFCArgs()[0]   # set new revert object and cancel old revert job
            logger.critical("new revert= "+ str(revert))
        fcjob=GivQueue.q.enqueue_in(timedelta(minutes=chargeTime),FCResume,revert)
        with open(".FCRunning", 'w') as f:
            f.write('\n'.join([str(fcjob.id),str(finish)]))
        logger.debug("Force Charge revert jobid is: "+fcjob.id)
        temp['result']="Charge successfully forced for "+str(chargeTime)+" minutes"
        updateControlCache("Force_Charge","Running")
        logger.debug(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Force charge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def tmpPDResume(payload):
    temp={}
    try:
        logger.debug("Reverting Temp Pause Discharge")
        result=setDischargeRate(payload)
        if exists(".tpdRunning"): os.remove(".tpdRunning")
        temp['result']="Temp Pause Discharge Reverted"
        updateControlCache("Temp_Pause_Discharge","Normal")
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Temp Pause Discharge Resume failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def tempPauseDischarge(pauseTime):
    temp={}
    try:
        pauseTime=int(pauseTime)
        logger.debug("Pausing Discharge for "+str(pauseTime)+" minutes")
        payload={}
        result={}
        payload['dischargeRate']=0
        result=setDischargeRate(payload)
        #Update read data via pickle
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            revertRate=regCacheStack[4]["Control"]["Battery_Discharge_Rate"]
        else:
            revertRate=2600
        payload['dischargeRate']=revertRate
        delay=float(pauseTime*60)
        tpdjob=GivQueue.q.enqueue_in(timedelta(seconds=delay),tmpPDResume,payload)
        finishtime=GivLUT.getTime(datetime.now()+timedelta(minutes=pauseTime))
        with open(".tpdRunning", 'w') as f:
            f.write('\n'.join([str(tpdjob.id),str(finishtime)]))
        
        logger.debug("Temp Pause Discharge revert jobid is: "+tpdjob.id)
        temp['result']="Discharge paused for "+str(delay)+" seconds"
        updateControlCache("Temp_Pause_Discharge","Running")
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Pausing Discharge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def tmpPCResume(payload):
    temp={}
    try:
        logger.debug("Reverting Temp Pause Charge...")
        result=setChargeRate(payload)
        if exists(".tpcRunning"): os.remove(".tpcRunning")
        temp['result']="Temp Pause Charge Reverted"
        updateControlCache("Temp_Pause_Charge","Normal")
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Temp Pause Charge Resume failed: " + str(e)
        logger.error (temp['result'])
    return json.dump(temp)

def tempPauseCharge(pauseTime):
    temp={}
    try:
        logger.debug("Pausing Charge for "+str(pauseTime)+" minutes")
        payload={}
        result={}
        payload['chargeRate']=0
        result=setChargeRate(payload)
        #Update read data via pickle
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack= pickle.load(inp)
            revertRate=regCacheStack[4]["Control"]["Battery_Charge_Rate"]
        else:
            revertRate=2600
        payload['chargeRate']=revertRate
        delay=float(pauseTime*60)
        finishtime=GivLUT.getTime(datetime.now()+timedelta(minutes=pauseTime))
        tpcjob=GivQueue.q.enqueue_in(timedelta(seconds=delay),tmpPCResume,payload)
        with open(".tpcRunning", 'w') as f:
            f.write('\n'.join([str(tpcjob.id),str(finishtime)]))
        logger.debug("Temp Pause Charge revert jobid is: "+tpcjob.id)
        temp['result']="Charge paused for "+str(delay)+" seconds"
        updateControlCache("Temp_Pause_Charge","Running")
        logger.debug(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Pausing Charge failed: " + str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

def setBatteryPowerMode(payload):
    temp={}
    try:
        logger.debug("Setting Battery Power Mode to: "+str(payload['state']))
        if type(payload) is not dict: payload=json.loads(payload)
        if payload['state']=="enable":
            temp= asyncio.run(sbdmd())
        else:
            temp= asyncio.run(sbdmmp())
        temp['result']="Setting Battery Power Mode to "+str(payload['state'])+" was a success"
    except:
        e=sys.exc_info()
        temp['Result']="Error in setting Battery power mode: "+str(e)
    return json.dumps(temp)

def setBatteryPauseMode(payload):
    temp={}
    try:
        logger.debug("Setting Battery Pause Mode to: "+str(payload['state']))
        if type(payload) is not dict: payload=json.loads(payload)
        if payload['state'] in GivLUT.battery_pause_mode:
            val=GivLUT.battery_pause_mode.index(payload['state'])
            temp= asyncio.run(sbpm(val))
        else:
            logger.error ("Invalid Mode requested: "+ payload['state'])
            temp['result']="Invalid Mode requested"
    except:
        e=sys.exc_info()
        temp['Result']="Error in setting Battery pause mode: "+str(e)
    return json.dumps(temp)

def setLocalControlMode(payload):
    temp={}
    try:
        logger.debug("Setting Local Control Mode to: "+str(payload['state']))
        if type(payload) is not dict: payload=json.loads(payload)
        if payload['state'] in GivLUT.local_control_mode:
            val=GivLUT.local_control_mode.index(payload['state'])
            temp= asyncio.run(slcm(val))
        else:
            logger.error ("Invalid Mode requested: "+ payload['state'])
            temp['result']="Invalid Mode requested"
    except:
        e=sys.exc_info()
        temp['Result']="Error in setting local control mode: "+str(e)
    return json.dumps(temp)

def setBatteryMode(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Battery Mode to: "+str(payload['mode']))
        if payload['mode']=="Eco":
            temp= asyncio.run(smd(False))
            saved_battery_reserve = getSavedBatteryReservePercentage()
            temp= asyncio.run(ssc(saved_battery_reserve))
        elif payload['mode']=="Eco (Paused)":
            temp= asyncio.run(smd(True))
        elif payload['mode']=="Timed Demand":
            temp= asyncio.run(sbdmd())
            temp= asyncio.run(ed())
        elif payload['mode']=="Timed Export":
            temp= asyncio.run(sbdmmp())
            temp= asyncio.run(ed())
        else:
            logger.error ("Invalid Mode requested: "+ payload['mode'])
            temp['result']="Invalid Mode requested"
            return json.dumps(temp)
        temp['result']="Setting Battery Mode was a success"
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Mode failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setPVInputMode(payload):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting PV Input mode to: "+ str(payload['state']))
        if payload['state'] in GivLUT.pv_input_mode:
            temp= asyncio.run(spvim(GivLUT.pv_input_mode.index(payload['state'])))
        else:
            logger.error ("Invalid Mode requested: "+ payload['state'])
            temp['result']="Invalid Mode requested"
        temp['result']="Setting PV Input Mode was a success"
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting PV Input Mode failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

def setDateTime(payload):
    temp={}
    targetresult="Success"
    if type(payload) is not dict: payload=json.loads(payload)
    #convert payload to dateTime components
    try:
        iDateTime=datetime.strptime(payload['dateTime'],"%d/%m/%Y %H:%M:%S")   #format '12/11/2021 09:15:32'
        logger.debug("Setting inverter time to: "+iDateTime)
        #Set Date and Time on inverter
        temp= asyncio.run(sdt(iDateTime))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting inverter DateTime failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

def setCarChargeBoost(val):
    temp={}
    targetresult="Success"
    try:
        logger.debug("Setting Car Charge Boost to: "+str(val)+"w")
        temp= asyncio.run(sccb(val))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Car Charge Boost failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

def setBatteryCalibration(payload):
    temp={}
    targetresult="Success"
    if type(payload) is not dict: payload=json.loads(payload)
    if payload['state'] in GivLUT.battery_calibration:
        val=GivLUT.battery_calibration.index(payload['state'])
    try:
        logger.debug("Setting Battery Calibration to: "+str(payload['state']))
        temp= asyncio.run(sbc(val))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Calibration failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

def setExportLimit(val):
    temp={}
    targetresult="Success"
    try:
        logger.debug("Setting Export Limit to: "+str(val)+"w")
        #Set Date and Time on inverter
        temp= asyncio.run(sel(val))
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Limit failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

def switchRate(payload):
    temp={}
    if GiV_Settings.dynamic_tariff == False:     # Only allow this control if Dynamic control is enabled
        temp['result']="External rate setting not allowed. Enable Dynamic Tariff in settings"
        logger.error(temp['result'])
        return json.dumps(temp)
    try:
        if payload.lower()=="day":
            open(GivLUT.dayRateRequest, 'w').close()
            logger.info ("Setting dayRate via external trigger")
        else:
            open(GivLUT.nightRateRequest, 'w').close()
            logger.info ("Setting nightRate via external trigger")
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Rate failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

def rebootAddon():
    temp={}
    try:
        logger.critical("Restarting the GivTCP Addon in 2s...")
        time.sleep(2)
        if GiV_Settings.isAddon:
            access_token = os.getenv("SUPERVISOR_TOKEN")
            url="http://supervisor/addons/self/restart"
            result = requests.post(url,
                headers={'Content-Type':'application/json',
                        'Authorization': 'Bearer {}'.format(access_token)})
            logger.info("Supervisor restart was: "+str(result))
        else:
            open("/app/.reboot", 'w').close()
            result="Container restarting within 60s"
            logger.info("Container restart was: "+str(result))
        
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Failed to reboot GivTCP: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(result)

def getSavedBatteryReservePercentage():
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

# -*- coding: utf-8 -*-
# version 2022.01.31
import sys
import json
import logging
import datetime
from datetime import datetime, timedelta
from settings import GiV_Settings
import settings
import signal
import time
from os.path import exists
import pickle,os
import GivLUT
from GivLUT import GivLUT, GivQueue
from givenergy_modbus_async.client import commands
from givenergy_modbus_async.model import TimeSlot
from givenergy_modbus.client import GivEnergyClient
from givenergy_modbus_async.pdu import WriteHoldingRegisterResponse, TransparentRequest
import requests
import importlib
import asyncio

from GivLUT import GivClientAsync

logging.getLogger("givenergy_modbus_async").setLevel(logging.CRITICAL)
client=GivEnergyClient(host=GiV_Settings.invertorIP)

logger = GivLUT.logger

def finditem(obj, key):
    if key in obj: return obj[key]
    for k, v in obj.items():
        if isinstance(v,dict):
            item = finditem(v, key)
            if item is not None:
                return item
    return None

def frtouch():
    with open(".fullrefresh",'w') as fp:
        pass

def updateControlCache(entity,value,isTime: bool=False):
    from mqtt import GivMQTT
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
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        regCacheStack = GivLUT.get_regcache()
    if "regCacheStack" in locals():
        #find right object
        if isTime:
            regCacheStack[4]['Timeslots'][entity]=value
        else:
            regCacheStack[4]['Control'][entity]=value
        with open(GivLUT.regcache, 'wb') as outp:
            pickle.dump(regCacheStack, outp, pickle.HIGHEST_PROTOCOL)
        logger.debug("Pushing control update to pkl cache: "+entity+" - "+str(value))
    return

async def sendAsyncCommand(reqs,readloop):
    output={}
    asyncclient=await GivClientAsync.get_connection()
    if not asyncclient.connected:
        logger.info("Write client not connected after import")
        await asyncclient.connect()

    result= await asyncclient.execute(reqs,timeout=3,retries=6, return_exceptions=True)
    for idx, req in enumerate(result):
        if not isinstance(req,WriteHoldingRegisterResponse):
            output['error']="Error in write command: HR("+str(reqs[idx].register)+")"
            output['error_type']=type(req).__name__
            break
    if not readloop:
        #if write command came from somewhere other than the read loop then close the connection at the end
        logger.debug("Closing non readloop modbus connection")
        await asyncclient.close()
    return output

async def sct(target, readloop=False):
    """ Not suitable for AIO, use sst()"""
    temp={}
    try:
        reqs=commands.set_charge_target_only(int(target), inv_type=GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Target_SOC",target)
        temp['result']="Setting Charge Target "+str(target)+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Charge Target "+str(target)+" failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def sem(enable,readloop=False):
    temp={}
    try:
        reqs=commands.set_eco_mode(enable)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if enable:
            updateControlCache("Eco_Mode","enable")
        else:
            updateControlCache("Eco_Mode","disable")
        temp['result']="Setting Eco Mode "+str(enable)+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Eco Mode "+str(enable)+" failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def sst(target,slot,readloop=False):
    temp={}
    try:
        reqs=commands.set_soc_target(False,slot,int(target),GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Charge_Target_SOC_"+str(slot),target)
        else:
            updateControlCache("Charge_Target_SOC_"+str(slot),target)
        temp['result']="Setting Charge Target "+str(slot) + " was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Charge Target "+str(slot) + " failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def sest(target,slot,readloop=False):
    temp={}
    try:
        reqs=commands.set_export_soc_target(False,slot,int(target))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Export_Target_SOC_"+str(slot),target)
        temp['result']="Setting Export Target "+str(slot) + " was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Export Target "+str(slot) + " failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def sdct(target,slot,readloop=False):
    temp={}
    try:
        reqs=commands.set_soc_target(True,slot,int(target),GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Discharge_Target_SOC_"+str(slot),target)
        else:
            updateControlCache("Discharge_Target_SOC_"+str(slot),target)
        temp['result']="Setting Discharge Target "+str(slot) + " was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Discharge Target "+str(slot) + " failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def ect(readloop=False):
    temp={}
    try:
        reqs=commands.enable_charge_target()
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception           
        temp['result']="Enabling Charge Target was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Enabling Charge Target failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def dct(readloop=False):
    temp={}
    try:
        reqs=commands.disable_charge_target()
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception   
        updateControlCache("Target_SOC",100)
        temp['result']="Disabling Charge Target was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Disabling Charge Target failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def ed(readloop=False):
    temp={}
    try:
        reqs=commands.set_enable_discharge(True)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception   
        updateControlCache("Enable_Discharge_Schedule","enable")
        temp['result']="Enabling Discharge Schedule was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Enabling Discharge Schedule failed: "+str(result['error_type'])
        logger.error(temp['result'])   
    return temp

async def dd(readloop=False):
    temp={}
    try:
        reqs=commands.set_enable_discharge(False)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception   
        updateControlCache("Enable_Discharge_Schedule","disable")
        temp['result']="Disabling Discharge Schedule was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Disabling Discharge Schedule failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def ec(readloop=False):
    temp={}
    try:
        reqs=commands.set_enable_charge(True)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception        
        updateControlCache("Enable_Charge_Schedule","enable")
        temp['result']="Enabling Charge Schedule was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Enabling Charge Schedule failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def dc(readloop=False):
    temp={}
    try:
        reqs=commands.set_enable_charge(False)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception 
        updateControlCache("Enable_Charge_Schedule","disable")
        temp['result']="Disabling Charge Schedule was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Disabling Charge Schedule failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

def slcm(val):
    temp={}
    try:
        client.set_local_control_mode(val)
        updateControlCache("Local_control_mode",str(GivLUT.local_control_mode[int(val)]))
        temp['result']="Setting Local Control Mode to " +str(GivLUT.local_control_mode[val])+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Local Control Mode to " +str(GivLUT.local_control_mode[val])+" failed"
        logger.error(temp['result'])
    return temp

async def sbpm(val,readloop=False):
    temp={}
    try:
        
        reqs=commands.set_battery_pause_mode(val)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception 
        updateControlCache("Battery_pause_mode",str(GivLUT.battery_pause_mode[int(val)]))
        temp['result']="Setting Battery Pause Mode to " +str(GivLUT.battery_pause_mode[val])+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Battery Pause Mode to " +str(GivLUT.battery_pause_mode[val])+" failed"
        logger.error(temp['result'])
    return temp

async def ssc(target,readloop=False):
    temp={}
    try:
        
        reqs=commands.set_battery_soc_reserve(target, inv_type=GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Power_Reserve",target)
        temp['result']="Setting shallow charge "+str(target)+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting shallow charge "+str(target)+" failed"
        logger.error(temp['result'])
    return temp
async def sbpr(target,readloop=False):
    temp={}
    try:
        
        reqs=commands.set_battery_power_reserve(target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Power_Cutoff",target)
        temp['result']="Setting battery power reserve to "+str(target)+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting battery power reserve "+str(target)+" failed"
        logger.error(temp['result'])
    return temp
async def ri(readloop=False):
    temp={}
    try:
        
        reqs=commands.set_inverter_reboot()
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        temp['result']="Rebooting Inverter was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Rebooting Inverter failed"
        logger.error(temp['result'])
    return temp

async def sapr(target,readloop=False):
    temp={}
    try:
        
        reqs=commands.set_active_power_rate(target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Active_Power_Rate",target)
        temp['result']="Setting active power rate "+str(target)+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting active power rate "+str(target)+" failed"
        logger.error(temp['result'])
    return temp
async def sbcl(target,readloop=False):
    temp={}
    try:
        reqs=commands.set_battery_charge_limit(target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        # Get cache and work out rate
        regCacheStack = GivLUT.get_regcache()
        if "regCacheStack" in locals():
            multi_output_old = regCacheStack[4]
        batteryCapacity=int(multi_output_old[finditem(multi_output_old,"Invertor_Serial_Number")]['Battery_Capacity_kWh'])*1000
        batmaxrate=int(multi_output_old[finditem(multi_output_old,"Invertor_Serial_Number")]['Invertor_Max_Bat_Rate'])
        val=int(min((target/100)*(batteryCapacity), batmaxrate))
        updateControlCache("Battery_Charge_Rate",val)
        temp['result']="Setting battery charge rate "+str(target)+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting battery charge rate "+str(target)+" failed"
        logger.error(temp['result'])
    return temp
async def sbcla(target,readloop=False):
    temp={}
    try:
        reqs=commands.set_battery_charge_limit_ac(target, inv_type=GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Charge_Rate_AC",target)
        temp['result']="Setting battery charge rate AC to "+str(target)+"% was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting battery charge rate "+str(target)+" failed"
        logger.error(temp['result'])
    return temp

async def sbdl(target,readloop=False):
    temp={}
    try:
        reqs=commands.set_battery_discharge_limit(target)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        # Get cache and work out rate
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            regCacheStack=GivLUT.get_regcache()
            multi_output_old = regCacheStack[4]
            batteryCapacity=int(multi_output_old[finditem(multi_output_old,'Invertor_Serial_Number')]['Battery_Capacity_kWh'])*1000
            batmaxrate=int(multi_output_old[finditem(multi_output_old,'Invertor_Serial_Number')]['Invertor_Max_Bat_Rate'])
            val=int(min((target/100)*(batteryCapacity), batmaxrate))
            updateControlCache("Battery_Discharge_Rate",val)
        temp['result']="Setting battery discharge limit "+str(target)+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting battery discharge limit "+str(target)+" failed"
        logger.error(temp['result'])   
    return temp

async def sbdla(target,readloop=False):
    temp={}
    try:
        
        reqs=commands.set_battery_discharge_limit_ac(target, inv_type=GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Discharge_Rate_AC",target)
        temp['result']="Setting battery discharge rate AC to "+str(target)+"% was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting battery discharge rate "+str(target)+" failed"
        logger.error(temp['result'])
    return temp
async def smd(paused,readloop=False):
    temp={}
    try:
        
        reqs=commands.set_mode_dynamic(paused)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        temp['result']="Setting dynamic mode was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting dynamic mode failed"
        logger.error(temp['result'])
    return temp
async def sms(target,readloop=False):
    temp={}
    try:
        
        reqs=commands.set_mode_storage(discharge_for_export=False, inv_type=GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        temp['result']="Setting storage mode "+str(target)+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting storage mode "+str(target)+" failed"
        logger.error(temp['result'])
    return temp
async def sbdmd(readloop=False):
    temp={}
    try:
        
        reqs=commands.set_mode_storage(discharge_for_export=False, inv_type=GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Mode","Timed Demand")
        temp['result']="Setting demand mode was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting demand mode failed"
        logger.error(temp['result'])
    return temp
async def sbdmmp(readloop=False):
    temp={}
    try:
        
        reqs=commands.set_mode_storage(discharge_for_export=True, inv_type=GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Mode","Timed Export")
        temp['result']="Setting export mode was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting export mode failed"
        logger.error(temp['result'])   
    return temp

async def spvim(val):
    temp={}
    try:
        client.set_pv_input_mode(val)
        updateControlCache("PV_input_mode",str(GivLUT.pv_input_mode[int(val)]))
        temp['result']="Setting PV Input mode to "+str(GivLUT.pv_input_mode[val])+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting PV Input mode to "+str(GivLUT.pv_input_mode[val])+" failed"
        logger.error(temp['result'])  
    return temp

async def sccb(val,readloop=False):
    temp={}
    try:
        reqs=commands.set_car_charge_boost(discharge_for_export=True)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Car_Charge_Boost",val)
        temp['result']="Setting Car Charge Boost to "+str(val)+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Car Charge Boost to "+str(val)+" failed: "+str(result['error_type'])
        logger.error(temp['result'])  
    return temp

async def sel(val,readloop=False):
    temp={}
    try:
        reqs=commands.set_export_limit(discharge_for_export=True)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Export_Power_Limit",val)
        temp['result']="Setting Car Charge Boost to "+str(val)+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Car Charge Boost to "+str(val)+" failed: "+str(result['error_type'])
        logger.error(temp['result'])  
    return temp

async def sdt(idateTime: datetime,readloop=False):
    temp={}
    try:
        
        reqs=commands.set_system_date_time(idateTime)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        temp['result']="Setting inverter time was a success"
        updateControlCache("Invertor_Time",idateTime.strftime("%d-%m-%Y %H:%M:%S.%f"))
        logger.debug(temp['result'])
    except:
        temp['result']="Setting inverter time failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def sds(payload,readloop=False):
    temp={}
    try:
        # create Timeslot object forslot in func
        slot=TimeSlot
        slot.start=datetime.strptime(payload['start'],"%H:%M")
        slot.end=datetime.strptime(payload['finish'],"%H:%M")
        reqs=commands._set_charge_slot(True,int(payload['slot']),slot,GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("EMS_Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def sbc(val,readloop=False):
    temp={}
    try:
        reqs=commands.set_calibrate_battery_soc(int(val))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_Calibration",str(GivLUT.battery_calibration[val]))
        temp['result']="Setting Battery Calibration "+str(val)+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Battery Calibration "+str(val)+" failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def ses(payload,readloop=False):
    temp={}
    try:
        # create Timeslot object forslot in func
        slot=TimeSlot
        slot.start=datetime.strptime(payload['start'],"%H:%M")
        slot.end=datetime.strptime(payload['finish'],"%H:%M")
        reqs=commands.set_export_slot(int(payload['slot']),slot)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Export_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        updateControlCache("Export_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Export Slot "+str(payload['slot'])+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def sdss(payload,readloop=False):
    temp={}
    try:

        reqs=commands.set_charge_slot_start(True,int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"),GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        else:
            updateControlCache("Discharge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Discharge Slot Start "+str(payload['slot'])+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Discharge Slot Start "+str(payload['slot'])+" failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp


async def sdse(payload,readloop=False):
    temp={}
    try:

        reqs=commands.set_charge_slot_end(True,int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"),GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Discharge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def sps(payload,readloop=False):
    temp={}
    try:
        slot=TimeSlot
        slot.start=datetime.strptime(payload['start'],"%H:%M")
        slot.end=datetime.strptime(payload['finish'],"%H:%M")
        
        reqs=commands.set_pause_slot(slot)
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        updateControlCache("Battery_pause_start_time_slot",str(datetime.strptime(payload['start'],"%H:%M")))
        updateControlCache("Battery_pause_end_time_slot",str(datetime.strptime(payload['finish'],"%H:%M")))
        temp['result']="Setting Battery Pause Slot was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Battery Pause Slot failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def spss(payload,readloop=False):
    temp={}
    try:
        
        reqs=commands.set_pause_slot_start(datetime.strptime(payload['start'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result)
        updateControlCache("Battery_pause_start_time_slot",str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Pause Slot Start was a success"
        logger.debug(temp['result'])
    except:
        e=sys.exc_info()[1].args[0], os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Pause Slot Start failed: " + str(e)
        logger.error(temp['result'])
    return temp

async def spse(payload,readloop=False):
    temp={}
    try:
        reqs=commands.set_pause_slot_end(datetime.strptime(payload['finish'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception(result)
        updateControlCache("Battery_pause_end_time_slot",str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Pause Slot End was a success"
        logger.debug(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Pause Slot End failed: " + str(e)
        logger.error(temp['result'])
    return temp

async def scs(payload,readloop=False):
    temp={}
    try:
        slot=TimeSlot
        slot.start=datetime.strptime(payload['start'],"%H:%M")
        slot.end=datetime.strptime(payload['finish'],"%H:%M")

        reqs=commands._set_charge_slot(False,int(payload['slot']),slot,GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("EMS_Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
            updateControlCache("Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+str(result['error_type'])
        logger.error(temp['result'])   
    return temp

async def sess(payload,readloop=False):
    temp={}
    try:
        reqs=commands.set_export_slot_start(int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception        
        updateControlCache("Export_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Export Slot Start "+str(payload['slot'])+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Export Slot Start "+str(payload['slot'])+" failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def sese(payload,readloop=False):
    temp={}
    try:
        
        reqs=commands.set_export_slot_end(int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"))
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception         
        updateControlCache("Export_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Export Slot End "+str(payload['slot'])+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Export Slot End "+str(payload['slot'])+" failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def scss(payload,readloop=False):
    temp={}
    try:
        if "TPH" in payload:
            TPH=payload['TPH']
        else:
            TPH=False
        if "EMS" in payload:
            EMS=payload['EMS']
        else:
            EMS=False
        reqs=commands.set_charge_slot_start(False,int(payload['slot']),datetime.strptime(payload['start'],"%H:%M"),GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if EMS:
            updateControlCache("EMS_Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        else:
            updateControlCache("Charge_start_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['start'],"%H:%M")),True)
        temp['result']="Setting Charge Slot Start "+str(payload['slot'])+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Charge Slot Start "+str(payload['slot'])+" failed: "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def scse(payload,readloop=False):
    temp={}
    try:

        reqs=commands.set_charge_slot_end(False,int(payload['slot']),datetime.strptime(payload['finish'],"%H:%M"),GiV_Settings.inverter_type.lower())
        result= await sendAsyncCommand(reqs,readloop)
        if 'error' in result:
            raise Exception
        if 'ems' in GiV_Settings.inverter_type.lower():
            updateControlCache("EMS_Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        else:
            updateControlCache("Charge_end_time_slot_"+str(payload['slot']),str(datetime.strptime(payload['finish'],"%H:%M")),True)
        temp['result']="Setting Charge Slot End "+str(payload['slot'])+" was a success"
        logger.debug(temp['result'])
    except:
        temp['result']="Setting Charge Slot End "+str(payload['slot'])+" failed: : "+str(result['error_type'])
        logger.error(temp['result'])
    return temp

async def setForceCharge(payload,readloop=False):
    temp={}
    try:
        logger.debug("Enabling Force Charge")
        if payload['state']=="enable":
            enabled=True
        else:
            enabled=False
        reqs=commands.set_force_charge(enabled)
        temp['result']= await sendAsyncCommand(reqs,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Force Charge "+str(payload['state'])+" failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setForceDischarge(payload,readloop=False):
    temp={}
    try:
        logger.debug("Enabling Force Discharge")
        if payload['state']=="enable":
            enabled=True
        else:
            enabled=False
        reqs=commands.set_force_discharge(enabled)
        temp['result']= await sendAsyncCommand(reqs,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Force Discharge "+str(payload['state'])+" failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setACCharge(payload,readloop=False):
    temp={}
    try:
        logger.debug("Enabling AC Charge")
        if payload['state']=="enable":
            enabled=True
        else:
            enabled=False
        reqs=commands.set_ac_charge(enabled)
        temp['result']= await sendAsyncCommand(reqs,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting AC Charge "+str(payload['state'])+" failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def enableDischargeSchedule(payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Disharge Schedule")
            temp= await ed(readloop)
        elif payload['state']=="disable":
            logger.debug("Disabling Discharge Schedule")
            temp= await dd(readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Enable failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def enableChargeSchedule(payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Charge Schedule")
            temp= await ec(readloop)
        elif payload['state']=="disable":
            logger.debug("Disabling Charge Schedule")
            temp= await dc(readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting charge schedule "+str(payload['state'])+" failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def enableChargeTarget(payload,readloop=False):
    temp={}
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Charge Target")
            temp= await ect(readloop)
        elif payload['state']=="disable":
            logger.debug("Disabling Charge Target")
            temp= await dct(readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Target failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def enableDischarge(payload,readloop=False):
    temp={}
    saved_battery_reserve = getSavedBatteryReservePercentage()
    try:
        if payload['state']=="enable":
            logger.debug("Enabling Discharge")
            temp= await ssc(saved_battery_reserve,readloop)
            updateControlCache("Enable_Discharge","enable")
        elif payload['state']=="disable":
            logger.debug("Disabling Discharge")
            temp= await ssc(100,readloop)
            updateControlCache("Enable_Discharge","disable")
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Enable failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setShallowCharge(payload,readloop=False):
    temp={}
    try:
        logger.debug("Setting Shallow Charge to: "+ str(payload['val']))
        temp= await ssc(int(payload['val']),readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting shallow charge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeTarget(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['chargeToPercent'])
        logger.debug("Setting Charge Target to: "+str(target))
        temp=await sct(target,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Target failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeTarget2(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['chargeToPercent'])
        slot=int(payload['slot'])
        if "EMS" in payload.keys():
            EMS=bool(payload['EMS'])
        else:
            EMS=False
        if "TPH" in payload:
            TPH=payload['TPH']
        else:
            TPH=False
        logger.debug("Setting Charge Target "+str(slot) + " to: "+str(target))
        temp= await sst(target,slot,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Target "+str(slot) + " failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportTarget(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['exportToPercent'])
        slot=int(payload['slot'])
        logger.debug("Setting Export Target "+str(slot) + " to: "+str(target))
        temp= await sest(target,slot,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Target "+str(slot) + " failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeTarget(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['dischargeToPercent'])
        slot=int(payload['slot'])
        logger.debug("Setting Discharge Target "+str(slot) + " to: "+str(target))
        temp= await sdct(target,slot,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Target "+str(slot) + " failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setBatteryReserve(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['reservePercent'])
        #Only allow minimum of 4%
        if target<4: target=4
        logger.debug ("Setting battery reserve target to: " + str(target))
        temp= await ssc(target,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Reserve failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setBatteryCutoff(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['dischargeToPercent'])
        #Only allow minimum of 4%
        if target<4: target=4
        logger.debug ("Setting battery cutoff target to: " + str(target))
        temp= await sbpr(target,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Cutoff failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def rebootinverter(payload,readloop=False):
    temp={}
    try:
        logger.debug("Rebooting inverter...")
        temp= await ri(readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Reboot inverter failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setActivePowerRate(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['activePowerRate'])
        logger.debug("Setting Active Power Rate to "+str(target))
        temp= await sapr(target,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Active Power Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeRate(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)

    # Get inverter max bat power
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        regCacheStack=GivLUT.get_regcache()
        multi_output_old = regCacheStack[4]
        invmaxrate=finditem(multi_output_old,'Invertor_Max_Bat_Rate')
        batcap=float(finditem(multi_output_old,'Battery_Capacity_kWh'))*1000
        try:
            if "3ph" in GiV_Settings.inverter_type.lower():
                target= round(int(payload['chargeRate'])/invmaxrate,0)
                temp = await sbcla(target, readloop)
            else:
                if int(payload['chargeRate']) < int(invmaxrate):
                    target=int(min((int(payload['chargeRate'])/(batcap/2))*50,50))
                else:
                    target=50
                temp= await sbcl(target,readloop)
            logger.debug ("Setting battery charge rate to: " + str(payload['chargeRate'])+" ("+str(target)+")")
            logger.info(temp['result'])
        except:
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            temp['result']="Setting Charge Rate failed: " + str(e)
            logger.error (temp['result'])
    else:
        temp['result']="Setting Charge Rate failed: No charge rate limit available"
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeRateAC(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['chargeRate'])
        logger.debug ("Setting AC battery charge rate to: " + str(target))
        temp= await sbcla(target,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting AC Battery Charge Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeRate(payload,readloop=False):

## Make this work for 3PH using ratio for limit_ac
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    # Get inverter max bat power
    if exists(GivLUT.regcache):      # if there is a cache then grab it
        regCacheStack=GivLUT.get_regcache()
        multi_output_old = regCacheStack[4]
        invmaxrate=int(finditem(multi_output_old,"Invertor_Max_Bat_Rate"))
        batcap=float(finditem(multi_output_old,'Battery_Capacity_kWh'))*1000
        try:
            if "3ph" in GiV_Settings.inverter_type.lower():
                target= round(int(payload['dischargeRate'])/invmaxrate,0)
                temp = await sbdla(target, readloop)
            else:
                if int(payload['dischargeRate']) < int(invmaxrate):
                    target=int(min((int(payload['dischargeRate'])/(batcap/2))*50,50))
                else:
                    target=50
                temp= await sbdl(target,readloop)
            logger.debug ("Setting battery discharge rate to: " + str(payload['dischargeRate'])+" ("+str(target)+")")
            
            logger.info(temp['result'])
        except:
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            temp['result']="Setting Discharge Rate failed: " + str(e)
            logger.error (temp['result'])
    else:
        temp['result']="Setting Discharge Rate failed: No discharge rate limit available"
        logger.error (temp['result'])        
    return json.dumps(temp)

async def setDischargeRateAC(payload,readloop=False):
    temp={}
    try:
        if type(payload) is not dict: payload=json.loads(payload)
        target=int(payload['dischargeRate'])
        logger.debug ("Setting AC battery discharge rate to: " + str(target))
        temp= await sbdla(target,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting AC battery discharge Rate failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeSlot(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    if 'chargeToPercent' in payload.keys():
        temp= await sct(int(payload['chargeToPercent']),readloop)
    try:
        logger.debug("Setting Charge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        temp= await scs(payload,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setPauseSlot(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Battery Pause slot to: "+str(payload['start'])+" - "+str(payload['finish']))
        temp= await sps(payload,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Pause Slot failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeSlotStart(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Charge Slot "+str(payload['slot'])+" Start to: "+str(payload['start']))
        temp= await scss(payload,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setChargeSlotEnd(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Charge Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        temp= await scse(payload,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Charge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportSlotStart(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Export Slot "+str(payload['slot'])+" Start to: "+str(payload['start']))
        temp= await sess(payload,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportSlotEnd(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Export Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        temp= await sese(payload,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeSlot(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    # Should this include DischargePercent, or drop?
    if 'dischargeToPercent' in payload.keys():
        pload={}
        pload['reservePercent']=payload['dischargeToPercent']
        result=await setBatteryReserve(pload,readloop)
    try:
        strt=datetime.strptime(payload['start'],"%H:%M")
        fnsh=datetime.strptime(payload['finish'],"%H:%M")
        logger.debug("Setting Discharge Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        temp= await sds(payload,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportSlot(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        strt=datetime.strptime(payload['start'],"%H:%M")
        fnsh=datetime.strptime(payload['finish'],"%H:%M")
        logger.debug("Setting Export Slot "+str(payload['slot'])+" to: "+str(payload['start'])+" - "+str(payload['finish']))
        temp= await ses(payload,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Slot "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeSlotStart(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Discharge Slot start "+str(payload['slot'])+" Start to: "+str(payload['start']))
        temp= await sdss(payload,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Slot start "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDischargeSlotEnd(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Discharge Slot End "+str(payload['slot'])+" to: "+str(payload['finish']))
        temp= await sdse(payload,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Discharge Slot End "+str(payload['slot'])+" failed: "+ str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setPauseStart(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Pause Slot Start to: "+str(payload['start']))
        temp= await spss(payload,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Pause Slot Start failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setPauseEnd(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Pause Slot End to: "+str(payload['finish']))
        temp= await spse(payload,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Pause Slot End failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def FEResume(revert, readloop=False):
    temp={}
    try:
        logger.info("Reverting Force Export settings:")
        payload={}
        payload["mode"]=revert["mode"]
        result=await setBatteryMode(payload,readloop)
        reqs=commands.set_battery_soc_reserve(revert["reservePercent"],GiV_Settings.inverter_type.lower())
        slot=TimeSlot
        slot.start=datetime.strptime(revert['start_time'],"%H:%M")
        slot.end=datetime.strptime(revert['end_time'],"%H:%M")
        reqs.extend(commands._set_charge_slot(True,2,slot,GiV_Settings.inverter_type))
        if revert["discharge_schedule"]=="enable":
            enabled=True
        else:
            enabled=False
        reqs.extend(commands.set_enable_discharge(enabled))
        if "dischargeRate" in revert:
            target=50
            if exists(GivLUT.regcache):      # if there is a cache then grab it
                regCacheStack=GivLUT.get_regcache()
                multi_output_old = regCacheStack[4]
                invmaxrate=int(finditem(multi_output_old,"Invertor_Max_Bat_Rate"))
                batcap=float(finditem(multi_output_old,'Battery_Capacity_kWh'))*1000
                if int(revert['dischargeRate']) < int(invmaxrate):
                    target=int(min((int(revert['dischargeRate'])/(batcap/2))*50,50))
            reqs.extend(commands.set_battery_discharge_limit(target))
        elif "dischargeRateAC" in revert:
            reqs.extend(commands.set_battery_discharge_limit_ac(revert["dischargeRateAC"]),GiV_Settings.inverter_type)
        if "3ph" in GiV_Settings.inverter_type.lower():
            reqs.extend(commands.set_force_discharge(revert["forceDischargeEnable"]))  # turn on Force Export in 3PH
            reqs.extend(commands.set_force_charge(revert["forceChargeEnable"]))  # turn off Force Charge in 3PH
        if "batteryPauseMode" in revert:
            reqs.extend(commands.set_battery_pause_mode(GivLUT.battery_pause_mode.index(revert["batteryPauseMode"])))
        
        result = await sendAsyncCommand(reqs,readloop)
        if result:
            logger.error("Errors in control commands: "+str(result))
            raise Exception(result)
        frtouch()
        os.remove(".FERunning"+str(GiV_Settings.givtcp_instance))
        updateControlCache("Force_Export","Normal")
        temp['result']="Force Export Reverted successfully"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Force Export Revert failed: " + str(e)
        os.remove(".FERunning"+str(GiV_Settings.givtcp_instance))
        logger.error (temp['result'])
    return json.dumps(temp)

async def forceExport(exportTime,readloop=False):
    temp={}
    logger.info("Forcing Export for "+str(exportTime)+" minutes")
    try:
        result={}
        revert={}
        hasBPM=False
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            regCacheStack=GivLUT.get_regcache()
            revert["start_time"]=regCacheStack[4]["Timeslots"]["Discharge_start_time_slot_2"][:5]
            revert["end_time"]=regCacheStack[4]["Timeslots"]["Discharge_end_time_slot_2"][:5]
            revert["reservePercent"]=regCacheStack[4]["Control"]["Battery_Power_Reserve"]
            revert["mode"]=regCacheStack[4]["Control"]["Mode"]
            revert['discharge_schedule']=regCacheStack[4]["Control"]["Enable_Discharge_Schedule"]
            if "Battery_Discharge_Rate" in regCacheStack[4]["Control"]:
                revert["dischargeRate"]=regCacheStack[4]["Control"]["Battery_Discharge_Rate"]
            elif "Battery_Discharge_Rate_AC" in regCacheStack[4]["Control"]:
                revert["dischargeRateAC"]=regCacheStack[4]["Control"]["Battery_Discharge_Rate_AC"]
            if "Battery_pause_mode" in regCacheStack[4]["Control"]:
                revert["batteryPauseMode"]=regCacheStack[4]["Control"]["Battery_pause_mode"]
                hasBPM=True
            if "Force_Discharge_Enable" in regCacheStack[4]["Control"]:
                revert["forceDischargeEnable"]=regCacheStack[4]["Control"]["Force_Discharge_Enable"]
            if "Force_Charge_Enable" in regCacheStack[4]["Control"]:
                revert["forceChargeEnable"]=regCacheStack[4]["Control"]["Force_Charge_Enable"]

        reqs=commands.set_battery_soc_reserve(4,GiV_Settings.inverter_type.lower())
        finish=GivLUT.getTime(datetime.now()+timedelta(minutes=exportTime))
        slot=TimeSlot
        slot.start=datetime.strptime(GivLUT.getTime(datetime.now()),"%H:%M")
        slot.end=datetime.strptime(finish,"%H:%M")

        if "3ph" in GiV_Settings.inverter_type.lower():
            reqs.extend(commands.set_force_discharge(True))  # turn on Force Export in 3PH
            reqs.extend(commands.set_force_charge(False))  # turn off Force Charge in 3PH
            reqs.extend(commands.set_battery_discharge_limit_ac(100,GiV_Settings.inverter_type.lower()))
        else:
            reqs.extend(commands.set_battery_discharge_limit(50))
        reqs.extend(commands.set_mode_storage(discharge_slot_2=slot,discharge_for_export=True, inv_type=GiV_Settings.inverter_type.lower()))
        if hasBPM:
            reqs.extend(commands.set_battery_pause_mode(0))
        result = await sendAsyncCommand(reqs,readloop)
        frtouch()   #Force full refresh on next run to update control status
        if result:
            logger.error("Errors in control commands: "+str(result))
            raise Exception(result)
        if exists(".FERunning"+str(GiV_Settings.givtcp_instance)):    # If a forcecharge is already running, change time of revert job to new end time.
            logger.info("Force Export already running, changing end time")
            revert=getFEArgs()[0]   # set new revert object and cancel old revert job
            logger.debug("new revert= "+ str(revert))
        fejob=GivQueue.q.enqueue_in(timedelta(minutes=exportTime),FEResume,revert)
        with open(".FERunning"+str(GiV_Settings.givtcp_instance), 'w') as f:
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

async def FCResume(revert,readloop=False):
    payload={}
    temp={}
    try:
        logger.info("Reverting Force Charge Settings:")
        if "chargeRate" in revert:
            if exists(GivLUT.regcache):      # if there is a cache then grab it
                regCacheStack=GivLUT.get_regcache()
                multi_output_old = regCacheStack[4]
                invmaxrate=int(finditem(multi_output_old,"Invertor_Max_Bat_Rate"))
                batcap=float(finditem(multi_output_old,'Battery_Capacity_kWh'))*1000
                if "3ph" in GiV_Settings.inverter_type.lower():
                    target= round(int(revert['chargeRate'])/invmaxrate,0)
                    temp = await sbcla(target, readloop)
                else:
                    if int(revert['chargeRate']) < int(invmaxrate):
                        target=int(min((int(revert['chargeRate'])/(batcap/2))*50,50))
                    else:
                        target=50
            reqs=commands.set_battery_charge_limit(target)
        elif "chargeRateAC" in revert:
            reqs=commands.set_battery_charge_limit_ac(revert["chargeRateAC"])
        if revert["chargeScheduleEnable"]=="enable":
            enable=True
        else:
            enable=False
        reqs.extend(commands.set_enable_charge(enable))
        slot=TimeSlot
        slot.start=datetime.strptime(revert['start_time'],"%H:%M")
        slot.end=datetime.strptime(revert['end_time'],"%H:%M")
        reqs.extend(commands._set_charge_slot(False,1,slot,GiV_Settings.inverter_type))
        reqs.extend(commands.set_charge_target_only(int(revert["targetSOC"]), inv_type=GiV_Settings.inverter_type.lower()))
        if "batteryPauseMode" in revert:
            reqs.extend(commands.set_battery_pause_mode(GivLUT.battery_pause_mode.index(revert["batteryPauseMode"])))
        if "3ph" in GiV_Settings.inverter_type.lower():
            reqs.extend(commands.set_force_discharge(revert["forceDischargeEnable"]))  # turn back Force Export in 3PH
            reqs.extend(commands.set_force_charge(revert["forceChargeEnable"]))  # turn back Force Charge in 3PH
            reqs.extend(commands.set_ac_charge(revert["forceACChargeEnable"]))  # turn back AC Charge enable in 3PH

        result = await sendAsyncCommand(reqs,readloop)
        if result:
            logger.error("Errors in control commands: "+str(result))
            raise Exception(result)
        frtouch()        
        os.remove(".FCRunning"+str(GiV_Settings.givtcp_instance))
        updateControlCache("Force_Charge","Normal")
        temp['result']="Force Charge Reverted successfully"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        logger.error("Force Charge revert failed: "+str(e))
        temp['result']="Force Charge revert failed: "+str(e)
        os.remove(".FCRunning"+str(GiV_Settings.givtcp_instance))
        logger.error(temp['result'])
    return json.dumps(temp)

def cancelJob(jobid, readloop=False):
    temp={}
    if jobid in GivQueue.q.scheduled_job_registry:
        GivQueue.q.scheduled_job_registry.requeue(jobid, at_front=True)
        temp['result']="Cancelling scheduled task as requested"
        logger.info(temp['result'])
    else:
        temp['result']="Job ID: " + str(jobid) + " not found in redis queue"
        logger.error(temp['result'])
    return json.dumps(temp)

def getFCArgs():
    from rq.job import Job
    # getjobid
    f=open(".FCRunning"+str(GiV_Settings.givtcp_instance), 'r')
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
    f=open(".FERunning"+str(GiV_Settings.givtcp_instance), 'r')
    jobid=f.readline().strip('\n')
    f.close()
    # get the revert details from the old job
    job=Job.fetch(jobid,GivQueue.redis_connection)
    details=job.args
    logger.debug("Previous args= "+str(details))
    GivQueue.q.scheduled_job_registry.remove(jobid) # Remove the job from the schedule
    return (details)

async def forceCharge(chargeTime, readloop=False):
    temp={}
    logger.info("Forcing Charge for "+str(chargeTime)+" minutes")
    try:
        revert={}
        regCacheStack = GivLUT.get_regcache()
        hasBPM=False
        if "regCacheStack" in locals():
            revert["start_time"]=regCacheStack[4]["Timeslots"]["Charge_start_time_slot_1"][:5]
            revert["end_time"]=regCacheStack[4]["Timeslots"]["Charge_end_time_slot_1"][:5]
            if "Battery_Charge_Rate" in regCacheStack[4]["Control"]:
                revert["chargeRate"]=regCacheStack[4]["Control"]["Battery_Charge_Rate"]
            elif "Battery_Charge_Rate_AC" in regCacheStack[4]["Control"]:
                revert["chargeRateAC"]=regCacheStack[4]["Control"]["Battery_Charge_Rate_AC"]
            revert["targetSOC"]=regCacheStack[4]["Control"]["Target_SOC"]
            revert["chargeScheduleEnable"]=regCacheStack[4]["Control"]["Enable_Charge_Schedule"]
            if "Battery_pause_mode" in regCacheStack[4]["Control"]:
                revert["batteryPauseMode"]=regCacheStack[4]["Control"]["Battery_pause_mode"]
                hasBPM=True
            if "Force_Charge_Enable" in regCacheStack[4]["Control"]:
                revert['forceChargeEnable']= regCacheStack[4]["Control"]["Force_Charge_Enable"]
            if "Force_AC_Charge_Enable" in regCacheStack[4]["Control"]:
                revert['forceACChargeEnable']= regCacheStack[4]["Control"]["Force_AC_Charge_Enable"]

        finish=GivLUT.getTime(datetime.now()+timedelta(minutes=chargeTime))
        reqs=commands.set_charge_target_only(100,GiV_Settings.inverter_type.lower())
        slot=TimeSlot
        slot.start=datetime.strptime(GivLUT.getTime(datetime.now()),"%H:%M")
        slot.end=datetime.strptime(finish,"%H:%M")
        reqs.extend(commands._set_charge_slot(False,1,slot, inv_type=GiV_Settings.inverter_type.lower()))
        if "3ph" in GiV_Settings.inverter_type.lower():
            reqs.extend(commands.set_battery_charge_limit_ac(100,GiV_Settings.inverter_type.lower()))
            reqs.extend(commands.set_force_charge(True))
            reqs.extend(commands.set_ac_charge(True))
        else:
            reqs.extend(commands.set_enable_charge(True))
            reqs.extend(commands.set_battery_charge_limit(50))

        # Set Battery Pause Mode only if it exists
        if hasBPM:
            reqs.extend(commands.set_battery_pause_mode(0))
        result= await sendAsyncCommand(reqs,readloop)
        frtouch()   #Force full refresh on next run to update control status
        if result:
            logger.error("Errors in control commands: "+str(result))
            raise Exception(result)
        if exists(".FCRunning"+str(GiV_Settings.givtcp_instance)):    # If a forcecharge is already running, change time of revert job to new end time
            logger.info("Force Charge already running, changing end time")
            revert=getFCArgs()[0]   # set new revert object and cancel old revert job
            logger.critical("new revert= "+ str(revert))
        fcjob=GivQueue.q.enqueue_in(timedelta(minutes=chargeTime),FCResume,revert)
        with open(".FCRunning"+str(GiV_Settings.givtcp_instance), 'w') as f:
            f.write('\n'.join([str(fcjob.id),str(finish)]))
        logger.debug("Force Charge revert jobid is: "+fcjob.id)
        temp['result']="Charge successfully forced for "+str(chargeTime)+" minutes"
        updateControlCache("Force_Charge","Running")

        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Force charge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def tmpPDResume(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Reverting Temp Pause Discharge")
        result=await setDischargeRate(payload,readloop)
        if exists(".tpdRunning_"+str(GiV_Settings.givtcp_instance)): os.remove(".tpdRunning_"+str(GiV_Settings.givtcp_instance))
        temp['result']="Temp Pause Discharge Reverted"
        updateControlCache("Temp_Pause_Discharge","Normal")
        updateControlCache("Battery_Discharge_Rate",payload["dischargeRate"])
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Temp Pause Discharge Resume failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def tempPauseDischarge(pauseTime,readloop=False):
    temp={}
    try:
        logger.debug("Pausing Discharge for "+str(pauseTime)+" minutes")
        #Update read data via pickle
        regCacheStack = GivLUT.get_regcache()
        if "regCacheStack" in locals():
            multi_output_old = regCacheStack[4]
            revertRate=regCacheStack[4]["Control"]["Battery_Discharge_Rate"]
        else:
            revertRate=2600
            
        payload={}
        payload['dischargeRate']=0
        result=await setDischargeRate(payload,readloop)
        payload['dischargeRate']=revertRate
        delay=float(pauseTime*60)
        tpdjob=GivQueue.q.enqueue_in(timedelta(seconds=delay),tmpPDResume,payload)
        finishtime=GivLUT.getTime(datetime.now()+timedelta(minutes=pauseTime))
        with open(".tpdRunning_"+str(GiV_Settings.givtcp_instance), 'w') as f:
            f.write('\n'.join([str(tpdjob.id),str(finishtime)]))
        
        logger.debug("Temp Pause Discharge revert jobid is: "+tpdjob.id)
        temp['result']="Discharge paused for "+str(delay)+" seconds"
        updateControlCache("Temp_Pause_Discharge","Running")
        updateControlCache("Battery_Discharge_Rate",payload["dischargeRate"])
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Pausing Discharge failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def tmpPCResume(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Reverting Temp Pause Charge...")
        result=await setChargeRate(payload,readloop)
        if exists(".tpcRunning_"+str(GiV_Settings.givtcp_instance)): os.remove(".tpcRunning_"+str(GiV_Settings.givtcp_instance))
        temp['result']="Temp Pause Charge Reverted"
        updateControlCache("Temp_Pause_Charge","Normal")
        updateControlCache("Battery_Charge_Rate",payload["chargeRate"])
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Temp Pause Charge Resume failed: " + str(e)
        logger.error (temp['result'])
    return json.dump(temp)

async def tempPauseCharge(pauseTime, readloop=False):
    temp={}
    try:
        logger.debug("Pausing Charge for "+str(pauseTime)+" minutes")
        regCacheStack = GivLUT.get_regcache()
        if "regCacheStack" in locals():
            revertRate=regCacheStack[4]["Control"]["Battery_Charge_Rate"]
        else:
            revertRate=2600
        payload={}
        payload['chargeRate']=0
        result=await setChargeRate(payload,readloop)
        payload['chargeRate']=revertRate
        delay=float(pauseTime*60)
        finishtime=GivLUT.getTime(datetime.now()+timedelta(minutes=pauseTime))
        tpcjob=GivQueue.q.enqueue_in(timedelta(seconds=delay),tmpPCResume,payload)
        with open(".tpcRunning_"+str(GiV_Settings.givtcp_instance), 'w') as f:
            f.write('\n'.join([str(tpcjob.id),str(finishtime)]))
        logger.debug("Temp Pause Charge revert jobid is: "+tpcjob.id)
        temp['result']="Charge paused for "+str(delay)+" seconds"
        updateControlCache("Temp_Pause_Charge","Running")
        updateControlCache("Battery_Charge_Rate",payload["chargeRate"])
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Pausing Charge failed: " + str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def setEcoMode(payload,readloop=False):
    temp={}
    try:
        logger.debug("Setting Eco Mode to: "+str(payload['state']))
        if type(payload) is not dict: payload=json.loads(payload)
        if payload['state']=="enable":
            temp=await sem(True,readloop)
        else:
            temp=await sem(False,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()
        temp['Result']="Error in setting Eco mode: "+str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def setBatteryPauseMode(payload,readloop=False):
    temp={}
    try:
        logger.debug("Setting Battery Pause Mode to: "+str(payload['state']))
        if type(payload) is not dict: payload=json.loads(payload)
        if payload['state'] in GivLUT.battery_pause_mode:
            val=GivLUT.battery_pause_mode.index(payload['state'])
            temp= await sbpm(val,readloop)
            logger.info(temp['result'])
        else:
            temp['result']="Invalid Mode requested: "+ payload['state']
            logger.error(temp['result'])
    except:
        e=sys.exc_info()
        temp['Result']="Error in setting Battery pause mode: "+str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def setLocalControlMode(payload,readloop=False):
    temp={}
    try:
        logger.debug("Setting Local Control Mode to: "+str(payload['state']))
        if type(payload) is not dict: payload=json.loads(payload)
        if payload['state'] in GivLUT.local_control_mode:
            val=GivLUT.local_control_mode.index(payload['state'])
            temp= await slcm(val,readloop)
        else:
            temp['result']="Invalid Mode requested: "+ payload['state']
            logger.error(temp['result'])
    except:
        e=sys.exc_info()
        temp['Result']="Error in setting local control mode: "+str(e)
        logger.error(temp['result'])
    return json.dumps(temp)

async def setBatteryMode(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting Battery Mode to: "+str(payload['mode']))
        if payload['mode']=="Eco":
            temp= await smd(False,readloop)
            saved_battery_reserve = getSavedBatteryReservePercentage()
            temp= await ssc(saved_battery_reserve,readloop)
        elif payload['mode']=="Eco (Paused)":
            temp= await smd(True,readloop)
        elif payload['mode']=="Timed Demand":
            temp= await sbdmd(readloop)
            temp= await ed(readloop)
        elif payload['mode']=="Timed Export":
            temp= await sbdmmp(readloop)
            temp= await ed(readloop)
        else:
            temp['result']="Invalid Mode requested"+ payload['mode']
            logger.error (temp['result'])
            return json.dumps(temp)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Mode failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def setPVInputMode(payload,readloop=False):
    temp={}
    if type(payload) is not dict: payload=json.loads(payload)
    try:
        logger.debug("Setting PV Input mode to: "+ str(payload['state']))
        if payload['state'] in GivLUT.pv_input_mode:
            temp= await spvim(GivLUT.pv_input_mode.index(payload['state']),readloop)
            temp['result']="Setting PV Input Mode was a success"
        else:
            logger.error ("Invalid Mode requested: "+ payload['state'])
            temp['result']="Invalid Mode requested"
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting PV Input Mode failed: " + str(e)
        logger.error (temp['result'])
    return json.dumps(temp)

async def syncDateTime(payload,readloop=False):
    temp={}
    targetresult="Success"
    #convert payload to dateTime components
    try:
        iDateTime=datetime.now()   #format '12/11/2021 09:15:32'
        logger.debug("Syncing inverter time to: "+str(iDateTime))
        #Set Date and Time on inverter
        temp= await sdt(iDateTime,readloop)
        logger.info(temp['result'])
        await asyncio.sleep(2)
        updateControlCache("Sync_Time","disable")
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Syncing inverter DateTime failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

async def setDateTime(payload,readloop=False):
    temp={}
    targetresult="Success"
    if type(payload) is not dict: payload=json.loads(payload)
    #convert payload to dateTime components
    try:
        iDateTime=datetime.strptime(payload['dateTime'],"%d/%m/%Y %H:%M:%S")   #format '12/11/2021 09:15:32'
        logger.debug("Setting inverter time to: "+iDateTime)
        #Set Date and Time on inverter
        temp= await sdt(iDateTime,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting inverter DateTime failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

async def setCarChargeBoost(payload, readloop=False):
    temp={}
    targetresult="Success"
    val=payload['boost']
    try:
        logger.debug("Setting Car Charge Boost to: "+str(val)+"w")
        temp= await sccb(val,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Car Charge Boost failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

async def setBatteryCalibration(payload,readloop=False):
    temp={}
    targetresult="Success"
    if type(payload) is not dict: payload=json.loads(payload)
    if payload['state'] in GivLUT.battery_calibration:
        val=GivLUT.battery_calibration.index(payload['state'])
    try:
        logger.debug("Setting Battery Calibration to: "+str(payload['state']))
        temp= await sbc(val,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Battery Calibration failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

async def setExportLimit(val, readloop=False):
    temp={}
    targetresult="Success"
    try:
        logger.debug("Setting Export Limit to: "+str(val)+"w")
        #Set Date and Time on inverter
        temp= await sel(val,readloop)
        logger.info(temp['result'])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        temp['result']="Setting Export Limit failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

def switchRate(payload,readloop=False):
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
            result="Please restart GivTCP Manually..."
            logger.info(result)
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

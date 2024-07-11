# -*- coding: utf-8 -*-
# version 2022.08.01
from threading import Lock
from givenergy_modbus_async.model.register import Model, Generation
from givenergy_modbus_async.model.plant import Plant, Inverter, EMS, ThreePhaseInverter, Gateway, Battery, BCU, Meter
from givenergy_modbus_async.client.client import commands
from givenergy_modbus_async.model.register import HR
import sys
import json
import logging
import datetime
import pickle
import time
from GivLUT import GivLUT, maxvalues, InvType
from settings import GiV_Settings
from os.path import exists
import os
from datetime import timedelta
import asyncio
from typing import Callable, Optional
from mqtt import GivMQTT

logging.getLogger("givenergy_modbus_async").setLevel(logging.CRITICAL) 
logging.getLogger("rq.worker").setLevel(logging.CRITICAL)

sys.path.append(GiV_Settings.default_path)

givLUT = GivLUT.entity_type
logger = GivLUT.logger

#cacheLock = Lock()

from GivLUT import GivClientAsync

async def watch_plant(
        host: str,
        handler: Optional[Callable] = None,
        refresh_period: float = 15.0,
        full_refresh_period: float = 60,
        num_batteries: int = 2,
        timeout: float = 3,
        retries: int = 5,
        passive: bool = False,
    ):
        totalTimeoutErrors=0
        """Refresh data about the Plant."""
        try:
            await GivClientAsync.client.connect()
            logger.critical("Detecting inverter characteristics...")
            await GivClientAsync.client.detect_plant()
            await GivClientAsync.client.refresh_plant(True, number_batteries=GivClientAsync.client.plant.number_batteries,meter_list=GivClientAsync.client.plant.meter_list)
            #await GivClientAsync.client.close()
            logger.debug ("Running full refresh")
            if handler:
                try:
                    handler(GivClientAsync.client.plant)
                except Exception:
                    e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
                    logger.error ("Error in calling handler: "+str(e))
        except Exception:
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            logger.error ("Error in inital detect/refresh: "+str(e))
            await GivClientAsync.client.close()
            return
        # set last full_refresh time
        lastfulltime=datetime.datetime.now()
        timeoutErrors=0
        while True:
            try:
                await asyncio.sleep(refresh_period)
                # add a check in here to see if it got stuck ( not updated for ages?) and then restart

                if not passive:
                    #Check time since last full_refresh
                    timesincefull=datetime.datetime.now()-lastfulltime
                    if timesincefull.total_seconds() > full_refresh_period or exists(".fullrefresh"):
                        fullRefresh=True
                        logger.debug ("Running full refresh")
                        lastfulltime=datetime.datetime.now()
                        if exists(".fullrefresh"):
                            os.remove(".fullRefresh")
                    else:
                        fullRefresh=False
                        logger.debug ("Running partial refresh")
                    try:
                        #await GivClientAsync.client.connect()
                        reqs = commands.refresh_plant_data(fullRefresh, GivClientAsync.client.plant.number_batteries, slave_addr=GivClientAsync.client.plant.slave_address,isHV=GivClientAsync.client.plant.isHV,additional_holding_registers=GivClientAsync.client.plant.additional_holding_registers,additional_input_registers=GivClientAsync.client.plant.additional_input_registers)
                        result= await GivClientAsync.client.execute(
                            reqs, timeout=timeout, retries=retries, return_exceptions=True
                        )
                        #await GivClientAsync.client.close()
                        hasTimeout=False
                        for res in result:
                            if isinstance(res,TimeoutError):
                                hasTimeout=True
                                raise Exception(res)
                        timeoutErrors=0     # Reset timeouts if all is good this run
                        logger.debug("Data get was successful, now running handler if needed: ")
                    except Exception:
                        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
                        totalTimeoutErrors=totalTimeoutErrors+1
                        # Publish the new total timeout errors

                        timeoutErrors=timeoutErrors+1
                        logger.debug("Error num "+str(timeoutErrors)+" in watch loop execute command: "+str(e))
                        logger.debug("Not running handler")
                        if timeoutErrors>5:
                            logger.error("5 consecutive timeout errors in watch loop. Restarting modbus connection:")
                            await GivClientAsync.client.close()
                            await asyncio.sleep(2)      #Just pause for a moment before trying to reconnect
                            await GivClientAsync.client.connect()
                        continue
                    if handler:
                        try:
                            handler(GivClientAsync.client.plant)
                        except Exception:
                            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
                            logger.error ("Error in calling handler: "+str(e))
            except Exception:
                e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
                logger.error ("Error in Watch Loop: "+str(e))
                await GivClientAsync.client.close()

def updateErrorsCache(value):
    # immediately update broker on Timeout Error
    if GiV_Settings.MQTT_Topic == "":
        GiV_Settings.MQTT_Topic = "GivEnergy"
    Topic=str(GiV_Settings.MQTT_Topic+"/"+GiV_Settings.serial_number+"/Stats/Timeout_Errors")
    GivMQTT.single_MQTT_publish(Topic,str(value))

def getInvModel(plant: Plant):

##### Feels like this needs reviewing and maybe moving to the device models

    inverterModel = InvType
    if not plant.inverter ==None:
        GEInv=plant.inverter
    elif not plant.ems ==None:
        GEInv=plant.ems
    elif not plant.gateway ==None:
        GEInv=plant.gateway

    inverterModel.model=GEInv.model
    inverterModel.generation=GEInv.generation
    inverterModel.phase=GEInv.num_phases
    inverterModel.invmaxrate=GEInv.inverter_max_power
    inverterModel.batterycapacity=GEInv.battery_nominal_capacity

    if inverterModel.generation == Generation.GEN1:
        if inverterModel.model == Model.AC:
            maxBatChargeRate=3000
        elif inverterModel.model == Model.ALL_IN_ONE:
            maxBatChargeRate=6000
        else:
            maxBatChargeRate=2600
    else:
        if inverterModel.model == Model.AC:
            maxBatChargeRate=5000
        else:
            maxBatChargeRate=3600

    # Calc max charge rate
    if inverterModel.phase == 3:
        inverterModel.batmaxrate=GEInv.Battery_Max_Power
    else:
        inverterModel.batmaxrate=min(maxBatChargeRate, inverterModel.batterycapacity*1000/2)

    return inverterModel

def getRaw(plant: Plant):
    if not plant.inverter ==None:
        GEInv: Inverter =plant.inverter
    elif not plant.ems ==None:
        GEInv=plant.ems
    elif not plant.gateway ==None:
        GEInv=plant.gateway
    if plant.isHV:
        HVStack=plant.HVStack
    else:
        GEBat=plant.batteries
    
    #GEBCU=plant.bcu

    Meters=plant.meters
    isHV=plant.isHV
    raw = {}
    bat={}
    meters={}
    inv=GEInv.getall()
    raw['invertor']=inv
    if isHV:
        stacks={}
        for i, stck in enumerate(HVStack):
            stack={}
            stack=stck[0].getall()
            for b in stck[1]:
                if b.is_valid():
                    sn=b.serial_number
                else:
                    sn=b.getsn()
                stack[sn]=b.getall()
            stacks['Stack_'+str(i)]=stack
        raw['HV_Battery_Stacks']=stacks
    else:
        for b in GEBat:
            bat[b.serial_number]=b.getall()
        raw['batteries']=bat
    if Meters:
        for m in Meters:
            meters['Meter_ID_'+str(m)]=Meters[m].getall()
        raw['meters']=meters
    
    return raw

def getMeters(plant: Plant):
    meters={}
    for m in plant.meters:
        temp=plant.meters[m]
        meter={}
        meter['Phase_1_Voltage']=temp.v_phase_1
        meter['Phase_2_Voltage']=temp.v_phase_2
        meter['Phase_3_Voltage']=temp.v_phase_3
        meter['Phase_1_Current']=temp.i_phase_1
        meter['Phase_2_Current']=temp.i_phase_2
        meter['Phase_3_Current']=temp.i_phase_3
        meter['Phase_1_Power']=temp.p_active_phase_1
        meter['Phase_2_Power']=temp.p_active_phase_2
        meter['Phase_3_Power']=temp.p_active_phase_3
        meter['Frequency']=temp.frequency
        meter['Phase_1_Power_Factor']=temp.pf_phase_1
        meter['Phase_2_Power_Factor']=temp.pf_phase_2
        meter['Phase_3_Power_Factor']=temp.pf_phase_3
        meter['Import_Energy_kWh']=temp.e_import_active
        meter['Export_Energy_kWh']=temp.e_export_active
        meters['Meter_ID'+str(m)]=meter
    return meters

def getBatteries(plant: Plant):
    if not plant.inverter ==None:
        GEInv: Inverter =plant.inverter
    elif not plant.ems ==None:
        GEInv=plant.ems
    elif not plant.gateway ==None:
        GEInv=plant.gateway
    isHV=plant.isHV
    batteries2={}
    stack={}
    logger.debug("Getting Battery Details")
    if not isHV:
        GEBat=plant.batteries
        for b in GEBat:
            if b.is_valid():          # Check for empty battery object responses and only process if they are complete (have a serial number)
                logger.debug("Building battery output: ")
                battery = {}
                battery['Battery_Serial_Number'] = b.serial_number
                if b.soc != 0:
                    battery['Battery_SOC'] = b.soc
                #elif b.soc == 0 and 'multi_output_old' in locals():
                #    battery['Battery_SOC'] = multi_output_old['Battery_Details'][b.serial_number]['Battery_SOC']
                elif b.soc == 0 and not 'multi_output_old' in locals():
                    battery['Battery_SOC'] = 1
                battery['Battery_Capacity'] = b.cap_calibrated
                battery['Battery_Design_Capacity'] = b.cap_design
                battery['Battery_Remaining_Capacity'] = b.cap_remaining
                battery['Battery_Firmware_Version'] = b.bms_firmware_version
                battery['Battery_Cells'] = b.num_cells
                battery['Battery_Cycles'] = b.num_cycles
                battery['Battery_USB_present'] = b.usb_device_inserted
                battery['Battery_Temperature'] = b.t_bms_mosfet
                battery['Battery_Voltage'] = b.v_cells_sum
                for i in range(16):
                    battery['Battery_Cell_'+str(i+1)+'_Voltage'] = b.get('v_cell_'+str(i+1).zfill(2))
                battery['Battery_Cell_1_Temperature'] = b.t_cells_01_04
                battery['Battery_Cell_2_Temperature'] = b.t_cells_05_08
                battery['Battery_Cell_3_Temperature'] = b.t_cells_09_12
                battery['Battery_Cell_4_Temperature'] = b.t_cells_13_16
                stack[b.serial_number] = battery
                
                logger.debug("Battery "+str(b.serial_number)+" added")
            else:
                logger.error("Battery Object empty so skipping")
            
            stack['BMS_Temperature']=GEInv.temp_battery
            stack['BMS_Voltage']=GEInv.v_battery
            # Make this always Battery_Stack_1
            batteries2['Battery_Stack_1']=stack
    else:
        HVStack=plant.HVStack
        for num,stack in enumerate(HVStack):
            bcudata={}
            bcudata['Stack_Voltage']=stack[0].battery_voltage
            bcudata['Stack_Current']=stack[0].battery_current
            bcudata['Stack_Power']=stack[0].battery_power
            bcudata['Stack_SOH']=stack[0].battery_soh
            bcudata['Stack_Load_Voltage']=stack[0].load_voltage
            bcudata['Stack_Cycles']=stack[0].number_of_cycles
            bcudata['Stack_SOC_Difference']=stack[0].battery_soc_max-stack[0].battery_soc_min
            bcudata['Stack_SOC_High']=stack[0].battery_soc_max
            bcudata['Stack_SOC_Low']=stack[0].battery_soc_min
            bcudata['Stack_Firmware']=stack[0].pack_software_version
            bcudata['BMS_Temperature']=GEInv.temp_battery
            for b in stack[1]:
                if b.is_valid():
                    sn=b.serial_number
                else:
                    sn=b.getsn()
                if sn.upper().isupper():          # Check for empty battery object responses and only process if they are complete (have a serial number)
                    logger.debug("Building battery output: ")
                    battery = {}
                    battery['Battery_Serial_Number'] = sn
                    for i in range(24):
                        battery['Battery_Cell_'+str(i+1)+'_Voltage'] = b.get('v_cell_'+str(i+1).zfill(2))
                    
                    for i in range(12):
                        battery['Battery_Cell_'+str(i+1)+'_Temperature'] = b.get('t_cell_'+str(i+1).zfill(2))
                    
                    bcudata[sn] = battery
                    logger.debug("Battery "+str(sn)+" added")
                else:
                    logger.error("Battery Object empty so skipping")
            batteries2['Battery_Stack_'+str(num+1)]=bcudata
    return batteries2

def getTimeslots(plant):
    timeslots={}
    controlmode={}
    if not plant.inverter ==None:
        GEInv=plant.inverter
    elif not plant.ems ==None:
        GEInv=plant.ems
    elif not plant.gateway ==None:
        GEInv=plant.gateway
    logger.debug("Getting TimeSlot data")
    timeslots['Discharge_start_time_slot_1'] = GEInv.discharge_slot_1.start.isoformat()
    timeslots['Discharge_end_time_slot_1'] = GEInv.discharge_slot_1.end.isoformat()
    timeslots['Discharge_start_time_slot_2'] = GEInv.discharge_slot_2.start.isoformat()
    timeslots['Discharge_end_time_slot_2'] = GEInv.discharge_slot_2.end.isoformat()
    timeslots['Charge_start_time_slot_1'] = GEInv.charge_slot_1.start.isoformat()
    timeslots['Charge_end_time_slot_1'] = GEInv.charge_slot_1.end.isoformat()
    try:
        if GEInv.model in [Model.ALL_IN_ONE, Model.AC_3PH, Model.HYBRID_3PH, Model.GATEWAY] or (GEInv.generation == Generation.GEN3 and int(GEInv.arm_firmware_version)>302):   #10 slots only apply to AIO, 3ph and new fw on Gen 3
        #if not GEInv.charge_slot_2 == None:
            timeslots['Charge_start_time_slot_2'] = GEInv.charge_slot_2.start.isoformat()
            timeslots['Charge_end_time_slot_2'] = GEInv.charge_slot_2.end.isoformat()
            timeslots['Charge_start_time_slot_3'] = GEInv.charge_slot_3.start.isoformat()
            timeslots['Charge_end_time_slot_3'] = GEInv.charge_slot_3.end.isoformat()
            timeslots['Charge_start_time_slot_4'] = GEInv.charge_slot_4.start.isoformat()
            timeslots['Charge_end_time_slot_4'] = GEInv.charge_slot_4.end.isoformat()
            timeslots['Charge_start_time_slot_5'] = GEInv.charge_slot_5.start.isoformat()
            timeslots['Charge_end_time_slot_5'] = GEInv.charge_slot_5.end.isoformat()
            timeslots['Charge_start_time_slot_6'] = GEInv.charge_slot_6.start.isoformat()
            timeslots['Charge_end_time_slot_6'] = GEInv.charge_slot_6.end.isoformat()
            timeslots['Charge_start_time_slot_7'] = GEInv.charge_slot_7.start.isoformat()
            timeslots['Charge_end_time_slot_7'] = GEInv.charge_slot_7.end.isoformat()
            timeslots['Charge_start_time_slot_8'] = GEInv.charge_slot_8.start.isoformat()
            timeslots['Charge_end_time_slot_8'] = GEInv.charge_slot_8.end.isoformat()
            timeslots['Charge_start_time_slot_9'] = GEInv.charge_slot_9.start.isoformat()
            timeslots['Charge_end_time_slot_9'] = GEInv.charge_slot_9.end.isoformat()
            timeslots['Charge_start_time_slot_10'] = GEInv.charge_slot_10.start.isoformat()
            timeslots['Charge_end_time_slot_10'] = GEInv.charge_slot_10.end.isoformat()
            timeslots['Discharge_start_time_slot_3'] = GEInv.discharge_slot_3.start.isoformat()
            timeslots['Discharge_end_time_slot_3'] = GEInv.discharge_slot_3.end.isoformat()
            timeslots['Discharge_start_time_slot_4'] = GEInv.discharge_slot_4.start.isoformat()
            timeslots['Discharge_end_time_slot_4'] = GEInv.discharge_slot_4.end.isoformat()
            timeslots['Discharge_start_time_slot_5'] = GEInv.discharge_slot_5.start.isoformat()
            timeslots['Discharge_end_time_slot_5'] = GEInv.discharge_slot_5.end.isoformat()
            timeslots['Discharge_start_time_slot_6'] = GEInv.discharge_slot_6.start.isoformat()
            timeslots['Discharge_end_time_slot_6'] = GEInv.discharge_slot_6.end.isoformat()
            timeslots['Discharge_start_time_slot_7'] = GEInv.discharge_slot_7.start.isoformat()
            timeslots['Discharge_end_time_slot_7'] = GEInv.discharge_slot_7.end.isoformat()
            timeslots['Discharge_start_time_slot_8'] = GEInv.discharge_slot_8.start.isoformat()
            timeslots['Discharge_end_time_slot_8'] = GEInv.discharge_slot_8.end.isoformat()
            timeslots['Discharge_start_time_slot_9'] = GEInv.discharge_slot_9.start.isoformat()
            timeslots['Discharge_end_time_slot_9'] = GEInv.discharge_slot_9.end.isoformat()
            timeslots['Discharge_start_time_slot_10'] = GEInv.discharge_slot_10.start.isoformat()
            timeslots['Discharge_end_time_slot_10'] = GEInv.discharge_slot_10.end.isoformat()
            controlmode['Charge_Target_SOC_1'] = GEInv.charge_target_soc_1
            controlmode['Charge_Target_SOC_2'] = GEInv.charge_target_soc_2
            controlmode['Charge_Target_SOC_3'] = GEInv.charge_target_soc_3
            controlmode['Charge_Target_SOC_4'] = GEInv.charge_target_soc_4
            controlmode['Charge_Target_SOC_5'] = GEInv.charge_target_soc_5
            controlmode['Charge_Target_SOC_6'] = GEInv.charge_target_soc_6
            controlmode['Charge_Target_SOC_7'] = GEInv.charge_target_soc_7
            controlmode['Charge_Target_SOC_8'] = GEInv.charge_target_soc_8
            controlmode['Charge_Target_SOC_9'] = GEInv.charge_target_soc_9
            controlmode['Charge_Target_SOC_10'] = GEInv.charge_target_soc_10
            controlmode['Discharge_Target_SOC_1'] = GEInv.discharge_target_soc_1
            controlmode['Discharge_Target_SOC_2'] = GEInv.discharge_target_soc_2
            controlmode['Discharge_Target_SOC_3'] = GEInv.discharge_target_soc_3
            controlmode['Discharge_Target_SOC_4'] = GEInv.discharge_target_soc_4
            controlmode['Discharge_Target_SOC_5'] = GEInv.discharge_target_soc_5
            controlmode['Discharge_Target_SOC_6'] = GEInv.discharge_target_soc_6
            controlmode['Discharge_Target_SOC_7'] = GEInv.discharge_target_soc_7
            controlmode['Discharge_Target_SOC_8'] = GEInv.discharge_target_soc_8
            controlmode['Discharge_Target_SOC_9'] = GEInv.discharge_target_soc_9
            controlmode['Discharge_Target_SOC_10'] = GEInv.discharge_target_soc_10
    except:
        logger.debug("New Charge/Discharge timeslots don't exist for this model")

    if not GEInv.battery_pause_slot_1 == None:
        timeslots['Battery_pause_start_time_slot'] = GEInv.battery_pause_slot_1.start.isoformat()
        timeslots['Battery_pause_end_time_slot'] = GEInv.battery_pause_slot_1.end.isoformat()
    return timeslots,controlmode


def getControls(plant,regCacheStack, inverterModel):
    controlmode={}
    temp={}
    if not plant.inverter ==None:
        GEInv=plant.inverter
    elif not plant.ems ==None:
        GEInv=plant.ems
    elif not plant.gateway ==None:
        GEInv=plant.gateway

    logger.debug("Getting mode control figures")
    # Get Control Mode registers
    if GEInv.enable_charge == True:
        charge_schedule = "enable"
    else:
        charge_schedule = "disable"
    if GEInv.enable_discharge == True:
        discharge_schedule = "enable"
    else:
        discharge_schedule = "disable"
    if GEInv.battery_power_mode == 1:
        batPowerMode="enable"
    else:
        batPowerMode="disable"
    #Get Battery Stat registers
    #battery_reserve = GEInv.battery_discharge_min_power_reserve

    battery_reserve = GEInv.battery_soc_reserve

    # Save a non-100 battery_reserve value for use later in restoring after resuming Eco/Dynamic mode
    # Check to see if we have a saved value already...
    saved_battery_reserve = 0
    if exists(GivLUT.reservepkl):
        with open(GivLUT.reservepkl, 'rb') as inp:
            saved_battery_reserve = pickle.load(inp)

    # Has the saved value changed from the current value? Only carry on if it is different
    if saved_battery_reserve != battery_reserve:
        if battery_reserve < 100:
            try:
                # Pickle the value to use later...
                with open(GivLUT.reservepkl, 'wb') as outp:
                    pickle.dump(battery_reserve, outp, pickle.HIGHEST_PROTOCOL)
                logger.debug ("Saving the battery reserve percentage for later: " + str(battery_reserve))
            except:
                e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
                temp['result'] = "Saving the battery reserve for later failed: " + str(e)
                logger.error (temp['result'])
        else:
            # Value is 100, we don't want to save 100 because we need to restore to a value FROM 100...
            logger.debug ("Saving the battery reserve percentage for later: no need, it's currently at 100 and we don't want to save that.")

    battery_cutoff = GEInv.battery_discharge_min_power_reserve
    target_soc = GEInv.charge_target_soc
    if GEInv.battery_soc_reserve <= GEInv.battery_percent:
        discharge_enable = "enable"
    else:
        discharge_enable = "disable"

    # Get Charge/Discharge Active status

    discharge_rate = int(min((GEInv.battery_discharge_limit/100)*inverterModel.batterycapacity*1000, inverterModel.batmaxrate))
    charge_rate = int(min((GEInv.battery_charge_limit/100)*inverterModel.batterycapacity*1000, inverterModel.batmaxrate))
    if GEInv.battery_discharge_limit_ac:
        discharge_rate_ac = int(GEInv.battery_discharge_limit_ac)       #not on old firmware
        controlmode['Battery_Discharge_Rate_AC'] = discharge_rate_ac
    if GEInv.battery_charge_limit_ac:
        charge_rate_ac = int(GEInv.battery_charge_limit_ac)                #not on old firmware
        controlmode['Battery_Charge_Rate_AC'] = charge_rate_ac
    

    # Calculate Mode
    logger.debug("Calculating Mode...")
    # Calc Mode

    if GEInv.battery_power_mode == 1 and GEInv.enable_discharge == False and GEInv.battery_soc_reserve != 100:
        # Dynamic r27=1 r110=4 r59=0
        mode = "Eco"
    elif GEInv.battery_power_mode == 1 and GEInv.enable_discharge == False and GEInv.battery_soc_reserve == 100:
        # Dynamic r27=1 r110=4 r59=0
        mode = "Eco (Paused)"
    elif GEInv.battery_power_mode == 1 and GEInv.enable_discharge == True:
        # Storage (demand) r27=1 r110=100 r59=1
        mode = "Timed Demand"
    elif GEInv.battery_power_mode == 0 and GEInv.enable_discharge == True:
        # Storage (export) r27=0 r59=1
        mode = "Timed Export"
    elif GEInv.battery_power_mode == 0 and GEInv.enable_discharge == False:
        # Dynamic r27=1 r110=4 r59=0
        mode = "Eco (Paused)"
    else:
        mode = "Unknown"

    logger.debug("Mode is: " + str(mode))

    controlmode['Mode'] = mode
    controlmode['Battery_Power_Reserve'] = battery_reserve
    controlmode['Battery_Power_Cutoff'] = battery_cutoff
    controlmode['Battery_Power_Mode'] = batPowerMode
    controlmode['Target_SOC'] = target_soc

    if not GEInv.battery_pause_mode == None:    #not on old firmware
        controlmode['Battery_pause_mode'] = GivLUT.battery_pause_mode[int(GEInv.battery_pause_mode)]

    controlmode['Battery_Calibration'] = GivLUT.battery_calibration[GEInv.soc_force_adjust]
    controlmode['Enable_Charge_Schedule'] = charge_schedule
    controlmode['Enable_Discharge_Schedule'] = discharge_schedule
    controlmode['Enable_Discharge'] = discharge_enable
    controlmode['Battery_Charge_Rate'] = charge_rate
    controlmode['Battery_Discharge_Rate'] = discharge_rate
    controlmode['Active_Power_Rate']= GEInv.active_power_rate
    controlmode['Reboot_Invertor']="disable"
    controlmode['Reboot_Addon']="disable"
    if not isinstance(regCacheStack[4], int):
        if "Temp_Pause_Discharge" in regCacheStack[4]:
            controlmode['Temp_Pause_Discharge'] = regCacheStack[4]["Control"]["Temp_Pause_Discharge"]
        if "Temp_Pause_Charge" in regCacheStack[4]:
            controlmode['Temp_Pause_Charge'] = regCacheStack[4]["Control"]["Temp_Pause_Charge"]
    else:
        controlmode['Temp_Pause_Charge'] = "Normal"
        controlmode['Temp_Pause_Discharge'] = "Normal"

### Implement Force number option here###

    if exists(".FCRunning"):
        logger.debug("Force Charge is Running")
        controlmode['Force_Charge'] = "Running"
        #Get time left to run in mins and publish to number
        minsremain=getJobFinish(".FCRunning")
        logger.debug("Time remaining is" + str(minsremain))
        controlmode['Force_Charge_Num']=int(minsremain)
    else:
        controlmode['Force_Charge'] = "Normal"
        controlmode['Force_Charge_Num']=0
    if exists(".FERunning"):
        logger.debug("Force_Export is Running")
        controlmode['Force_Export'] = "Running"
        minsremain=getJobFinish(".FERunning")
        logger.debug("Time remaining is" + str(minsremain))
        controlmode['Force_Export_Num']=int(minsremain)
    else:
        logger.debug("Force Export is not Running")
        controlmode['Force_Export'] = "Normal"
        controlmode['Force_Export_Num']=0
    if exists(".tpcRunning"):
        logger.debug("Temp Pause Charge is Running")
        controlmode['Temp_Pause_Charge'] = "Running"
        minsremain=getJobFinish(".tpcRunning")
        logger.debug("Time remaining is" + str(minsremain))
        controlmode['Temp_Pause_Charge_Num']=int(minsremain)
    else:
        controlmode['Temp_Pause_Charge'] = "Normal"
        controlmode['Temp_Pause_Charge_Num']=0
    if exists(".tpdRunning"):
        logger.debug("Temp_Pause_Discharge is Running")
        controlmode['Temp_Pause_Discharge'] = "Running"
        minsremain=getJobFinish(".tpdRunning")
        logger.debug("Time remaining is" + str(minsremain))
        controlmode['Temp_Pause_Discharge_Num']=int(minsremain)
    else:
        controlmode['Temp_Pause_Discharge'] = "Normal"
        controlmode['Temp_Pause_Discharge_Num']=0
    return controlmode

def processInverterInfo(plant: Plant):
    energy_total_output = {}
    energy_today_output = {}
    power_output = {}
    controlmode = {}
    power_flow_output = {}
    inverter = {}
    inverterModel= InvType
    multi_output={}
    GEInv=plant.inverter
    GEBat=plant.batteries
    Meters=plant.meters
    isHV=plant.isHV
    inverterModel=getInvModel(plant)

############  Energy Stats    ############

    # Total Energy Figures
    logger.debug("Getting Total Energy Data")
    if not isHV:
        #if GEInv.e_battery_charge_total == 0 and GEInv.e_battery_discharge_total == 0 and not GiV_Settings.numBatteries==0:  # If no values in "nomal" registers then grab from back up registers - for some f/w versions
        if GEBat[0].e_battery_charge_total == 0 and GEBat[0].e_battery_discharge_total == 0 and len(GEBat)>0:  # If no values in "nomal" registers then grab from back up registers - for some f/w versions
            energy_total_output['Battery_Charge_Energy_Total_kWh'] = GEBat[0].e_battery_charge_total_2
            energy_total_output['Battery_Discharge_Energy_Total_kWh'] = GEBat[0].e_battery_discharge_total_2
        else:
            energy_total_output['Battery_Charge_Energy_Total_kWh'] = GEBat[0].e_battery_charge_total
            energy_total_output['Battery_Discharge_Energy_Total_kWh'] = GEBat[0].e_battery_discharge_total
    energy_total_output['Export_Energy_Total_kWh'] = GEInv.e_grid_out_total
    energy_total_output['Import_Energy_Total_kWh'] = GEInv.e_grid_in_total
    energy_total_output['Invertor_Energy_Total_kWh'] = GEInv.e_inverter_out_total
    energy_total_output['PV_Energy_Total_kWh'] = GEInv.e_pv_total
    energy_total_output['AC_Charge_Energy_Total_kWh'] = GEInv.e_inverter_in_total

    if inverterModel.model == Model.HYBRID:
        energy_total_output['Load_Energy_Total_kWh'] = round((energy_total_output['Invertor_Energy_Total_kWh']-energy_total_output['AC_Charge_Energy_Total_kWh']) -
                                                                (energy_total_output['Export_Energy_Total_kWh']-energy_total_output['Import_Energy_Total_kWh']), 2)
    else:
        energy_total_output['Load_Energy_Total_kWh'] = round((energy_total_output['Invertor_Energy_Total_kWh']-energy_total_output['AC_Charge_Energy_Total_kWh']) -
                                                                (energy_total_output['Export_Energy_Total_kWh']-energy_total_output['Import_Energy_Total_kWh'])+energy_total_output['PV_Energy_Total_kWh'], 2)

    energy_total_output['Self_Consumption_Energy_Total_kWh'] = round(energy_total_output['PV_Energy_Total_kWh']-energy_total_output['Export_Energy_Total_kWh'], 2)


    # Energy Today Figures
    logger.debug("Getting Today Energy Data")
    energy_today_output['PV_Energy_Today_kWh'] = GEInv.e_pv1_day+GEInv.e_pv2_day
    energy_today_output['Import_Energy_Today_kWh'] = GEInv.e_grid_in_day
    energy_today_output['Export_Energy_Today_kWh'] = GEInv.e_grid_out_day
    energy_today_output['AC_Charge_Energy_Today_kWh'] = GEInv.e_inverter_in_day
    energy_today_output['Invertor_Energy_Today_kWh'] = GEInv.e_inverter_out_day
    energy_today_output['Self_Consumption_Energy_Today_kWh'] = round(energy_today_output['PV_Energy_Today_kWh'], 2)-round(energy_today_output['Export_Energy_Today_kWh'], 2)

    if inverterModel.model == Model.HYBRID:
        energy_today_output['Load_Energy_Today_kWh'] = round((energy_today_output['Invertor_Energy_Today_kWh']-energy_today_output['AC_Charge_Energy_Today_kWh']) -
                                                                (energy_today_output['Export_Energy_Today_kWh']-energy_today_output['Import_Energy_Today_kWh']), 2)
    else:
        energy_today_output['Load_Energy_Today_kWh'] = round((energy_today_output['Invertor_Energy_Today_kWh']-energy_today_output['AC_Charge_Energy_Today_kWh']) -
                                                                (energy_today_output['Export_Energy_Today_kWh']-energy_today_output['Import_Energy_Today_kWh'])+energy_today_output['PV_Energy_Today_kWh'], 2)

    checksum = 0
    for item in energy_today_output:
        checksum = checksum+energy_today_output[item]
    if checksum == 0 and GEInv.system_time.hour == 0 and GEInv.system_time.minute == 0:
        with GivLUT.cachelock:
            if exists(GivLUT.regcache):
                # remove regcache at midnight
                logger.debug("Energy Today is Zero and its midnight so resetting regCache")
                os.remove(GivLUT.regcache)


############  Core Power Stats    ############

    # PV Power
    logger.debug("Getting PV Power")
    PV_power_1 = GEInv.p_pv1
    PV_power_2 = GEInv.p_pv2
    PV_power = PV_power_1+PV_power_2
    if PV_power < 15000:
        power_output['PV_Power_String_1'] = PV_power_1
        power_output['PV_Power_String_2'] = PV_power_2
        power_output['PV_Power'] = PV_power
    power_output['PV_Voltage_String_1'] = GEInv.v_pv1
    power_output['PV_Voltage_String_2'] = GEInv.v_pv2
    power_output['PV_Current_String_1'] = GEInv.i_pv1*10
    power_output['PV_Current_String_2'] = GEInv.i_pv2*10
    power_output['Grid_Voltage'] = GEInv.v_ac1
    power_output['Grid_Current'] = GEInv.i_grid_port 

    # Grid Power
    logger.debug("Getting Grid Power")
    grid_power = GEInv.p_grid_out
    if grid_power < 0:
        import_power = abs(grid_power)
        export_power = 0
    elif grid_power > 0:
        import_power = 0
        export_power = abs(grid_power)
    else:
        import_power = 0
        export_power = 0
    power_output['Grid_Power'] = grid_power
    power_output['Import_Power'] = import_power
    power_output['Export_Power'] = export_power

    # EPS Power
    logger.debug("Getting EPS Power")
    power_output['EPS_Power'] = GEInv.p_eps_backup

    # Inverter Power
    logger.debug("Getting PInv Power")
    inverter_power = GEInv.p_inverter_out
    if -inverterModel.invmaxrate <= inverter_power <=inverterModel.invmaxrate:
        power_output['Invertor_Power'] = inverter_power
    if inverter_power < 0:
        power_output['AC_Charge_Power'] = abs(inverter_power)
    else:
        power_output['AC_Charge_Power'] = 0

    # Load Power
    logger.debug("Getting Load Power")
    Load_power = GEInv.p_load_demand
    if Load_power < 15500:
        power_output['Load_Power'] = Load_power

    # Self Consumption
    logger.debug("Getting Self Consumption Power")
    power_output['Self_Consumption_Power'] = max(Load_power - import_power, 0)


############  Power Flow Stats    ############

    # Solar to H/B/G
    logger.debug("Getting Solar to H/B/G Power Flows")
    if PV_power > 0:
        S2H = min(PV_power, Load_power)
        power_flow_output['Solar_to_House'] = S2H
        power_flow_output['Solar_to_Grid'] = export_power

    else:
        power_flow_output['Solar_to_House'] = 0
        power_flow_output['Solar_to_Grid'] = 0

    # Grid to Battery/House Power
    logger.debug("Getting Grid to Battery/House Power Flow")
    if import_power > 0:
        power_flow_output['Grid_to_House'] = import_power
    else:
        power_flow_output['Grid_to_House'] = 0

    ######## Grab output history to allow data smoothing ########

    # Grab previous data from Pickle and use it validate any outrageous changes
    with GivLUT.cachelock:
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack = pickle.load(inp)
                multi_output_old = regCacheStack[4]
        else:
            regCacheStack = [0, 0, 0, 0, 0]

    ######## Battery Stats only if there are batteries...  ########
    logger.debug("Getting SOC")
#        if int(GiV_Settings.numBatteries) > 0:  # only do this if there are batteries
    if GEInv.battery_percent != 0:
        power_output['SOC'] = GEInv.battery_percent
    elif GEInv.battery_percent == 0 and 'multi_output_old' in locals():
        power_output['SOC'] = multi_output_old['Power']['Power']['SOC']
        logger.error("\"Battery SOC\" reported as: "+str(GEInv.battery_percent)+"% so using previous value")
    elif GEInv.battery_percent == 0 and not 'multi_output_old' in locals():
        power_output['SOC'] = 1
        logger.error("\"Battery SOC\" reported as: "+str(GEInv.battery_percent)+"% and no previous value so setting to 1%")
    power_output['SOC_kWh'] = round((int(power_output['SOC'])*(inverterModel.batterycapacity))/100,2)

    # Energy Stats
    logger.debug("Getting Battery Energy Data")
    energy_today_output['Battery_Charge_Energy_Today_kWh'] = GEInv.e_battery_charge_today
    energy_today_output['Battery_Discharge_Energy_Today_kWh'] = GEInv.e_battery_discharge_today
    energy_today_output['Battery_Throughput_Today_kWh'] = GEInv.e_battery_charge_today+GEInv.e_battery_discharge_today
    energy_total_output['Battery_Throughput_Total_kWh'] = GEInv.e_battery_throughput_total

######## Get Control Data ########

    controlmode={}
    controlmode.update(getControls(plant,regCacheStack,inverterModel))


############  Battery Power Stats    ############

    # Battery Power
    logger.debug ("Getting Power data")
    Battery_power = GEInv.p_battery
    if not exists(GivLUT.firstrun):    #GiV_Settings.first_run:          # Make sure that we publish the HA message for both Charge and Discharge times
        power_output['Charge_Time_Remaining'] = 0
        power_output['Charge_Completion_Time'] = datetime.datetime.now().replace(tzinfo=GivLUT.timezone).isoformat()
        power_output['Discharge_Time_Remaining'] = 0
        power_output['Discharge_Completion_Time'] = datetime.datetime.now().replace(tzinfo=GivLUT.timezone).isoformat()
    if Battery_power >= 0:
        discharge_power = abs(Battery_power)
        charge_power = 0
        power_output['Charge_Time_Remaining'] = 0
        #power_output['Charge_Completion_Time'] = finaltime.replace(tzinfo=GivLUT.timezone).isoformat()
        if discharge_power!=0:
            # Time to get from current SOC to battery Reserve at the current rate
            power_output['Discharge_Time_Remaining'] = max(int(inverterModel.batterycapacity*((power_output['SOC'] - controlmode['Battery_Power_Reserve'])/100) / (discharge_power/1000) * 60),0)
            finaltime=datetime.datetime.now() + timedelta(minutes=power_output['Discharge_Time_Remaining'])
            power_output['Discharge_Completion_Time'] = finaltime.replace(tzinfo=GivLUT.timezone).isoformat()
        else:
            power_output['Discharge_Time_Remaining'] = 0
            #power_output['Discharge_Completion_Time'] = datetime.datetime.now().replace(tzinfo=GivLUT.timezone).isoformat()
    elif Battery_power <= 0:
        discharge_power = 0
        charge_power = abs(Battery_power)
        power_output['Discharge_Time_Remaining'] = 0
        #power_output['Discharge_Completion_Time'] = datetime.datetime.now().replace(tzinfo=GivLUT.timezone).isoformat()
        if charge_power!=0:
            # Time to get from current SOC to target SOC at the current rate (Target SOC-Current SOC)xBattery Capacity
            power_output['Charge_Time_Remaining'] = max(int(inverterModel.batterycapacity*((controlmode['Target_SOC'] - power_output['SOC'])/100) / (charge_power/1000) * 60),0)
            finaltime=datetime.datetime.now() + timedelta(minutes=power_output['Charge_Time_Remaining'])
            power_output['Charge_Completion_Time'] = finaltime.replace(tzinfo=GivLUT.timezone).isoformat()
        else:
            power_output['Charge_Time_Remaining'] = 0
            #power_output['Charge_Time_Remaining'] = datetime.datetime.now().replace(tzinfo=GivLUT.timezone).isoformat()
    power_output['Battery_Power'] = Battery_power
    power_output['Battery_Voltage'] = GEInv.v_battery
    power_output['Battery_Current'] = GEInv.i_battery
    power_output['Charge_Power'] = charge_power
    power_output['Discharge_Power'] = discharge_power
    if GEInv.f_ac1>100:
        freq=GEInv.f_ac1/10
    else:
        freq=GEInv.f_ac1
    power_output['Grid_Frequency'] = freq
    if GEInv.f_eps_backup>100:
        freq=GEInv.f_eps_backup/10
    else:
        freq=GEInv.f_eps_backup
    power_output['Inverter_Output_Frequency'] = freq
    power_output['Combined_Generation_Power'] = GEInv.p_combined_generation

    # Power flows
    logger.debug("Getting Solar to H/B/G Power Flows")
    if PV_power > 0:
        S2H = min(PV_power, Load_power)
        power_flow_output['Solar_to_House'] = S2H
        S2B = max((PV_power-S2H)-export_power, 0)
        power_flow_output['Solar_to_Battery'] = S2B
        power_flow_output['Solar_to_Grid'] = max(PV_power - S2H - S2B, 0)

    else:
        power_flow_output['Solar_to_House'] = 0
        power_flow_output['Solar_to_Battery'] = 0
        power_flow_output['Solar_to_Grid'] = 0

    # Battery to House
    logger.debug("Getting Battery to House Power Flow")
    B2H = max(discharge_power-export_power, 0)
    power_flow_output['Battery_to_House'] = B2H

    # Grid to Battery/House Power
    logger.debug("Getting Grid to Battery/House Power Flow")
    if import_power > 0:
        power_flow_output['Grid_to_Battery'] = charge_power-max(PV_power-Load_power, 0)
        power_flow_output['Grid_to_House'] = max(import_power-charge_power, 0)

    else:
        power_flow_output['Grid_to_Battery'] = 0
        power_flow_output['Grid_to_House'] = 0

    # Battery to Grid Power
    logger.debug("Getting Battery to Grid Power Flow")
    if export_power > 0:
        power_flow_output['Battery_to_Grid'] = max(discharge_power-B2H, 0)
    else:
        power_flow_output['Battery_to_Grid'] = 0

    

    # Check for all zeros
    checksum = 0
    for item in energy_total_output:
        checksum = checksum+energy_total_output[item]
    if checksum == 0:
        raise ValueError("All zeros returned by inverter, skipping update")


    ######## Grab Timeslots ########
    res = {}
    res=getTimeslots(plant)
    timeslots={}
    timeslots.update(res[0])
    controlmode.update(res[1])

    ######## Get Inverter Details ########
    inverter = {}
    logger.debug("Getting inverter Details")
    inverter['Battery_Type'] = GEInv.battery_type.name.capitalize()
    inverter['Battery_Capacity_kWh'] = inverterModel.batterycapacity
    inverter['Invertor_Serial_Number'] = plant.inverter_serial_number
    inverter['Modbus_Version'] = GEInv.modbus_version
    inverter['Invertor_Firmware'] = GEInv.firmware_version
    inverter['Invertor_Time'] = GEInv.system_time.replace(tzinfo=GivLUT.timezone).isoformat()
    metertype = GEInv.meter_type.name.capitalize()
    inverter['Meter_Type'] = metertype
    inverter['Invertor_Type'] = inverterModel.generation.name.capitalize() + " " + inverterModel.model.name.capitalize()
    inverter['Invertor_Max_Inv_Rate'] = inverterModel.invmaxrate
    inverter['Invertor_Max_Bat_Rate'] = inverterModel.batmaxrate
    inverter['Invertor_Temperature'] = GEInv.temp_inverter_heatsink
    inverter['Export_Limit']=GEInv.grid_port_max_power_output

    ######## Get Meter Details ########

    meters={}
    meters.update(getMeters(plant))

    ######## Get Battery Details ########

    batteries2 = {}
    batteries2.update(getBatteries(plant))

        ######## Create multioutput and publish #########
    energy = {}
    energy["Today"] = energy_today_output
    energy["Total"] = energy_total_output
    power = {}
    power["Power"] = power_output
    power["Flows"] = power_flow_output
    multi_output["Power"] = power
    multi_output[GEInv.serial_number] = inverter
    multi_output["Energy"] = energy
    multi_output["Timeslots"] = timeslots
    multi_output["Control"] = controlmode
    multi_output["Battery_Details"] = batteries2
    multi_output["Meter_Details"] = meters
#    if GiV_Settings.Print_Raw_Registers:
    multi_output['raw'] = getRaw(plant)
    return multi_output

def processEMSInfo(plant: Plant):
    multi_output={}
    GEInv=plant.ems
    # Grab previous data from Pickle and use it validate any outrageous changes
    with GivLUT.cachelock:
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack = pickle.load(inp)
                multi_output_old = regCacheStack[4]
        else:
            regCacheStack = [0, 0, 0, 0, 0]

    ems={}
    ems['status']=GEInv.status.name.capitalize()
    ems['Inverter_Count']=GEInv.inverter_count
    ems['Meter_Count']=GEInv.meter_count
    ems['Car_Charge_Count']=GEInv.expected_car_charger_count
    ems['Plant_Status']=GEInv.plant_status.name.capitalize()  # Is this mode?
    ems['Serial_Number']=GEInv.getsn()
    ems['Invertor_Type'] = GEInv.generation + " - " + GEInv.model.name.capitalize()
    ems['Invertor_Firmware']=GEInv.firmware_version
    ems['System_Time']=GEInv.system_time
    ems['Remaining_Battery_Wh']=GEInv.remaining_battery_wh
    ems['Invertor_Serial_Number']=plant.inverter_serial_number
    ems['Export_Limit']=GEInv.grid_port_max_power_output
    
    inverters={}
    if GEInv.inverter_1_power:
        inv1={}
        inv1['Power']=GEInv.inverter_1_power
        inv1['SOC']=GEInv.inverter_1_soc
        inv1['Temperature']=GEInv.inverter_1_temp
        inv1['Serial_Number']=GEInv.inverter_1_serial_number
        inv1['status']=GEInv.inverter_1_status
        inverters[GEInv.inverter_1_serial_number]=inv1

    if GEInv.inverter_2_power:
        inv2={}
        inv2['Power']=GEInv.inverter_2_power
        inv2['SOC']=GEInv.inverter_2_soc
        inv2['Temperature']=GEInv.inverter_2_temp
        inv2['Serial_Number']=GEInv.inverter_2_serial_number
        inv2['status']=GEInv.inverter_2_status
        inverters[GEInv.inverter_2_serial_number]=inv2

    if GEInv.inverter_3_power:
        inv3={}
        inv3['Power']=GEInv.inverter_3_power
        inv3['SOC']=GEInv.inverter_3_soc
        inv3['Temperature']=GEInv.inverter_3_temp
        inv3['Serial_Number']=GEInv.inverter_3_serial_number
        inv3['status']=GEInv.inverter_3_status
        inverters[GEInv.inverter_3_serial_number]=inv3
    
    if GEInv.inverter_4_power:
        inv4={}
        inv4['Power']=GEInv.inverter_4_power
        inv4['SOC']=GEInv.inverter_4_soc
        inv4['Temperature']=GEInv.inverter_4_temp
        inv4['Serial_Number']=GEInv.inverter_4_serial_number
        inv4['status']=GEInv.inverter_4_status
        inverters[GEInv.inverter_4_serial_number]=inv4


    power_output={}
    power_output['Grid_Power']=GEInv.grid_meter_power
    power_output['Calculated_Load_Power']=GEInv.calc_load_power
    power_output['Measured_Load_Power']=GEInv.measured_load_power
    power_output['Generation_Load_Power']=GEInv.total_generation_load_power
    power_output['Total_Power']=GEInv.p_inverter_active
    power_output['Total_Battery_Power']=GEInv.total_battery_power
    power_output['Other_Battery_Power']=GEInv.other_battery_power

    energy={}
    energy_total_output = {}
    energy_today_output = {}
    energy_total_output['Generation_Energy_Total_kWh']=GEInv.e_generation_total
    energy_total_output['Inverter_Out_Energy_Total_kWh']=GEInv.e_inverter_out_total
    energy_total_output['Inverter_In_Energy_Total_kWh']=GEInv.e_inverter_in_total
    energy_total_output['Export_Energy_Total_kWh']=GEInv.e_grid_out_total
    energy_total_output['Import_Energy_Total_kWh']=GEInv.e_grid_in_total
    
    energy_today_output['Export_Energy_Today_kWh']=GEInv.e_grid_out_day
    energy_today_output['Import_Energy_Today_kWh']=GEInv.e_grid_in_day
    energy_today_output['Inverter_In_Energy_Today_kWh']=GEInv.e_inverter_in_day
    energy_today_output['Inverter_Out_Energy_Today_kWh']=GEInv.e_inverter_out_today
    energy_today_output['Generation_Energy_Today_kWh']=GEInv.e_generation_day
    

    meter={}
    meter['Meter_1_Power']=GEInv.meter_1_power
    meter['Meter_2_Power']=GEInv.meter_2_power
    meter['Meter_3_Power']=GEInv.meter_3_power
    meter['Meter_4_Power']=GEInv.meter_4_power
    meter['Meter_5_Power']=GEInv.meter_5_power
    meter['Meter_6_Power']=GEInv.meter_6_power
    meter['Meter_7_Power']=GEInv.meter_7_power
    meter['Meter_8_Power']=GEInv.meter_8_power
    meter['Meter_1_Status']=GEInv.meter_1_status
    meter['Meter_2_Status']=GEInv.meter_2_status
    meter['Meter_3_Status']=GEInv.meter_3_status
    meter['Meter_4_Status']=GEInv.meter_4_status
    meter['Meter_5_Status']=GEInv.meter_5_status
    meter['Meter_6_Status']=GEInv.meter_6_status
    meter['Meter_7_Status']=GEInv.meter_7_status
    meter['Meter_8_Status']=GEInv.meter_8_status

    controlmode = {}
    #controlmode['Plant_Control']=GEInv.enable_plant_control
    controlmode['EMS_Discharge_Target_SOC_1']=GEInv.discharge_target_1
    controlmode['EMS_Discharge_Target_SOC_2']=GEInv.discharge_target_2
    controlmode['EMS_Discharge_Target_SOC_3']=GEInv.discharge_target_3
    controlmode['EMS_Charge_Target_SOC_1']=GEInv.charge_target_1
    controlmode['EMS_Charge_Target_SOC_2']=GEInv.charge_target_2
    controlmode['EMS_Charge_Target_SOC_3']=GEInv.charge_target_3
    controlmode['Export_Target_SOC_1']=GEInv.export_target_1
    controlmode['Export_Target_SOC_2']=GEInv.export_target_2
    controlmode['Export_Target_SOC_3']=GEInv.export_target_3
    controlmode['Car_Charge_Mode']=GivLUT.car_charge_mode[GEInv.car_charge_mode]
    controlmode['Car_Charge_Boost']=GEInv.car_charge_boost
    controlmode['Plant_Charge_Compensation']=GEInv.plant_charge_compensation
    controlmode['Plant_Discharge_Compensation']=GEInv.plant_discharge_compensation
    
    timeslots = {}
    logger.debug("Getting TimeSlot data")
    timeslots['EMS_Discharge_start_time_slot_1'] = GEInv.discharge_slot_1.start.isoformat()
    timeslots['EMS_Discharge_end_time_slot_1'] = GEInv.discharge_slot_1.end.isoformat()
    timeslots['EMS_Discharge_start_time_slot_2'] = GEInv.discharge_slot_2.start.isoformat()
    timeslots['EMS_Discharge_end_time_slot_2'] = GEInv.discharge_slot_2.end.isoformat()
    timeslots['EMS_Discharge_start_time_slot_3'] = GEInv.discharge_slot_3.start.isoformat()
    timeslots['EMS_Discharge_end_time_slot_3'] = GEInv.discharge_slot_3.end.isoformat()
    timeslots['EMS_Charge_start_time_slot_1'] = GEInv.charge_slot_1.start.isoformat()
    timeslots['EMS_Charge_end_time_slot_1'] = GEInv.charge_slot_1.end.isoformat()
    timeslots['EMS_Charge_start_time_slot_2'] = GEInv.charge_slot_2.start.isoformat()
    timeslots['EMS_Charge_end_time_slot_2'] = GEInv.charge_slot_2.end.isoformat()
    timeslots['EMS_Charge_start_time_slot_3'] = GEInv.charge_slot_3.start.isoformat()
    timeslots['EMS_Charge_end_time_slot_3'] = GEInv.charge_slot_3.end.isoformat()
    timeslots['Export_start_time_slot_1'] = GEInv.export_slot_1.start.isoformat()
    timeslots['Export_end_time_slot_1'] = GEInv.export_slot_1.end.isoformat()
    timeslots['Export_start_time_slot_2'] = GEInv.export_slot_2.start.isoformat()
    timeslots['Export_end_time_slot_2'] = GEInv.export_slot_2.end.isoformat()
    timeslots['Export_start_time_slot_3'] = GEInv.export_slot_3.start.isoformat()
    timeslots['Export_end_time_slot_3'] = GEInv.export_slot_3.end.isoformat()

    #if GiV_Settings.Print_Raw_Registers:
    multi_output['raw'] = getRaw(plant)

    multi_output['Power']=power_output
    multi_output['Power']['Meters']=meter
    multi_output['Inverters']=inverters
    multi_output['Control']=controlmode
    multi_output['Timeslots']=timeslots
    multi_output[GEInv.serial_number]=ems
    energy['Today']=energy_today_output
    energy['Total']=energy_total_output
    multi_output['Energy']=energy

    return multi_output

def processGatewayInfo(plant: Plant):
    GEInv=plant.gateway
    inverterModel=InvType
    inverterModel=getInvModel(plant)

    # Grab previous data from Pickle and use it validate any outrageous changes
    with GivLUT.cachelock:
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack = pickle.load(inp)
                multi_output_old = regCacheStack[4]
        else:
            regCacheStack = [0, 0, 0, 0, 0]

    multi_output={}
    gateway={}
    gateway['Invertor_Type'] = GEInv.generation + " - " + GEInv.model.name.capitalize()
    gateway['Invertor_Serial_Number']=plant.inverter_serial_number
    #gateway['Invertor_Firmware']=GEInv.firmware_version
    gateway['Gateway_Software_Version']=GEInv.software_version
    gateway['Parallel_Total_AIO_Number']=GEInv.parallel_aio_num
    gateway['Parallel_Total_AIO_Online_Number']=GEInv.parallel_aio_online_num
    gateway['Gateway_State']=GEInv.aio_state.name.capitalize()
    gateway['Gateway_Mode']=GEInv.work_mode.name.replace("_"," ").capitalize()
    gateway['Export_Limit']=GEInv.grid_port_max_power_output

    #gateway['DO_State']=GEInv.do_state
    #gateway['DI_State']=GEInv.di_state

    power_output={}
    power_output['Grid_Voltage']=GEInv.v_grid
    power_output['Grid_Current']=GEInv.i_grid
    power_output['Load_Voltage']=GEInv.v_load
    power_output['Load_Current']=GEInv.i_load
    power_output['PV_Current']=GEInv.i_pv
    power_output['Grid_Power']=GEInv.p_ac1
    power_output['PV_Power']=GEInv.p_pv
    power_output['Load_Power']=GEInv.p_load
    power_output['Liberty_Power']=-GEInv.p_liberty      #invert to get negative for export
    power_output['Grid_Relay_Voltage']=GEInv.v_grid_relay
    power_output['Inverter_Relay_Voltage']=GEInv.v_inverter_relay
    power_output['Total_Gateway_Power']=GEInv.p_aio_total

    inverters={}
    swv=int(GEInv.software_version[-2:])
    if GEInv.e_aio1_charge_today:
        inv1={}
        inv1['AC_Charge_Energy_Today_kWh']=GEInv.e_aio1_charge_today
        inv1['AC_Charge_Energy_Total_kWh']=round(GEInv.e_aio1_charge_total/1000,2)
        inv1['AC_Discharge_Energy_Today_kWh']=GEInv.e_aio1_discharge_today
        inv1['AC_Discharge_Energy_Total_kWh']=round(GEInv.e_aio1_discharge_total/1000,2)
        inv1['SOC']=GEInv.aio1_soc
        inv1['Invertor_Power']=-GEInv.p_aio1_inverter           #invert to get negative for export
        if swv>9:
            inv1['AIO_1_Serial_Number']=GEInv.aio1_serial_number_new
        else:
            inv1['AIO_1_Serial_Number']=GEInv.aio1_serial_number
        #inverters[GEInv.aio1_serial_number]=inv1
        inverters["AIO_1"]=inv1
    if GEInv.e_aio2_charge_today:
        inv2={}
        inv2['AC_Charge_Energy_Today_kWh']=GEInv.e_aio2_charge_today
        inv2['AC_Charge_Energy_Total_kWh']=round(GEInv.e_aio2_charge_total/1000,2)
        inv2['AC_Discharge_Energy_Today_kWh']=GEInv.e_aio2_discharge_today
        inv2['AC_Discharge_Energy_Total_kWh']=round(GEInv.e_aio2_discharge_total/1000,2)
        inv2['SOC']=GEInv.aio2_soc
        inv2['Invertor_Power']=-GEInv.p_aio2_inverter           #invert to get negative for export
        if swv>9:
            inv2['AIO_2_Serial_Number']=GEInv.aio2_serial_number_new
        else:
            inv2['AIO_2_Serial_Number']=GEInv.aio2_serial_number
        #inverters[GEInv.aio2_serial_number]=inv2
        inverters["AIO_2"]=inv2
    if GEInv.e_aio3_charge_today:
        inv3={}
        inv3['AC_Charge_Energy_Today_kWh']=GEInv.e_aio3_charge_today
        inv3['AC_Charge_Energy_Total_kWh']=round(GEInv.e_aio3_charge_total/1000,2)
        inv3['AC_Discharge_Energy_Today_kWh']=GEInv.e_aio3_discharge_today
        inv3['AC_Discharge_Energy_Total_kWh']=round(GEInv.e_aio3_discharge_total/1000,2)
        inv3['SOC']=GEInv.aio3_soc
        inv3['Invertor_Power']=-GEInv.p_aio3_inverter           #invert to get negative for export
        if swv>9:
            inv3['AIO_3_Serial_Number']=GEInv.aio3_serial_number_new
        else:
            inv3['AIO_3_Serial_Number']=GEInv.aio3_serial_number
        #inverters[GEInv.aio3_serial_number]=inv3
        inverters["AIO_3"]=inv3
    
    energy = {}
    energy_today_output={}
    energy_today_output['Export_Energy_Today_kWh']=GEInv.e_grid_export_today
    energy_today_output['PV_Energy_Today_kWh']=GEInv.e_pv_today
    energy_today_output['Import_Energy_Today_kWh']=GEInv.e_grid_import_today
    energy_today_output['Load_Energy_Today_kWh']=GEInv.e_load_today
    energy_today_output['Battery_Charge_Energy_Today_kWh']=GEInv.e_battery_charge_today
    energy_today_output['Battery_Discharge_Energy_Today_kWh']=GEInv.e_battery_discharge_today
    energy_today_output['Parallel_Total_Charge_Energy_Today_kWh']=GEInv.e_aio_charge_today
    energy_today_output['Parallel_Total_Discharge_Energy_Today_kWh']=GEInv.e_aio_discharge_today

    energy_total_output={}
    energy_total_output['Import_Energy_Total_kWh']=round(GEInv.e_grid_import_total/1000,2)
    energy_total_output['PV_Energy_Total_kWh']=round(GEInv.e_pv_total/1000,2)
    energy_total_output['Export_Energy_Total_kWh']=round(GEInv.e_grid_export_total/1000,2)
    energy_total_output['Load_Energy_Total_kWh']=round(GEInv.e_load_total/1000,2)
    energy_total_output['Battery_Charge_Energy_Total_kWh']=round(GEInv.e_battery_charge_total/1000,2)
    energy_total_output['Battery_Discharge_Energy_Total_kWh']=round(GEInv.e_battery_discharge_total/1000,2)
    energy_total_output['Parallel_Total_Charge_Energy_Total_kWh']=round(GEInv.e_aio_charge_total/1000,2)
    energy_total_output['Parallel_Total_Discharge_Energy_Total_kWh']=round(GEInv.e_aio_discharge_total/1000,2)
    
    #Only implement these, if Parallel mode is in use
    if GEInv.parallel_aio_online_num>1:

        controlmode={}
        controlmode=getControls(plant,regCacheStack,inverterModel)
        logger.debug("Getting TimeSlot data")

        ######## Grab Timeslots ########
        res = {}
        res=getTimeslots(plant)
        timeslots={}
        timeslots.update(res[0])
        controlmode.update(res[1])

    ######## Get Meter Details ########

    meters={}
    meters.update(getMeters(plant))

    #if GiV_Settings.Print_Raw_Registers:
    multi_output['raw'] = getRaw(plant)

    energy["Today"] = energy_today_output
    energy["Total"] = energy_total_output
    power={}
    power['Power']=power_output
    multi_output['Inverters']=inverters
    multi_output["Power"]  = power
    multi_output["Energy"] = energy
    multi_output["Timeslots"] = timeslots
    multi_output["Control"] = controlmode
    multi_output[GEInv.serial_number]=gateway
    multi_output["Meter_Details"] = meters

    return multi_output

def processThreePhaseInfo(plant: Plant):
    GEInv=plant.inverter
    inverterModel = InvType
    multi_output={}

#    if GiV_Settings.Print_Raw_Registers:
    multi_output['raw'] = getRaw(plant)

    inverterModel=getInvModel(plant)

    # Grab previous data from Pickle and use it validate any outrageous changes
    with GivLUT.cachelock:
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack = pickle.load(inp)
                multi_output_old = regCacheStack[4]
        else:
            regCacheStack = [0, 0, 0, 0, 0]

    energy_today_output={}
    energy_today_output['Inverter_Out_Energy_Today_kWh']=GEInv.e_inverter_out_today
    energy_today_output['PV1_Energy_Today_kWh']=GEInv.e_pv1_today
    energy_today_output['PV_Energy_Today_kWh']=GEInv.e_pv2_today
    energy_today_output['AC_Charge_Energy_Today_kWh']=GEInv.e_ac_charge_today
    energy_today_output['Import_Energy_Today_kWh']=GEInv.e_import_today
    energy_today_output['Export_Energy_Today_kWh']=GEInv.e_export_today
    energy_today_output['Battery_Discharge_Energy_Today_kWh']=GEInv.e_battery_discharge_today
    energy_today_output['Battery_Charge_Energy_Today_kWh']=GEInv.e_battery_charge_today
    energy_today_output['Load_Energy_Today_kWh']=GEInv.e_load_today
    energy_today_output['Export2_Energy_Today_kWh']=GEInv.e_export2_today
    energy_today_output['PV_Energy_Today_kWh']=GEInv.e_pv_today
    energy_total_output={}
    energy_total_output['Inverter_Out_Energy_Total_kWh']=GEInv.e_inverter_out_total
    energy_total_output['PV1_Energy_Total_kWh']=GEInv.e_pv1_total
    energy_total_output['PV2_Energy_Total_kWh']=GEInv.e_pv2_total
    energy_total_output['AC_Charge_Energy_Total_kWh']=GEInv.e_ac_charge_total
    energy_total_output['Import_Energy_Total_kWh']=GEInv.e_import_total
    energy_total_output['Export_Energy_Total_kWh']=GEInv.e_export_total
    energy_total_output['Battery_Discharge_Energy_Total_kWh']=GEInv.e_battery_discharge_total
    energy_total_output['Battery_Charge_Energy_Total_kWh']=GEInv.e_battery_charge_total
    energy_total_output['Load_Energy_Total_kWh']=GEInv.e_load_total
    energy_total_output['Export2_Energy_Total_kWh']=GEInv.e_export2_total
    energy_total_output['PV_Energy_Total_kWh']=GEInv.e_pv_total

    power_output={}
    power_output['Export_Power']=GEInv.p_export
    power_output['Meter2_Power']=GEInv.p_meter2
    power_output['EPS_Phase1_Power']=GEInv.p_eps_ac1
    power_output['EPS_Phase2_Power']=GEInv.p_eps_ac2
    power_output['EPS_Phase3_Power']=GEInv.p_eps_ac3
    power_output['Battery_Charge_Power']=GEInv.p_battery_charge
    power_output['Battery_Discharge_Power']=GEInv.p_battery_discharge
    power_output['Inverter_Power_Out']=GEInv.p_inverter_out
    power_output['AC_Charge_Power']=GEInv.p_inverter_ac_charge
    power_output['Grid_Apparent_Power']=GEInv.p_grid_apparent
    power_output['Meter_Import_Power']=GEInv.p_meter_import
    power_output['Meter_Export_Power']=GEInv.p_meter_export
    power_output['Load_Phase1_Power']=GEInv.p_load_ac1
    power_output['Load_Phase2_Power']=GEInv.p_load_ac2
    power_output['Load_Phase3_Power']=GEInv.p_load_ac3
    power_output['Load_Power']=GEInv.p_load_all
    power_output['Export_Phase1_Power']=GEInv.p_out_ac1
    power_output['Export_Phase2_Power']=GEInv.p_out_ac2
    power_output['Export_Phase3_Power']=GEInv.p_out_ac3
    power_output['PV_Voltage_String_1']=GEInv.v_pv1
    power_output['PV_Voltage_String_1']=GEInv.v_pv2
    power_output['PV_Current_String_1']=GEInv.i_pv1
    power_output['PV_Current_String_1']=GEInv.i_pv2
    power_output['PV_Power_String_1']=GEInv.p_pv1
    power_output['PV_Power_String_1']=GEInv.p_pv2
    power_output['PV_Power']=GEInv.p_pv1+GEInv.p_pv2
    power_output['PV_Current']=GEInv.i_pv1+GEInv.i_pv2
    power_output['Grid_Phase1_Voltage']=GEInv.v_ac1
    power_output['Grid_Phase2_Voltage']=GEInv.v_ac2
    power_output['Grid_Phase3_Voltage']=GEInv.v_ac3
    power_output['Output_Phase1_Voltage']=GEInv.v_out_ac1
    power_output['Output_Phase2_Voltage']=GEInv.v_out_ac2
    power_output['Output_Phase3_Voltage']=GEInv.v_out_ac3
    power_output['Grid_Phase1_Current']=GEInv.i_ac1
    power_output['Grid_Phase2_Current']=GEInv.i_ac2
    power_output['Grid_Phase3_Current']=GEInv.i_ac3
    power_output['Grid_Frequency']=GEInv.f_ac1
    power_output['SOC']=GEInv.battery_soc
    power_output['SOC_kWh']=round(int(power_output['SOC'])*inverterModel.batterycapacity/100,2)
    power_output['Battery_Current']=GEInv.i_battery
    power_output['PCS_Voltage']=GEInv.v_battery_pcs
    power_output['BMS_Voltage']=GEInv.v_battery_bms
    power_output['EPS_Nominal_Frequency']=GEInv.f_nominal_eps

    ######## Get Battery Details ########

    batteries2 = {}
    batteries2=getBatteries(plant)

    inverter={}
    inverter['status']=GEInv.status.name.capitalize()
    inverter['System_Mode']=GEInv.system_mode.name.capitalize()
    inverter['Start_Delay_Time']=GEInv.start_delay_time
    inverter['Power_Factor']=GEInv.power_factor
    inverter['Battery_Type'] = GEInv.battery_type.name.capitalize()
    inverter['Invertor_Type'] = "Gen 3 - " + GEInv.model.name.capitalize()
    inverter['Battery_Priority']=GEInv.battery_priority.name.capitalize()
    inverter['Inverter_Temperature']=GEInv.t_inverter
    inverter['Boost_Temperature']=GEInv.t_boost
    inverter['Buck_Boost_Temperature']=GEInv.t_buck_boost
    inverter['DC_Status']=GEInv.dc_status.name.capitalize()
    inverter['Invertor_Serial_Number']=plant.inverter_serial_number
    inverter['Invertor_Software']=GEInv.tph_software_version
    inverter['Invertor_Firmware']=GEInv.tph_firmware_version
    inverter['Invertor_Time']=GEInv.system_time.replace(tzinfo=GivLUT.timezone).isoformat()
    firmware=GEInv.firmware_version

    controlmode={}
    # do the standard control apply to 3ph?

    controlmode.update(getControls(plant,regCacheStack,inverterModel))

    controlmode['Force_Discharge_Enable']=GEInv.force_discharge_enable.name.capitalize()
    controlmode['Force_Charge_Enable']=GEInv.force_charge_enable.name.capitalize()
    controlmode['Force_AC_Charge_Enable']=GEInv.ac_charge_enable.name.capitalize()
    controlmode['Target_SOC']=GEInv.charge_stop_soc
    controlmode['Battery_Charge_Rate_AC']=GEInv.p_charge_rate
    controlmode['Discharge_Target_SOC']=GEInv.discharge_stop_soc
    controlmode['Battery_Charge_Rate_AC']=GEInv.p_discharge_rate
    controlmode['Max_Charge_Current']=GEInv.max_charge_current
    controlmode['Load_Target_SOC']=GEInv.load_first_stop_soc
    controlmode['Export_Limit_AC']=GEInv.p_export_limit
    controlmode['Active_Power_Rate']=GEInv.active_rate
    controlmode['Reactive_Power_Rate']=GEInv.reactive_rate

    ######## Get Meter Details ########

    meters={}
    meters.update(getMeters(plant))

    timeslots={}
    logger.debug("Getting TimeSlot data")
    res = {}
    res=getTimeslots(plant)
    timeslots.update(res[0])
    controlmode.update(res[1])


    energy = {}
    energy["Today"] = energy_today_output
    energy["Total"] = energy_total_output
    power = {}
    power["Power"] = power_output
    multi_output["Battery_Details"]=batteries2
    multi_output["Power"] = power
    multi_output[GEInv.serial_number] = inverter
    multi_output["Meter_Details"] = meters
    multi_output["Energy"] = energy
    multi_output["Timeslots"] = timeslots
    multi_output["Control"] = controlmode
    return multi_output

def processData(plant: Plant):
    multi_output = {}
    result = {}
    try:
        logger.debug("Beginning parsing of Inverter data")

        #Don't use models in case its not
        modeltype=hex(plant.register_caches[plant.slave_address].get(HR(0)))[2:3]
        if modeltype == '5':
            multi_output=processEMSInfo(plant)
        elif modeltype == '7':
            multi_output=processGatewayInfo(plant)
        elif modeltype in ('4', '6'):
            multi_output=processThreePhaseInfo(plant)
        else:
            multi_output=processInverterInfo(plant)

        givtcpdata={}
        givtcpdata['Last_Updated_Time'] = datetime.datetime.now(datetime.UTC).isoformat()
        givtcpdata['status'] = "online"
        givtcpdata['Time_Since_Last_Update'] = 0
        givtcpdata['GivTCP_Version']= "2.4.393"
        multi_output['Stats']=givtcpdata
        with GivLUT.cachelock:
            if exists(GivLUT.regcache):      # if there is a cache then grab it
                with open(GivLUT.regcache, 'rb') as inp:
                    regCacheStack = pickle.load(inp)
                    multi_output_old = regCacheStack[4]
            else:
                regCacheStack = [0, 0, 0, 0, 0]

        # Dump raw inverter output to pkl for dataSmoother improvements
        
        if exists(GivLUT.rawpkl):
            with open(GivLUT.rawpkl, 'rb') as inp:
                rawCacheStack = pickle.load(inp)
            # Add new data to the stack
            rawCacheStack.pop(0)
        else:
            rawCacheStack=[0,0,0,0]
        rawCacheStack.append(multi_output['raw'])
        with open(GivLUT.rawpkl, 'wb') as outp:
            pickle.dump(rawCacheStack, outp, pickle.HIGHEST_PROTOCOL)

        ######### Section where post processing of multi_ouput functions are called ###########

        if 'multi_output_old' in locals():
            multi_output = dataCleansing(multi_output, regCacheStack[4])
            logger.debug("Data Cleansing Complete")

        # run ppkwh stats on firstrun and every half hour
        if plant.number_batteries>0:    #Don't run ratecalcs if no batteries
            if 'multi_output_old' in locals():
                multi_output = ratecalcs(multi_output, multi_output_old)
            else:
                multi_output = ratecalcs(multi_output, multi_output)
            multi_output = calcBatteryValue(multi_output)
            logger.debug("Battery rate calcs complete")


        # only update cache if its the same set of keys as previous (don't update if data missing)

        if 'multi_output_old' in locals():
            MOList = dicttoList(multi_output)
            MOOList = dicttoList(multi_output_old)
            dataDiff = set(MOOList) - set(MOList)
            if len(dataDiff) > 0:
                for key in dataDiff:
                    logger.debug(str(key)+" is missing from new data, publishing all other data")

        # Add new data to the stack
        regCacheStack.pop(0)
        regCacheStack.append(multi_output)

        # Get lastupdate from pickle if it exists
        with GivLUT.cachelock:
            if exists(GivLUT.lastupdate):
                with open(GivLUT.lastupdate, 'rb') as inp:
                    previousUpdate = pickle.load(inp)
                timediff = datetime.datetime.fromisoformat(multi_output['Stats']['Last_Updated_Time'])-datetime.datetime.fromisoformat(previousUpdate)
                multi_output['Stats']['Time_Since_Last_Update'] = (((timediff.seconds*1000000)+timediff.microseconds)/1000000)

            # Save new time to pickle
            with open(GivLUT.lastupdate, 'wb') as outp:
                pickle.dump(multi_output['Stats']['Last_Updated_Time'], outp, pickle.HIGHEST_PROTOCOL)

            # Save new data to Pickle
            with open(GivLUT.regcache, 'wb') as outp:
                pickle.dump(regCacheStack, outp, pickle.HIGHEST_PROTOCOL)
                
            logger.debug("Successfully processed data from: " + GiV_Settings.invertorIP)

            result['result'] = "Success processing data"

            # Success, so delete oldDataCount
            if exists(GivLUT.oldDataCount):
                os.remove(GivLUT.oldDataCount)

    except Exception:
        e = sys.exc_info()
        consecFails(e)
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        logger.error("inverter Update failed so using last known good data from cache: " + str(e))
        result['result'] = "processData Error processing registers: " + str(e)
        return json.dumps(result)
    return json.dumps(result, indent=4, sort_keys=True, default=str)


def consecFails(e):
    with GivLUT.cachelock:
        if exists(GivLUT.oldDataCount):
            with open(GivLUT.oldDataCount, 'rb') as inp:
                oldDataCount= pickle.load(inp)
            oldDataCount = oldDataCount + 1
            #if oldDataCount > 3:
            #    logger.error("Consecutive failure count= "+str(oldDataCount) +" -- "+ str(e))
        else:
            oldDataCount = 1
        if oldDataCount>10:
            #10 error in a row so delete regCache data
            logger.error("10 failed inverter reads in a row so removing Cache (pkl) files to force update...")
            if exists(GivLUT.regcache):
                os.remove(GivLUT.regcache)
            if exists(GivLUT.rawpkl):
                os.remove(GivLUT.rawpkl)
            if exists(GivLUT.batterypkl):
                os.remove(GivLUT.batterypkl)
            if exists(GivLUT.oldDataCount):
                os.remove(GivLUT.oldDataCount)
            if exists(GivLUT.ratedata):
                os.remove(GivLUT.ratedata)
        else:
            with open(GivLUT.oldDataCount, 'wb') as outp:
                pickle.dump(oldDataCount, outp, pickle.HIGHEST_PROTOCOL)

def runAll2(plant: Plant):  # Read from Inverter put in cache and publish
###### Step here to validate data coming in from watch_plant??
    logger.debug("Running processData")
    try:
        result=json.loads(processData(plant))
        logger.debug("processData result: "+str(result['result']))
        # Only publish if its new data?
        logger.debug("Running pubFromPickle")
        multi_output = pubFromPickle()
    except Exception:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        logger.error("runAll2 Error processing registers: " + str(e))
        return ("runAll2 Error processing registers: " + str(e))
    return multi_output

def pubFromPickle():  # Publish last cached Inverter Data
    multi_output = {}
    result = "Success"
    if not exists(GivLUT.regcache):  # if there is no cache, create it
        result = "Please get data from Inverter first, either by calling runAll or waiting until the self-run has completed"
    try:
        if "Success" in result:
            with GivLUT.cachelock:
                with open(GivLUT.regcache, 'rb') as inp:
                    regCacheStack = pickle.load(inp)
                    multi_output = regCacheStack[4]
            SN = finditem(multi_output,'Invertor_Serial_Number')
            publishOutput(multi_output, SN)
        else:
            multi_output['result'] = result
        return json.dumps(multi_output, indent=4, sort_keys=True, default=str)
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        logger.error("Error publishing data from pickle: "+str(e))
        multi_output['result']="Error publishing data from pickle"
        json.dumps(multi_output, indent=4, sort_keys=True, default=str)

def getCache():     # Get latest cache data and return it (for use in REST)
    multi_output={}
    try:
        if exists(GivLUT.regcache):
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack = pickle.load(inp)
                multi_output = regCacheStack[4]
            return json.dumps(multi_output, indent=4, sort_keys=True, default=str)
        else:
            multi_output['result']="No register data cache exists, try again later"
        return json.dumps(multi_output, indent=4, sort_keys=True, default=str)
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        logger.error("Error getting data from cache: "+str(e))
        multi_output['result']="Error getting data from cache"
        json.dumps(multi_output, indent=4, sort_keys=True, default=str)

async def self_run():
    # re-run everytime watch_plant Dies
    while True:
        try:
            logger.info("Starting watch_plant loop...")
            await watch_plant(host=GiV_Settings.invertorIP,handler=runAll2, refresh_period=GiV_Settings.self_run_timer,full_refresh_period=GiV_Settings.self_run_timer_full)
        except:
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            logger.error("Error in self_run. Re-running watch_plant: "+str(e))
            await asyncio.sleep(2)

def start():
    asyncio.run(self_run())

# Additional Publish options can be added here.
# A separate file in the folder can be added with a new publish "plugin"
# then referenced here with any settings required added into settings.py
def publishOutput(array, SN):
    tempoutput = {}
    tempoutput = iterate_dict(array)

#    threader = Threader(5)
    if GiV_Settings.MQTT_Output:
        if not exists(GivLUT.firstrun):
            logger.debug("Running updateFirstRun with SN= "+str(SN))
            updateFirstRun(SN)              # 09=July=23 - Always do this first irrespective of HA setting.
            if GiV_Settings.HA_Auto_D:
#### Should we remove old Givenergy messages here first, as updates seem to get stuck...                
                logger.info("Publishing Home Assistant Discovery messages")
                from HA_Discovery import HAMQTT
                HAMQTT.publish_discovery2(tempoutput, SN)
            open(GivLUT.firstrun, 'w').close()
        else:
            logger.debug("firstrun exists, so this should already have been run")
# Do this in a thread?
        from mqtt import GivMQTT
        logger.debug("Publish all to MQTT")
        if GiV_Settings.MQTT_Topic == "":
            GiV_Settings.MQTT_Topic = "GivEnergy"
        GivMQTT.multi_MQTT_publish(str(GiV_Settings.MQTT_Topic+"/"+SN+"/"), tempoutput)
    if GiV_Settings.Influx_Output:
        from influx import GivInflux
        logger.debug("Pushing output to Influx")
        GivInflux.publish(SN, tempoutput)

def updateFirstRun(SN):
    isSN = False
    script_dir = os.path.dirname(__file__)  # <-- absolute dir the script is in
    rel_path = "settings.py"
    abs_file_path = os.path.join(script_dir, rel_path)
    #check for settings lockfile before
    count=0
    while True:
        logger.debug("Opening settings for first run")
        if exists('.settings_lockfile'):
            logger.debug("Waiting for settings to be available")
            time.sleep(1)
            count=count+1
            if count==50:
                logger.error("Could not access settings file to update EVC Serial Number")
                break
        else:
            logger.debug("Settings available")
            #Create setting lockfile
            open(".settings_lockfile",'a').close()

            with open(abs_file_path, "r") as f:
                lines = f.readlines()
            with open(abs_file_path, "w") as f:
                for line in lines:
                    if line.strip("\n") == "    first_run= True":
                        f.write("    first_run= False\n")
                    else:
                        f.write(line)
                    if "serial_number=" in line:
                        logger.debug("serial number aready exists: \""+line+"\"")
                        isSN = True

                if not isSN:
                    logger.debug("serial number not in file, adding now")
                    f.writelines("    serial_number= \""+SN+"\"\n")  # only add SN if its not there
            # Delete settings_lockfile
            os.remove('.settings_lockfile')
            logger.debug("removing lockfile")
            break


def iterate_dict(array):        # Create a publish safe version of the output (convert non string or int datapoints)
    safeoutput = {}
    #dump
    for p_load in array:
        output = array[p_load]
        if isinstance(output, dict):
            temp = iterate_dict(output)
            safeoutput[p_load] = temp
            logger.debug('Dealt with '+p_load)
        elif isinstance(output, tuple):
            if "slot" in str(p_load):
                logger.debug('Converting Timeslots to publish safe string')
                safeoutput[p_load+"_start"] = output[0].strftime("%H:%M")
                safeoutput[p_load+"_end"] = output[1].strftime("%H:%M")
            else:
                # Deal with other tuples _ Print each value
                for index, key in enumerate(output):
                    logger.debug('Converting Tuple to multiple publish safe strings')
                    safeoutput[p_load+"_"+str(index)] = str(key)
        elif isinstance(output, datetime.datetime):
            logger.debug('Converting datetime to publish safe string')
            safeoutput[p_load] = output.strftime("%d-%m-%Y %H:%M:%S")
        elif isinstance(output, datetime.time):
            logger.debug('Converting time to publish safe string')
            safeoutput[p_load] = output.strftime("%H:%M")
        elif isinstance(output, Model):
            logger.debug('Converting Model to publish safe string')
            safeoutput[p_load] = output.name.capitalize()
        elif isinstance(output, float):
            safeoutput[p_load] = round(output, 3)
        else:
            safeoutput[p_load] = output
    return(safeoutput)


def ratecalcs(multi_output, multi_output_old):
    rate_data = {}
    logger.debug("Starting ratecalcs...")
    dayRateStart = datetime.datetime.strptime(GiV_Settings.day_rate_start, '%H:%M')
    nightRateStart = datetime.datetime.strptime(GiV_Settings.night_rate_start, '%H:%M')
    night_start = datetime.datetime.combine(datetime.datetime.now(GivLUT.timezone).date(),nightRateStart.time()).replace(tzinfo=GivLUT.timezone)
    logger.debug("Night Start= "+datetime.datetime.strftime(night_start, '%c'))
    day_start = datetime.datetime.combine(datetime.datetime.now(GivLUT.timezone).date(),dayRateStart.time()).replace(tzinfo=GivLUT.timezone)
    logger.debug("Day Start= "+datetime.datetime.strftime(day_start, '%c'))
    import_energy = multi_output['Energy']['Total']['Import_Energy_Total_kWh']
    import_energy_old = multi_output_old['Energy']['Total']['Import_Energy_Total_kWh']

    # check if pickle data exists:
    if exists(GivLUT.ratedata):
        with open(GivLUT.ratedata, 'rb') as inp:
            rate_data = pickle.load(inp)
    else:
        logger.debug("No rate_data exists, so creating new baseline")

    #       If no data then just save current import as base data
    if not('Night_Start_Energy_kWh' in rate_data):
        logger.debug("No Night Start Energy so setting it to: "+str(import_energy))
        rate_data['Night_Start_Energy_kWh'] = import_energy
    if not('Day_Start_Energy_kWh' in rate_data):
        logger.debug("No Day Start Energy so setting it to: "+str(import_energy))
        rate_data['Day_Start_Energy_kWh'] = import_energy
    if not('Night_Energy_kWh' in rate_data):
        rate_data['Night_Energy_kWh'] = 0.00
    if not('Day_Energy_kWh' in rate_data):
        rate_data['Day_Energy_kWh'] = 0.00
    if not('Night_Cost' in rate_data):
        rate_data['Night_Cost'] = 0.00
    if not('Day_Cost' in rate_data):
        rate_data['Day_Cost'] = 0.00
    if not('Night_Energy_Total_kWh' in rate_data):
        rate_data['Night_Energy_Total_kWh'] = 0
    if not('Day_Energy_Total_kWh' in rate_data):
        rate_data['Day_Energy_Total_kWh'] = 0

# Always update rates from new setting
    rate_data['Export_Rate'] = GiV_Settings.export_rate
    rate_data['Day_Rate'] = GiV_Settings.day_rate
    rate_data['Night_Rate'] = GiV_Settings.night_rate

    # if midnight then reset costs
    if datetime.datetime.now(GivLUT.timezone).hour == 0 and datetime.datetime.now(GivLUT.timezone).minute == 0:
        logger.info("Midnight, so resetting Day/Night stats...")
        rate_data['Night_Cost'] = 0.00
        rate_data['Day_Cost'] = 0.00
        rate_data['Night_Energy_kWh'] = 0.00
        rate_data['Day_Energy_kWh'] = 0.00
        rate_data['Day_Start_Energy_kWh'] = import_energy
        rate_data['Night_Start_Energy_kWh'] = import_energy
        rate_data['Day_Energy_Total_kWh'] = 0
        rate_data['Night_Energy_Total_kWh'] = 0

    if GiV_Settings.dynamic_tariff == False:     ## If we use externally triggered rates then don't do the time check but assume the rate files are set elsewhere (default to Day if not set)
        if dayRateStart.hour == datetime.datetime.now(GivLUT.timezone).hour and dayRateStart.minute == datetime.datetime.now(GivLUT.timezone).minute:
            open(GivLUT.dayRateRequest, 'w').close()
        elif nightRateStart.hour == datetime.datetime.now(GivLUT.timezone).hour and nightRateStart.minute == datetime.datetime.now(GivLUT.timezone).minute:
            open(GivLUT.nightRateRequest, 'w').close()
        # Otherwise check to see if dynamic trigger has been received to change rate type

    if exists(GivLUT.nightRateRequest):
        os.remove(GivLUT.nightRateRequest)
        if not exists(GivLUT.nightRate):
            #Save last total from todays dayrate so far
            rate_data['Day_Energy_Total_kWh']=rate_data['Day_Energy_kWh']       # save current day energy at the end of the slot
            logger.info("Saving current energy stats at start of night rate tariff (Dynamic)")
            rate_data['Night_Start_Energy_kWh'] = import_energy-rate_data['Night_Energy_Total_kWh']     #offset current night energy from current energy to combine into a single slot
            open(GivLUT.nightRate, 'w').close()
            if exists(GivLUT.dayRate):
                logger.debug(".dayRate exists so deleting it")
                os.remove(GivLUT.dayRate)
    elif exists(GivLUT.dayRateRequest):
        os.remove(GivLUT.dayRateRequest)
        if not exists(GivLUT.dayRate):
            rate_data['Night_Energy_Total_kWh']=rate_data['Night_Energy_kWh']   # save current night energy at the end of the slot
            logger.info("Saving current energy stats at start of day rate tariff (Dynamic)")
            rate_data['Day_Start_Energy_kWh'] = import_energy-rate_data['Day_Energy_Total_kWh']     # offset current day energy from current energy to combine into a single slot
            open(GivLUT.dayRate, 'w').close()
            if exists(GivLUT.nightRate):
                logger.debug(".nightRate exists so deleting it")
                os.remove(GivLUT.nightRate)

    if not exists(GivLUT.nightRate) and not exists(GivLUT.dayRate): #Default to Day if not previously set
        logger.info("No day/Night rate info so reverting to day")
        open(GivLUT.dayRate, 'w').close()

    if exists(GivLUT.dayRate):
        rate_data['Current_Rate_Type'] = "Day"
        rate_data['Current_Rate'] = GiV_Settings.day_rate
        logger.debug("Setting Rate to Day")
    else:
        rate_data['Current_Rate_Type'] = "Night"
        rate_data['Current_Rate'] = GiV_Settings.night_rate
        logger.debug("Setting Rate to Night")


    # now calc the difference for each value between the correct start pickle and now
    if import_energy>import_energy_old: # Only run if there has been more import
        logger.debug("Imported more energy so calculating current tariff costs: "+str(import_energy_old)+" -> "+str(import_energy))

#        if night_start <= datetime.datetime.now(GivLUT.timezone) < day_start:
        if exists(GivLUT.nightRate):
            logger.debug("Current Tariff is Night, calculating stats...")
            # Add change in energy this slot to previous rate_data
            rate_data['Night_Energy_kWh'] = import_energy-rate_data['Night_Start_Energy_kWh']
            logger.debug("Night_Energy_kWh=" +str(import_energy)+" - "+str(rate_data['Night_Start_Energy_kWh']))
            rate_data['Night_Cost'] = float(rate_data['Night_Energy_kWh'])*float(GiV_Settings.night_rate)
            logger.debug("Night_Cost= "+str(rate_data['Night_Energy_kWh'])+"kWh x £"+str(float(GiV_Settings.night_rate))+"/kWh = £"+str(rate_data['Night_Cost']))
            rate_data['Current_Rate'] = GiV_Settings.night_rate
        else:
            logger.debug("Current Tariff is Day, calculating stats...")
            rate_data['Day_Energy_kWh'] = import_energy-rate_data['Day_Start_Energy_kWh']
            logger.debug("Day_Energy_kWh=" + str(import_energy)+" - "+str(rate_data['Day_Start_Energy_kWh']))
            rate_data['Day_Cost'] = float(rate_data['Day_Energy_kWh'])*float(GiV_Settings.day_rate)
            logger.debug("Day_Cost= "+str(rate_data['Day_Energy_kWh'])+"kWh x £"+str(float(GiV_Settings.day_rate))+"/kWh = £"+str(rate_data['Day_Cost']))
            rate_data['Current_Rate'] = GiV_Settings.day_rate

        if (multi_output['Energy']['Today']['Load_Energy_Today_kWh']) != 0:
            rate_data['Import_ppkwh_Today'] = round((rate_data['Day_Cost']+rate_data['Night_Cost'])/(multi_output['Energy']['Today']['Import_Energy_Today_kWh']), 3)
            logger.debug("Import_ppkwh_Today= (£"+str(rate_data['Day_Cost'])+" + £"+str(rate_data['Night_Cost'])+") \ "+str(multi_output['Energy']['Today']['Load_Energy_Today_kWh'])+"kWh = £"+str(rate_data['Import_ppkwh_Today'])+"/kWh")

    multi_output['Energy']['Rates'] = rate_data

    # dump current data to Pickle
    with open(GivLUT.ratedata, 'wb') as outp:
        pickle.dump(rate_data, outp, pickle.HIGHEST_PROTOCOL)

    return (multi_output)


def dataCleansing(data, regCacheStack):
    logger.debug("Running the data cleansing process")
    # iterate multi_output to get each end result dict.
    # Loop that dict to validate against
    new_multi_output = loop_dict(data, regCacheStack, data['Stats']["Last_Updated_Time"])
    return(new_multi_output)


def dicttoList(array):
    safeoutput = []
    # finaloutput={}
    # arrayout={}
    for p_load in array:
        output = array[p_load]
        safeoutput.append(p_load)
        if isinstance(output, dict):
            safeoutput = safeoutput+dicttoList(output)
    return(safeoutput)


def loop_dict(array, regCacheStack, lastUpdate):
    safeoutput = {}
    # finaloutput={}
    # arrayout={}
    for p_load in array:
        output = array[p_load]
        if p_load == "raw":  # skip data cleansing for raw data
            safeoutput[p_load] = output
            continue
        if isinstance(output, dict):
            if p_load in regCacheStack:
                temp = loop_dict(output, regCacheStack[p_load], lastUpdate)
                safeoutput[p_load] = temp
                logger.debug('Data cleansed for: '+str(p_load))
            else:
                logger.debug(str(p_load)+" has no data in the cache so using new value.")
                safeoutput[p_load] = output
        else:
            # run datasmoother on the data item
            # only run if old data exists otherwise return the existing value
            if p_load in regCacheStack:
                safeoutput[p_load] = dataSmoother2([p_load, output], [p_load, regCacheStack[p_load]], lastUpdate)
            else:
                logger.debug(p_load+" has no data in the cache so using new value.")
                safeoutput[p_load] = output
    return(safeoutput)

def dataSmoother2(dataNew, dataOld, lastUpdate):
    # perform test to validate data and smooth out spikes
    newData = dataNew[1]
    oldData = dataOld[1]
    name = dataNew[0]
    lookup = givLUT[name]
    phases=3

    if GiV_Settings.data_smoother.lower() == "high":
        smoothRate = 0.25
        abssmooth=3000
    elif GiV_Settings.data_smoother.lower() == "medium":
        smoothRate = 0.35
        abssmooth=1000
    elif GiV_Settings.data_smoother.lower() == "none":
        return(newData)
    else:
        smoothRate = 0.50
        abssmooth=5000
    if isinstance(newData, int) or isinstance(newData, float):
        with open(GivLUT.regcache, 'rb') as inp:
            regCacheStack = pickle.load(inp)
        if not '3PH' in finditem(regCacheStack[4],"Invertor_Type"):
            if isinstance(lookup.min,str):
                min=maxvalues.single_phase[lookup.min]
            else:
                min=lookup.min
            if isinstance(lookup.max,str):
                max=maxvalues.single_phase[lookup.max]
            else:
                max=lookup.max
        else:
            if isinstance(lookup.min,str):
                min=maxvalues.three_phase[lookup.min]
            else:
                min=lookup.min
            if isinstance(lookup.max,str):
                max=maxvalues.three_phase[lookup.max]
            else:
                max=lookup.max
        if oldData != 0:
            then = datetime.datetime.fromisoformat(lastUpdate)
            now = datetime.datetime.now(GivLUT.timezone)
    ### Run checks against the conditions in GivLUT ###
            if now.minute == 0 and now.hour == 0 and "Today" in name:  # Treat Today stats as a special case
                logger.debug("Midnight and "+str(name)+" so accepting value as is")
                return (dataNew)
            if newData == 0 and not lookup.allowZero:  # if zero and not allowed to be
                logger.debug(str(name)+" is Zero so using old value")
                return(oldData)
            if newData < float(min) or newData > float(max):  # If outside min and max ranges
                logger.debug(str(name)+" is outside of allowable bounds so using old value. Out of bounds value is: "+str(newData) + ". Min limit: " + str(min) + ". Max limit: " + str(max))
                return(oldData)
            if lookup.onlyIncrease:  # if data can only increase then check
                if (oldData-newData) > 0.11:
                    logger.debug(str(name)+" has decreased so using old value")
                    return oldData
            if lookup.smooth:     # apply smoothing if required
                if newData != oldData:  # Only if its not the same
                    timeDelta = (now-then).total_seconds()
                    dataDelta = abs(newData-oldData)/oldData    #Should it be a ratio or an abs value as low values easily meet the threshold
                    if "Power" in name:
                        if abs(newData-oldData)>0:
                            if checkRawcache(newData,name,abssmooth): #If new data is persistently outside bounds
                                logger.debug(str(name)+" jumped too far in a single read: "+str(oldData)+"->"+str(newData)+" so using previous value")
                                return(oldData)
                            else:
                                return(newData)
                    else:
                        if dataDelta > smoothRate and timeDelta < 60:
                            logger.debug(str(name)+" jumped too far in a single read: "+str(oldData)+"->"+str(newData)+" so using previous value")
                            return(oldData)

    return(newData)

def checkRawcache(newData,name,abssmooth):
    #Get rawdata cache to check if unallowed changes are persistent and should be allowed
    if exists(GivLUT.rawpkl):
        with open(GivLUT.rawpkl, 'rb') as inp:
            rawCacheStack = pickle.load(inp)
        result=True
        for cache in rawCacheStack:
            try:
                oldData=cache['inverter'][name]
            except:
                continue
            if abs(newData-oldData)>abssmooth:
                result=False
    return result

def calcBatteryValue(multi_output):
    # get current data from read pickle
    batterystats = {}
    if exists(GivLUT.batterypkl):
        with open(GivLUT.batterypkl, 'rb') as inp:
            batterystats = pickle.load(inp)
    else:       # if no old AC charge, then set it to now and zero out value and ppkwh
        logger.debug("First time running so saving AC Charge status")
        batterystats['AC Charge last'] = float(multi_output['Energy']['Total']['AC_Charge_Energy_Total_kWh'])
        batterystats['Battery_Value'] = 0
        batterystats['Battery_ppkwh'] = 0
        batterystats['Battery_kWh_old'] = multi_output['Power']['Power']['SOC_kWh']

    if not exists(GivLUT.firstrun) or datetime.datetime.now(GivLUT.timezone).minute == 59 or datetime.datetime.now(GivLUT.timezone).minute == 29:
        if not exists(GivLUT.ppkwhtouch) and exists(GivLUT.batterypkl):      # only run this if there is no touchfile but there is a battery stat
            battery_kwh = multi_output['Power']['Power']['SOC_kWh']
            ac_charge = float(multi_output['Energy']['Total']['AC_Charge_Energy_Total_kWh'])-float(batterystats['AC Charge last'])
            logger.debug("Battery_kWh has gone from: "+str(batterystats['Battery_kWh_old'])+" -> "+str(battery_kwh))
            if float(battery_kwh) > float(batterystats['Battery_kWh_old']):
                logger.debug("Battery has been charged in the last 30mins so recalculating battery value and ppkwh: ")
                batVal = batterystats['Battery_Value']
                money_in = round(ac_charge*float(multi_output['Energy']['Rates']['Current_Rate']), 2)
                logger.debug("Money_in= "+str(round(ac_charge, 2))+"kWh * £"+str(float(multi_output['Energy']['Rates']['Current_Rate']))+"/kWh = £"+str(money_in))
                batterystats['Battery_Value'] = round(float(batterystats['Battery_Value']) + money_in, 3)
                logger.debug("Battery_Value= £"+str(float(batVal))+" + £"+str(money_in)+" = £"+str(batterystats['Battery_Value']))
                batterystats['Battery_ppkwh'] = round(batterystats['Battery_Value']/battery_kwh, 3)
                logger.debug("Battery_ppkWh= £"+str(batterystats['Battery_Value'])+" / "+str(battery_kwh)+"kWh = £"+str(batterystats['Battery_ppkwh'])+"/kWh")
            else:
                logger.debug("No battery charge in the last 30 mins so adjusting Battery Value")
                batterystats['Battery_Value'] = round(float(batterystats['Battery_ppkwh'])*battery_kwh, 3)
                logger.debug("Battery_Value= £"+str(round(float(batterystats['Battery_ppkwh']), 2))+"/kWh * "+str(round(battery_kwh, 2))+"kWh = £"+str(batterystats['Battery_Value']))
            # set the new "old" AC Charge stat to current AC Charge kwh
            batterystats['AC Charge last'] = float(multi_output['Energy']['Total']['AC_Charge_Energy_Total_kWh'])
            logger.debug("Updating battery_kWh_old to: "+str(battery_kwh))
            batterystats['Battery_kWh_old'] = battery_kwh
            open(GivLUT.ppkwhtouch, 'w').close()       # set touch file  to stop repeated triggers in the single minute

    else:       # remove the touchfile if it exists
        if exists(GivLUT.ppkwhtouch):
            os.remove(GivLUT.ppkwhtouch)

    # write data to pickle
    with open(GivLUT.batterypkl, 'wb') as outp:
        pickle.dump(batterystats, outp, pickle.HIGHEST_PROTOCOL)

    # remove non publishable stats
    del batterystats['AC Charge last']
    # add stats to multi_output
    multi_output['Energy']['Rates']['Battery_Value'] = batterystats['Battery_Value']
    multi_output['Energy']['Rates']['Battery_ppkwh'] = batterystats['Battery_ppkwh']
    return (multi_output)

def getJobFinish(type: str):
    with open(type, 'r') as f:
        lines=f.readlines()
    endtime=lines[1]
    logger.debug("Finish hour= "+str(endtime[:2]))
    logger.debug("Finish minute= "+str(endtime[-2:]))
    finishdate= datetime.datetime.now().replace(hour=int(endtime[:2]),minute=int(endtime[-2:]))
    logger.debug("Finishtime is: "+str(finishdate))
    timeleft=int((finishdate - datetime.datetime.now()).total_seconds()/60)
    logger.debug("Time remaining is" + str(timeleft))
    return (timeleft)

def finditem(obj, key):
    if key in obj: return obj[key]
    for k, v in obj.items():
        if isinstance(v,dict):
            item = finditem(v, key)
            if item is not None:
                return item
    return None

if __name__ == '__main__':
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])

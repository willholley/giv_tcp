# -*- coding: utf-8 -*-
# version 2022.08.01
# pylint: disable=line-too-long
"""Main Read module"""
import sys
from threading import Lock
import json
import logging
import datetime
import pickle
import time
from datetime import timedelta
from os.path import exists
import os
from rq import Retry
from givenergy_modbus.model.inverter import Model
from .giv_lut import GivLUT, GivQueue, GivClient, InvType
from .settings import GivSettings

logging.getLogger("givenergy_modbus").setLevel(logging.CRITICAL)
logging.getLogger("rq.worker").setLevel(logging.CRITICAL)

sys.path.append(GivSettings.default_path)


givLUT = GivLUT.entity_type
logger = GivLUT.logger

cacheLock = Lock()

def inverter_data(fullrefresh):
    """Actual inverter read function call"""
    try:
        plant = GivClient.get_data(fullrefresh)
        inverter = plant.inverter
        batteries = plant.batteries
    except Exception:
        return ("ERROR:-"+str(sys.exc_info()))
    return inverter,batteries

def get_data(fullrefresh):  # Read from Inverter put in cache
    """Request data from inverter and process"""
    energy_total_output = {}
    energy_today_output = {}
    power_output = {}
    controlmode = {}
    power_flow_output = {}
    inverter = {}
    multi_output = {}
    result = {}
    temp = {}

    logger.debug("----------------------------Starting----------------------------")
    logger.debug("Getting All Registers")

    # Connect to inverter and load data
    try:
        logger.debug("Connecting to: %s", GivSettings.invertorIP)
        plant=GivQueue.q.enqueue(inverter_data,fullrefresh,retry=Retry(max=GivSettings.queue_retries, interval=2))
        while plant.result is None and plant.exc_info is None:
            time.sleep(0.1)
        if "ERROR" in plant.result:
            raise Exception ("Garbage or failed inverter Response: %s", str(plant.result))
        ge_inverter=plant.result[0]
        ge_batteries=plant.result[1]

#        plant=inverter_data(True)
#        ge_inverter=plant[0]
#        ge_batteries=plant[1]

        multi_output['Last_Updated_Time'] = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()
        multi_output['status'] = "online"
        multi_output['Time_Since_Last_Update'] = 0
    except Exception:
        error = sys.exc_info()
        consec_fails(error)
        temp['result'] = "Error collecting registers: " + str(error)
        return json.dumps(temp)

    logger.debug("inverter connection successful, registers retrieved")

    try:
        logger.debug("Beginning parsing of Inverter data")
        inverter_model= InvType
        # Determine inverter Model and max charge rate first...

        #genint=math.floor(int(ge_inverter.arm_firmware_version)/100)

        inverter_model.model=ge_inverter.inverter_model
        inverter_model.generation=ge_inverter.inverter_generation
        inverter_model.phase=ge_inverter.inverter_phases
        inverter_model.invmaxrate=ge_inverter.inverter_maxpower

        if ge_inverter.device_type_code=="8001":  # if AIO
            battery_capacity=ge_inverter.battery_nominal_capacity*307
        else:
            battery_capacity=ge_inverter.battery_nominal_capacity*51.2

        if inverter_model.generation == 'Gen 1':
            if inverter_model.model == "AC":
                max_bat_charge_rate=3000
            elif inverter_model.model == "All in One":
                max_bat_charge_rate=6000
            else:
                max_bat_charge_rate=2600
        else:
            if inverter_model.model == "AC":
                max_bat_charge_rate=5000
            else:
                max_bat_charge_rate=3600

        # Calc max charge rate
        inverter_model.batmaxrate=min(max_bat_charge_rate, battery_capacity/2)

############  Energy Stats    ############

        # Total Energy Figures
        logger.debug("Getting Total Energy Data")
        energy_total_output['Export_Energy_Total_kWh'] = ge_inverter.e_grid_out_total
        energy_total_output['Import_Energy_Total_kWh'] = ge_inverter.e_grid_in_total
        energy_total_output['Invertor_Energy_Total_kWh'] = ge_inverter.e_inverter_out_total
        energy_total_output['PV_Energy_Total_kWh'] = ge_inverter.e_pv_total
        energy_total_output['AC_Charge_Energy_Total_kWh'] = ge_inverter.e_inverter_in_total

        if inverter_model.model == "Hybrid":
            energy_total_output['Load_Energy_Total_kWh'] = round((energy_total_output['Invertor_Energy_Total_kWh']-energy_total_output['AC_Charge_Energy_Total_kWh']) -
                                                                 (energy_total_output['Export_Energy_Total_kWh']-energy_total_output['Import_Energy_Total_kWh']), 2)
        else:
            energy_total_output['Load_Energy_Total_kWh'] = round((energy_total_output['Invertor_Energy_Total_kWh']-energy_total_output['AC_Charge_Energy_Total_kWh']) -
                                                                 (energy_total_output['Export_Energy_Total_kWh']-energy_total_output['Import_Energy_Total_kWh'])+energy_total_output['PV_Energy_Total_kWh'], 2)

        energy_total_output['Self_Consumption_Energy_Total_kWh'] = round(energy_total_output['PV_Energy_Total_kWh'], 2)-round(energy_total_output['Export_Energy_Total_kWh'], 2)


        # Energy Today Figures
        logger.debug("Getting Today Energy Data")
        energy_today_output['PV_Energy_Today_kWh'] = ge_inverter.e_pv1_day+ge_inverter.e_pv2_day
        energy_today_output['Import_Energy_Today_kWh'] = ge_inverter.e_grid_in_day
        energy_today_output['Export_Energy_Today_kWh'] = ge_inverter.e_grid_out_day
        energy_today_output['AC_Charge_Energy_Today_kWh'] = ge_inverter.e_inverter_in_day
        energy_today_output['Invertor_Energy_Today_kWh'] = ge_inverter.e_inverter_out_day
        energy_today_output['Self_Consumption_Energy_Today_kWh'] = round(energy_today_output['PV_Energy_Today_kWh'], 2)-round(energy_today_output['Export_Energy_Today_kWh'], 2)

        if inverter_model.model == "Hybrid":
            energy_today_output['Load_Energy_Today_kWh'] = round((energy_today_output['Invertor_Energy_Today_kWh']-energy_today_output['AC_Charge_Energy_Today_kWh']) -
                                                                 (energy_today_output['Export_Energy_Today_kWh']-energy_today_output['Import_Energy_Today_kWh']), 2)
        else:
            energy_today_output['Load_Energy_Today_kWh'] = round((energy_today_output['Invertor_Energy_Today_kWh']-energy_today_output['AC_Charge_Energy_Today_kWh']) -
                                                                 (energy_today_output['Export_Energy_Today_kWh']-energy_today_output['Import_Energy_Today_kWh'])+energy_today_output['PV_Energy_Today_kWh'], 2)

        checksum = 0
        for item in energy_today_output.items():
            checksum = checksum+energy_today_output[item]
        if checksum == 0 and ge_inverter.system_time.hour == 0 and ge_inverter.system_time.minute == 0:
            with cacheLock:
                if exists(GivLUT.regcache):
                    # remove regcache at midnight
                    logger.debug("Energy Today is Zero and its midnight so resetting regCache")
                    os.remove(GivLUT.regcache)


############  Core Power Stats    ############

        # PV Power
        logger.debug("Getting PV Power")
        pv_power_1 = ge_inverter.p_pv1
        pv_power_2 = ge_inverter.p_pv2
        pv_power = pv_power_1+pv_power_2
        if pv_power < 15000:
            power_output['PV_Power_String_1'] = pv_power_1
            power_output['PV_Power_String_2'] = pv_power_2
            power_output['PV_Power'] = pv_power
        power_output['PV_Voltage_String_1'] = ge_inverter.v_pv1
        power_output['PV_Voltage_String_2'] = ge_inverter.v_pv2
        power_output['PV_Current_String_1'] = ge_inverter.i_pv1*10
        power_output['PV_Current_String_2'] = ge_inverter.i_pv2*10
        power_output['Grid_Voltage'] = ge_inverter.v_ac1
        power_output['Grid_Current'] = ge_inverter.i_ac1*10

        # Grid Power
        logger.debug("Getting Grid Power")
        grid_power = ge_inverter.p_grid_out
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
        power_output['EPS_Power'] = ge_inverter.p_eps_backup

        # Inverter Power
        logger.debug("Getting PInv Power")
        inverter_power = ge_inverter.p_inverter_out
        if -inverter_model.invmaxrate <= inverter_power <=inverter_model.invmaxrate:
            power_output['Invertor_Power'] = inverter_power
        if inverter_power < 0:
            power_output['AC_Charge_Power'] = abs(inverter_power)
        else:
            power_output['AC_Charge_Power'] = 0

        # Load Power
        logger.debug("Getting Load Power")
        load_power = ge_inverter.p_load_demand
        if load_power < 15500:
            power_output['Load_Power'] = load_power

        # Self Consumption
        logger.debug("Getting Self Consumption Power")
        power_output['Self_Consumption_Power'] = max(load_power - import_power, 0)


############  Power Flow Stats    ############

        # Solar to H/B/G
        logger.debug("Getting Solar to H/B/G Power Flows")
        if pv_power > 0:
            solar_to_house = min(pv_power, load_power)
            power_flow_output['Solar_to_House'] = solar_to_house
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
        with cacheLock:
            if exists(GivLUT.regcache):      # if there is a cache then grab it
                with open(GivLUT.regcache, 'rb') as inp:
                    reg_cache_stack = pickle.load(inp)
                    multi_output_old = reg_cache_stack[4]
            else:
                reg_cache_stack = [0, 0, 0, 0, 0]

        ######## Battery Stats only if there are batteries...  ########
        logger.debug("Getting SOC")
#        if int(GivSettings.numBatteries) > 0:  # only do this if there are batteries
        if ge_inverter.battery_percent != 0:
            power_output['SOC'] = ge_inverter.battery_percent
        elif ge_inverter.battery_percent == 0 and 'multi_output_old' in locals():
            power_output['SOC'] = multi_output_old['Power']['Power']['SOC']
            logger.error("\"Battery SOC\" reported as: %s so using previous value",str(ge_inverter.battery_percent))
        elif ge_inverter.battery_percent == 0 and not 'multi_output_old' in locals():
            power_output['SOC'] = 1
            logger.error("\"Battery SOC\" reported as: %s and no previous value so setting to 1%",str(ge_inverter.battery_percent))
        power_output['SOC_kWh'] = (int(power_output['SOC'])*((battery_capacity)/1000))/100

        # Energy Stats
        logger.debug("Getting Battery Energy Data")
        energy_today_output['Battery_Charge_Energy_Today_kWh'] = ge_inverter.e_battery_charge_day
        energy_today_output['Battery_Discharge_Energy_Today_kWh'] = ge_inverter.e_battery_discharge_day
        energy_today_output['Battery_Throughput_Today_kWh'] = ge_inverter.e_battery_charge_day+ge_inverter.e_battery_discharge_day
        energy_total_output['Battery_Throughput_Total_kWh'] = ge_inverter.e_battery_throughput_total
        if ge_inverter.e_battery_charge_total == 0 and ge_inverter.e_battery_discharge_total == 0 and not GivSettings.numBatteries==0:
            energy_total_output['Battery_Charge_Energy_Total_kWh'] = ge_batteries[0].e_battery_charge_total_2
            energy_total_output['Battery_Discharge_Energy_Total_kWh'] = ge_batteries[0].e_battery_discharge_total_2
        else:
            energy_total_output['Battery_Charge_Energy_Total_kWh'] = ge_inverter.e_battery_charge_total
            energy_total_output['Battery_Discharge_Energy_Total_kWh'] = ge_inverter.e_battery_discharge_total


######## Get Control Data ########

        logger.debug("Getting mode control figures")
        # Get Control Mode registers
        if ge_inverter.enable_charge is True:
            charge_schedule = "enable"
        else:
            charge_schedule = "disable"
        if ge_inverter.enable_discharge is True:
            discharge_schedule = "enable"
        else:
            discharge_schedule = "disable"
        if ge_inverter.battery_power_mode == 1:
            battery_power_mode="enable"
        else:
            battery_power_mode="disable"
        #Get Battery Stat registers
        #battery_reserve = ge_inverter.battery_discharge_min_power_reserve

        battery_reserve = ge_inverter.battery_soc_reserve

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
                except Exception:
                    error = sys.exc_info()
                    temp['result'] = "Saving the battery reserve for later failed: " + str(error)
                    logger.error (temp['result'])
            else:
                # Value is 100, we don't want to save 100 because we need to restore to a value FROM 100...
                logger.debug ("Saving the battery reserve percentage for later: no need, it's currently at 100 and we don't want to save that.")

        battery_cutoff = ge_inverter.battery_discharge_min_power_reserve
        target_soc = ge_inverter.charge_target_soc
        if ge_inverter.battery_soc_reserve <= ge_inverter.battery_percent:
            discharge_enable = "enable"
        else:
            discharge_enable = "disable"

        # Get Charge/Discharge Active status
        discharge_rate = int(min((ge_inverter.battery_discharge_limit/100)*(battery_capacity), inverter_model.batmaxrate))
        charge_rate = int(min((ge_inverter.battery_charge_limit/100)*(battery_capacity), inverter_model.batmaxrate))

        # Calculate Mode
        logger.debug("Calculating Mode...")
        # Calc Mode

        if ge_inverter.battery_power_mode == 1 and ge_inverter.enable_discharge is False and ge_inverter.battery_soc_reserve != 100:
            # Dynamic r27=1 r110=4 r59=0
            mode = "Eco"
        elif ge_inverter.battery_power_mode == 1 and ge_inverter.enable_discharge is False and ge_inverter.battery_soc_reserve == 100:
            # Dynamic r27=1 r110=4 r59=0
            mode = "Eco (Paused)"
        elif ge_inverter.battery_power_mode == 1 and ge_inverter.enable_discharge is True:
            # Storage (demand) r27=1 r110=100 r59=1
            mode = "Timed Demand"
        elif ge_inverter.battery_power_mode == 0 and ge_inverter.enable_discharge is True:
            # Storage (export) r27=0 r59=1
            mode = "Timed Export"
        elif ge_inverter.battery_power_mode == 0 and ge_inverter.enable_discharge is False:
            # Dynamic r27=1 r110=4 r59=0
            mode = "Eco (Paused)"
        else:
            mode = "Unknown"

        logger.debug("Mode is: " + str(mode))

        controlmode['Mode'] = mode
        controlmode['Battery_Power_Reserve'] = battery_reserve
        controlmode['Battery_Power_Cutoff'] = battery_cutoff
        controlmode['Battery_Power_Mode'] = battery_power_mode
        controlmode['Target_SOC'] = target_soc

        try:
            controlmode['Local_control_mode'] = GivLUT.local_control_mode[int(ge_inverter.local_control_mode)]
            controlmode['PV_input_mode'] = GivLUT.pv_input_mode[int(ge_inverter.pv_input_mode)]
            controlmode['Battery_pause_mode'] = GivLUT.battery_pause_mode[int(ge_inverter.battery_pause_mode)]
        except Exception:
            logger.debug("New control modes don't exist for this model")

        controlmode['Enable_Charge_Schedule'] = charge_schedule
        controlmode['Enable_Discharge_Schedule'] = discharge_schedule
        controlmode['Enable_Discharge'] = discharge_enable
        controlmode['Battery_Charge_Rate'] = charge_rate
        controlmode['Battery_Discharge_Rate'] = discharge_rate
        controlmode['Active_Power_Rate']= ge_inverter.active_power_rate
        controlmode['Reboot_Invertor']="disable"
        controlmode['Reboot_Addon']="disable"
        if not isinstance(reg_cache_stack[4], int):
            if "Temp_Pause_Discharge" in reg_cache_stack[4]:
                controlmode['Temp_Pause_Discharge'] = reg_cache_stack[4]["Control"]["Temp_Pause_Discharge"]
            if "Temp_Pause_Charge" in reg_cache_stack[4]:
                controlmode['Temp_Pause_Charge'] = reg_cache_stack[4]["Control"]["Temp_Pause_Charge"]
        else:
            controlmode['Temp_Pause_Charge'] = "Normal"
            controlmode['Temp_Pause_Discharge'] = "Normal"

        if exists(".FCRunning"):
            logger.debug("Force Charge is Running")
            controlmode['Force_Charge'] = "Running"
        else:
            controlmode['Force_Charge'] = "Normal"
        if exists(".FERunning"):
            logger.debug("Force_Export is Running")
            controlmode['Force_Export'] = "Running"
        else:
            logger.debug("Force Export is not Running")
            controlmode['Force_Export'] = "Normal"
        if exists(".tpcRunning"):
            logger.debug("Temp Pause Charge is Running")
            controlmode['Temp_Pause_Charge'] = "Running"
        else:
            controlmode['Temp_Pause_Charge'] = "Normal"
        if exists(".tpdRunning"):
            logger.debug("Temp_Pause_Discharge is Running")
            controlmode['Temp_Pause_Discharge'] = "Running"
        else:
            controlmode['Temp_Pause_Discharge'] = "Normal"


############  Battery Power Stats    ############

        battery_power = ge_inverter.p_battery
        if GivSettings.first_run:          # Make sure that we publish the HA message for both Charge and Discharge times
            power_output['Charge_Time_Remaining'] = 0
            power_output['Charge_Completion_Time'] = datetime.datetime.now().replace(tzinfo=GivLUT.timezone).isoformat()
            power_output['Discharge_Time_Remaining'] = 0
            power_output['Discharge_Completion_Time'] = datetime.datetime.now().replace(tzinfo=GivLUT.timezone).isoformat()
        if battery_power >= 0:
            discharge_power = abs(battery_power)
            charge_power = 0
            power_output['Charge_Time_Remaining'] = 0
            if discharge_power!=0:
                # Time to get from current SOC to battery Reserve at the current rate
                power_output['Discharge_Time_Remaining'] = max(int((((battery_capacity)/1000)*((power_output['SOC'] - controlmode['Battery_Power_Reserve'])/100) / (discharge_power/1000)) * 60),0)
                finaltime=datetime.datetime.now() + timedelta(minutes=power_output['Discharge_Time_Remaining'])
                power_output['Discharge_Completion_Time'] = finaltime.replace(tzinfo=GivLUT.timezone).isoformat()
            else:
                power_output['Discharge_Time_Remaining'] = 0
        elif battery_power <= 0:
            discharge_power = 0
            charge_power = abs(battery_power)
            power_output['Discharge_Time_Remaining'] = 0
            if charge_power!=0:
                # Time to get from current SOC to target SOC at the current rate (Target SOC-Current SOC)xBattery Capacity
                power_output['Charge_Time_Remaining'] = max(int((((battery_capacity)/1000)*((controlmode['Target_SOC'] - power_output['SOC'])/100) / (charge_power/1000)) * 60),0)
                finaltime=datetime.datetime.now() + timedelta(minutes=power_output['Charge_Time_Remaining'])
                power_output['Charge_Completion_Time'] = finaltime.replace(tzinfo=GivLUT.timezone).isoformat()
            else:
                power_output['Charge_Time_Remaining'] = 0
        power_output['Battery_Power'] = battery_power
        power_output['Charge_Power'] = charge_power
        power_output['Discharge_Power'] = discharge_power
        power_output['Grid_Frequency'] = ge_inverter.f_ac1
        power_output['Inverter_Output_Frequency'] = ge_inverter.f_eps_backup

        # Power flows
        logger.debug("Getting Solar to H/B/G Power Flows")
        if pv_power > 0:
            solar_to_house = min(pv_power, load_power)
            power_flow_output['Solar_to_House'] = solar_to_house
            solar_to_battery = max((pv_power-solar_to_house)-export_power, 0)
            power_flow_output['Solar_to_Battery'] = solar_to_battery
            power_flow_output['Solar_to_Grid'] = max(pv_power - solar_to_house - solar_to_battery, 0)

        else:
            power_flow_output['Solar_to_House'] = 0
            power_flow_output['Solar_to_Battery'] = 0
            power_flow_output['Solar_to_Grid'] = 0

        # Battery to House
        logger.debug("Getting Battery to House Power Flow")
        battery_to_house = max(discharge_power-export_power, 0)
        power_flow_output['Battery_to_House'] = battery_to_house

        # Grid to Battery/House Power
        logger.debug("Getting Grid to Battery/House Power Flow")
        if import_power > 0:
            power_flow_output['Grid_to_Battery'] = charge_power-max(pv_power-load_power, 0)
            power_flow_output['Grid_to_House'] = max(import_power-charge_power, 0)

        else:
            power_flow_output['Grid_to_Battery'] = 0
            power_flow_output['Grid_to_House'] = 0

        # Battery to Grid Power
        logger.debug("Getting Battery to Grid Power Flow")
        if export_power > 0:
            power_flow_output['Battery_to_Grid'] = max(discharge_power-battery_to_house, 0)
        else:
            power_flow_output['Battery_to_Grid'] = 0

        # Check for all zeros
        checksum = 0
        for item in energy_total_output.items():
            checksum = checksum+energy_total_output[item]
        if checksum == 0:
            raise ValueError("All zeros returned by inverter, skipping update")

        ######## Grab Timeslots ########
        timeslots = {}
        logger.debug("Getting TimeSlot data")
        timeslots['Discharge_start_time_slot_1'] = ge_inverter.discharge_slot_1[0].isoformat()
        timeslots['Discharge_end_time_slot_1'] = ge_inverter.discharge_slot_1[1].isoformat()
        timeslots['Discharge_start_time_slot_2'] = ge_inverter.discharge_slot_2[0].isoformat()
        timeslots['Discharge_end_time_slot_2'] = ge_inverter.discharge_slot_2[1].isoformat()
        timeslots['Charge_start_time_slot_1'] = ge_inverter.charge_slot_1[0].isoformat()
        timeslots['Charge_end_time_slot_1'] = ge_inverter.charge_slot_1[1].isoformat()
        try:
            if inverter_model.generation in ("Gen 2","Gen 3"):
                timeslots['Charge_start_time_slot_2'] = ge_inverter.charge_slot_2[0].isoformat()
                timeslots['Charge_end_time_slot_2'] = ge_inverter.charge_slot_2[1].isoformat()
                timeslots['Charge_start_time_slot_3'] = ge_inverter.charge_slot_3[0].isoformat()
                timeslots['Charge_end_time_slot_3'] = ge_inverter.charge_slot_3[1].isoformat()
                timeslots['Charge_start_time_slot_4'] = ge_inverter.charge_slot_4[0].isoformat()
                timeslots['Charge_end_time_slot_4'] = ge_inverter.charge_slot_4[1].isoformat()
                timeslots['Charge_start_time_slot_5'] = ge_inverter.charge_slot_5[0].isoformat()
                timeslots['Charge_end_time_slot_5'] = ge_inverter.charge_slot_5[1].isoformat()
                timeslots['Charge_start_time_slot_6'] = ge_inverter.charge_slot_6[0].isoformat()
                timeslots['Charge_end_time_slot_6'] = ge_inverter.charge_slot_6[1].isoformat()
                timeslots['Charge_start_time_slot_7'] = ge_inverter.charge_slot_7[0].isoformat()
                timeslots['Charge_end_time_slot_7'] = ge_inverter.charge_slot_7[1].isoformat()
                timeslots['Charge_start_time_slot_8'] = ge_inverter.charge_slot_8[0].isoformat()
                timeslots['Charge_end_time_slot_8'] = ge_inverter.charge_slot_8[1].isoformat()
                timeslots['Charge_start_time_slot_9'] = ge_inverter.charge_slot_9[0].isoformat()
                timeslots['Charge_end_time_slot_9'] = ge_inverter.charge_slot_9[1].isoformat()
                timeslots['Charge_start_time_slot_10'] = ge_inverter.charge_slot_10[0].isoformat()
                timeslots['Charge_end_time_slot_10'] = ge_inverter.charge_slot_10[1].isoformat()
                timeslots['Discharge_start_time_slot_3'] = ge_inverter.discharge_slot_3[0].isoformat()
                timeslots['Discharge_end_time_slot_3'] = ge_inverter.discharge_slot_3[1].isoformat()
                timeslots['Discharge_start_time_slot_4'] = ge_inverter.discharge_slot_4[0].isoformat()
                timeslots['Discharge_end_time_slot_4'] = ge_inverter.discharge_slot_4[1].isoformat()
                timeslots['Discharge_start_time_slot_5'] = ge_inverter.discharge_slot_5[0].isoformat()
                timeslots['Discharge_end_time_slot_5'] = ge_inverter.discharge_slot_5[1].isoformat()
                timeslots['Discharge_start_time_slot_6'] = ge_inverter.discharge_slot_6[0].isoformat()
                timeslots['Discharge_end_time_slot_6'] = ge_inverter.discharge_slot_6[1].isoformat()
                timeslots['Discharge_start_time_slot_7'] = ge_inverter.discharge_slot_7[0].isoformat()
                timeslots['Discharge_end_time_slot_7'] = ge_inverter.discharge_slot_7[1].isoformat()
                timeslots['Discharge_start_time_slot_8'] = ge_inverter.discharge_slot_8[0].isoformat()
                timeslots['Discharge_end_time_slot_8'] = ge_inverter.discharge_slot_8[1].isoformat()
                timeslots['Discharge_start_time_slot_9'] = ge_inverter.discharge_slot_9[0].isoformat()
                timeslots['Discharge_end_time_slot_9'] = ge_inverter.discharge_slot_9[1].isoformat()
                timeslots['Discharge_start_time_slot_10'] = ge_inverter.discharge_slot_10[0].isoformat()
                timeslots['Discharge_end_time_slot_10'] = ge_inverter.discharge_slot_10[1].isoformat()
                controlmode['Charge_Target_SOC_2'] = ge_inverter.charge_target_soc_2
                controlmode['Charge_Target_SOC_3'] = ge_inverter.charge_target_soc_3
                controlmode['Charge_Target_SOC_4'] = ge_inverter.charge_target_soc_4
                controlmode['Charge_Target_SOC_5'] = ge_inverter.charge_target_soc_5
                controlmode['Charge_Target_SOC_6'] = ge_inverter.charge_target_soc_6
                controlmode['Charge_Target_SOC_7'] = ge_inverter.charge_target_soc_7
                controlmode['Charge_Target_SOC_8'] = ge_inverter.charge_target_soc_8
                controlmode['Charge_Target_SOC_9'] = ge_inverter.charge_target_soc_9
                controlmode['Charge_Target_SOC_10'] = ge_inverter.charge_target_soc_10
                controlmode['Discharge_Target_SOC_1'] = ge_inverter.discharge_target_soc_1
                controlmode['Discharge_Target_SOC_2'] = ge_inverter.discharge_target_soc_2
                controlmode['Discharge_Target_SOC_3'] = ge_inverter.discharge_target_soc_3
                controlmode['Discharge_Target_SOC_4'] = ge_inverter.discharge_target_soc_4
                controlmode['Discharge_Target_SOC_5'] = ge_inverter.discharge_target_soc_5
                controlmode['Discharge_Target_SOC_6'] = ge_inverter.discharge_target_soc_6
                controlmode['Discharge_Target_SOC_7'] = ge_inverter.discharge_target_soc_7
                controlmode['Discharge_Target_SOC_8'] = ge_inverter.discharge_target_soc_8
                controlmode['Discharge_Target_SOC_9'] = ge_inverter.discharge_target_soc_9
                controlmode['Discharge_Target_SOC_10'] = ge_inverter.discharge_target_soc_10
        except Exception:
            logger.debug("New Charge/Discharge timeslots don't exist for this model")

        try:
            timeslots['Battery_pause_start_time_slot'] = ge_inverter.battery_pause_slot[0].isoformat()
            timeslots['Battery_pause_end_time_slot'] = ge_inverter.battery_pause_slot[1].isoformat()
        except Exception:
            logger.debug("Battery Pause timeslots don't exist for this model")

        ######## Get Inverter Details ########
        inverter = {}
        logger.debug("Getting inverter Details")
        if ge_inverter.battery_type == 1:
            batterytype = "Lithium"
        if ge_inverter.battery_type == 0:
            batterytype = "Lead Acid"
        inverter['Battery_Type'] = batterytype
        inverter['Battery_Capacity_kWh'] = ((battery_capacity)/1000)
        inverter['Invertor_Serial_Number'] = ge_inverter.inverter_serial_number
        inverter['Modbus_Version'] = ge_inverter.modbus_version
        inverter['Invertor_Firmware'] = ge_inverter.arm_firmware_version
        inverter['Invertor_Time'] = ge_inverter.system_time.replace(tzinfo=GivLUT.timezone).isoformat()
        if ge_inverter.meter_type == 1:
            metertype = "EM115"
        if ge_inverter.meter_type == 0:
            metertype = "EM418"
        inverter['Meter_Type'] = metertype
        inverter['Invertor_Type'] = inverter_model.generation + " " + inverter_model.model
        inverter['Invertor_Max_Inv_Rate'] = inverter_model.invmaxrate
        inverter['Invertor_Max_Bat_Rate'] = inverter_model.batmaxrate
        inverter['Invertor_Temperature'] = ge_inverter.temp_inverter_heatsink

        ######## Get Battery Details ########
        battery = {}
        batteries2 = {}
        logger.debug("Getting Battery Details")
        for bat in ge_batteries:
            if bat.battery_serial_number.upper().isupper():          # Check for empty battery object responses and only process if they are complete (have a serial number)
                logger.debug("Building battery output: ")
                battery = {}
                battery['Battery_Serial_Number'] = bat.battery_serial_number
                if bat.battery_soc != 0:
                    battery['Battery_SOC'] = bat.battery_soc
                elif bat.battery_soc == 0 and 'multi_output_old' in locals():
                    battery['Battery_SOC'] = multi_output_old['Battery_Details'][bat.battery_serial_number]['Battery_SOC']
                elif bat.battery_soc == 0 and not 'multi_output_old' in locals():
                    battery['Battery_SOC'] = 1
                battery['Battery_Capacity'] = bat.battery_full_capacity
                battery['Battery_Design_Capacity'] = bat.battery_design_capacity
                battery['Battery_Remaining_Capacity'] = bat.battery_remaining_capacity
                battery['Battery_Firmware_Version'] = bat.bms_firmware_version
                battery['Battery_Cells'] = bat.battery_num_cells
                battery['Battery_Cycles'] = bat.battery_num_cycles
                battery['Battery_USB_present'] = bat.usb_inserted
                battery['Battery_Temperature'] = bat.temp_bms_mos
                battery['Battery_Voltage'] = bat.v_battery_cells_sum
                battery['Battery_Cell_1_Voltage'] = bat.v_battery_cell_01
                battery['Battery_Cell_2_Voltage'] = bat.v_battery_cell_02
                battery['Battery_Cell_3_Voltage'] = bat.v_battery_cell_03
                battery['Battery_Cell_4_Voltage'] = bat.v_battery_cell_04
                battery['Battery_Cell_5_Voltage'] = bat.v_battery_cell_05
                battery['Battery_Cell_6_Voltage'] = bat.v_battery_cell_06
                battery['Battery_Cell_7_Voltage'] = bat.v_battery_cell_07
                battery['Battery_Cell_8_Voltage'] = bat.v_battery_cell_08
                battery['Battery_Cell_9_Voltage'] = bat.v_battery_cell_09
                battery['Battery_Cell_10_Voltage'] = bat.v_battery_cell_10
                battery['Battery_Cell_11_Voltage'] = bat.v_battery_cell_11
                battery['Battery_Cell_12_Voltage'] = bat.v_battery_cell_12
                battery['Battery_Cell_13_Voltage'] = bat.v_battery_cell_13
                battery['Battery_Cell_14_Voltage'] = bat.v_battery_cell_14
                battery['Battery_Cell_15_Voltage'] = bat.v_battery_cell_15
                battery['Battery_Cell_16_Voltage'] = bat.v_battery_cell_16
                battery['Battery_Cell_1_Temperature'] = bat.temp_battery_cells_1
                battery['Battery_Cell_2_Temperature'] = bat.temp_battery_cells_2
                battery['Battery_Cell_3_Temperature'] = bat.temp_battery_cells_3
                battery['Battery_Cell_4_Temperature'] = bat.temp_battery_cells_4
                batteries2[bat.battery_serial_number] = battery
                logger.debug("Battery "+str(bat.battery_serial_number)+" added")
            else:
                logger.error("Battery Object empty so skipping")

        ######## Create multioutput and publish #########
        energy = {}
        energy["Today"] = energy_today_output
        energy["Total"] = energy_total_output
        power = {}
        power["Power"] = power_output
        power["Flows"] = power_flow_output
        multi_output["Power"] = power
        multi_output["Invertor_Details"] = inverter
        multi_output["Energy"] = energy
        multi_output["Timeslots"] = timeslots
        multi_output["Control"] = controlmode
        multi_output["Battery_Details"] = batteries2
        if GivSettings.Print_Raw_Registers:
            raw = {}
            raw["invertor"] = ge_inverter.dict()
            multi_output['raw'] = raw

        ######### Section where post processing of multi_ouput functions are called ###########

        # run ppkwh stats on firstrun and every half hour
        if 'multi_output_old' in locals():
            multi_output = rate_calcs(multi_output, multi_output_old)
        else:
            multi_output = rate_calcs(multi_output, multi_output)

        multi_output = calc_battery_value(multi_output)

        if 'multi_output_old' in locals():
            multi_output = data_cleansing(multi_output, reg_cache_stack[4])
        # only update cache if its the same set of keys as previous (don't update if data missing)

        if 'multi_output_old' in locals():
            m_o_list = dict_to_list(multi_output)
            m_o_o_list = dict_to_list(multi_output_old)
            data_diff = set(m_o_o_list) - set(m_o_list)
            if len(data_diff) > 0:
                for key in data_diff:
                    logger.debug(str(key)+" is missing from new data, publishing all other data")

        # Add new data to the stack
        reg_cache_stack.pop(0)
        reg_cache_stack.append(multi_output)

        # Get lastupdate from pickle if it exists
        with cacheLock:
            if exists(GivLUT.lastupdate):
                with open(GivLUT.lastupdate, 'rb') as inp:
                    previous_update = pickle.load(inp)
                timediff = datetime.datetime.fromisoformat(multi_output['Last_Updated_Time'])-datetime.datetime.fromisoformat(previous_update)
                multi_output['Time_Since_Last_Update'] = (((timediff.seconds*1000000)+timediff.microseconds)/1000000)

            # Save new time to pickle
            with open(GivLUT.lastupdate, 'wb') as outp:
                pickle.dump(multi_output['Last_Updated_Time'], outp, pickle.HIGHEST_PROTOCOL)

            # Save new data to Pickle
            with open(GivLUT.regcache, 'wb') as outp:
                pickle.dump(reg_cache_stack, outp, pickle.HIGHEST_PROTOCOL)
            logger.debug("Successfully retrieved from: " + GivSettings.invertorIP)
            result['result'] = "Success retrieving data"

            # Success, so delete oldDataCount
            if exists(GivLUT.oldDataCount):
                os.remove(GivLUT.oldDataCount)
    except Exception:
        error = sys.exc_info()
        consec_fails(error)
        logger.error("inverter Update failed so using last known good data from cache")
        result['result'] = "Error processing registers: " + str(error)
        return json.dumps(result)
    return json.dumps(result, indent=4, sort_keys=True, default=str)

def consec_fails(error):
    """Track consecutive inverter read fails and kick if reaches max"""
    with cacheLock:
        if exists(GivLUT.oldDataCount):
            with open(GivLUT.oldDataCount, 'rb') as inp:
                old_data_count= pickle.load(inp)
            old_data_count = old_data_count + 1
            if old_data_count > 3:
                logger.error("Consecutive failure count= "+str(old_data_count) +" -- "+ str(error))
        else:
            old_data_count = 1
        if old_data_count>10:
            #10 error in a row so delete regCache data
            logger.error("10 failed inverter reads in a row so removing regCache to force update...")
            if exists(GivLUT.regcache):
                os.remove(GivLUT.regcache)
            if exists(GivLUT.batterypkl):
                os.remove(GivLUT.batterypkl)
            if exists(GivLUT.oldDataCount):
                os.remove(GivLUT.oldDataCount)
        else:
            with open(GivLUT.oldDataCount, 'wb') as outp:
                pickle.dump(old_data_count, outp, pickle.HIGHEST_PROTOCOL)

def run_all(full_refresh):  # Read from Inverter put in cache and publish
    """Run both getting data and publishing data"""
    # full_refresh=True
    #from read import get_data
    get_data(full_refresh)
    # Step here to validate data against previous pickle?
    multi_output = pub_from_pickle()
    return multi_output

def pub_from_json():
    """Test funciton to push from json"""
    temp = open('GivTCP\\testdata.json',encoding='ascii')
    data = json.load(temp)
    serial_number = data["Invertor_Details"]['Invertor_Serial_Number']
    publish_output(data, serial_number)


def pub_from_pickle():
    """Publish last cached Inverter Data"""
    multi_output = {}
    result = "Success"
    if not exists(GivLUT.regcache):  # if there is no cache, create it
        result = "Please get data from Inverter first, either by calling run_all or waiting until the self-run has completed"
    if "Success" in result:
        with cacheLock:
            with open(GivLUT.regcache, 'rb') as inp:
                reg_cache_stack = pickle.load(inp)
                multi_output = reg_cache_stack[4]
        serial_number = multi_output["Invertor_Details"]['Invertor_Serial_Number']
        publish_output(multi_output, serial_number)
    else:
        multi_output['result'] = result
    return json.dumps(multi_output, indent=4, sort_keys=True, default=str)

def get_cache():
    """Get latest cache data and return it (for use in REST)"""
    multi_output={}
    with open(GivLUT.regcache, 'rb') as inp:
        reg_cache_stack = pickle.load(inp)
        multi_output = reg_cache_stack[4]
    return json.dumps(multi_output, indent=4, sort_keys=True, default=str)

def self_run2():
    """Main function to loop through read and publish"""
    counter = 0
    run_all("True")
    while True:
        counter = counter+1
        if exists(GivLUT.forcefullrefresh):
            run_all("True")
            os.remove(GivLUT.forcefullrefresh)
            counter = 0
        elif counter == 20:
            counter = 0
            run_all("True")
        else:
            run_all("False")
        time.sleep(GivSettings.self_run_timer)


# Additional Publish options can be added here.
# A separate file in the folder can be added with a new publish "plugin"
# then referenced here with any settings required added into settings.py

def publish_output(array, serial_number):
    """Push output to multiple locations"""
    tempoutput = {}
    tempoutput = iterate_dict(array)
#    threader = Threader(5)
    if GivSettings.MQTT_Output:
        if GivSettings.first_run:        # 09-July-23 - HA is seperated to seperate if check.
            # Do this in a thread?
#            threader.append(update_first_run,serial_number)
            update_first_run(serial_number)              # 09=July=23 - Always do this first irrespective of HA setting.
            if GivSettings.HA_Auto_D:        # Home Assistant MQTT Discovery
                logger.critical("Publishing Home Assistant Discovery messages")
                from ha_discovery import HAMQTT
                HAMQTT.publish_discovery(tempoutput, serial_number)
#                threader.append(HAMQTT.publish_discovery,tempoutput, serial_number)
            GivSettings.first_run = False  # 09-July-23 - Always set firstrun irrespective of HA setting.
# Do this in a thread?
        from mqtt import GivMQTT
        logger.debug("Publish all to MQTT")
        if GivSettings.MQTT_Topic == "":
            GivSettings.MQTT_Topic = "GivEnergy"
        GivMQTT.multi_mqtt_publish(str(GivSettings.MQTT_Topic+"/"+serial_number+"/"), tempoutput)
#        threader.append(GivMQTT.multi_mqtt_publish,str(GivSettings.MQTT_Topic+"/"+serial_number+"/"), tempoutput)
# Do this in a thread?
    if GivSettings.Influx_Output:
        from influx import GivInflux
        logger.debug("Pushing output to Influx")
        GivInflux.publish(serial_number, tempoutput)
#        threader.append(GivInflux.publish,serial_number, tempoutput)
#        logger.info("Starting publishing threads")
#        threader.start()
#        threader.join()
#        logger.info("Publishing threads finished")

def update_first_run(serial_number):
    """Update settings file on first run"""
    isserial_number = False
    script_dir = os.path.dirname(__file__)  # <-- absolute dir the script is in
    rel_path = "settings.py"
    abs_file_path = os.path.join(script_dir, rel_path)
    with open(abs_file_path, "r",encoding='ascii') as settings_file:
        lines = settings_file.readlines()
    with open(abs_file_path, "w",encoding='ascii') as settings_file:
        for line in lines:
            if line.strip("\n") == "    first_run= True":
                settings_file.write("    first_run= False\n")
            else:
                settings_file.write(line)
            if "serial_number" in line:
                isserial_number = True
        if not isserial_number:
            settings_file.writelines("    serial_number = \""+serial_number+"\"\n")  # only add serial_number if its not there


def iterate_dict(array):
    """Create a publish safe version of the output (convert non string or int datapoints)"""
    safeoutput = {}
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
            logger.debug('Converting time to publish safe string')
            safeoutput[p_load] = output.name
        elif isinstance(output, float):
            safeoutput[p_load] = round(output, 3)
        else:
            safeoutput[p_load] = output
    return safeoutput


def rate_calcs(multi_output, multi_output_old):
    """Calculates the current energy rates"""
    rate_data = {}
    day_rate_start = datetime.datetime.strptime(GivSettings.day_rate_start, '%H:%M')
    night_rate_start = datetime.datetime.strptime(GivSettings.night_rate_start, '%H:%M')
    night_start = datetime.datetime.combine(datetime.datetime.now(GivLUT.timezone).date(),night_rate_start.time()).replace(tzinfo=GivLUT.timezone)
    logger.debug("Night Start= "+datetime.datetime.strftime(night_start, '%c'))
    day_start = datetime.datetime.combine(datetime.datetime.now(GivLUT.timezone).date(),day_rate_start.time()).replace(tzinfo=GivLUT.timezone)
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
    if 'Night_Start_Energy_kWh' not in rate_data:
        logger.debug("No Night Start Energy so setting it to: %s",str(import_energy))
        rate_data['Night_Start_Energy_kWh'] = import_energy
    if 'Day_Start_Energy_kWh' not in rate_data:
        logger.debug("No Day Start Energy so setting it to: %s",str(import_energy))
        rate_data['Day_Start_Energy_kWh'] = import_energy
    if 'Night_Energy_kWh' not in rate_data:
        rate_data['Night_Energy_kWh'] = 0.00
    if 'Day_Energy_kWh' not in rate_data:
        rate_data['Day_Energy_kWh'] = 0.00
    if 'Night_Cost' not in rate_data:
        rate_data['Night_Cost'] = 0.00
    if 'Day_Cost' not in rate_data:
        rate_data['Day_Cost'] = 0.00
    if 'Night_Energy_Total_kWh' not in rate_data:
        rate_data['Night_Energy_Total_kWh'] = 0
    if 'Day_Energy_Total_kWh' not in rate_data:
        rate_data['Day_Energy_Total_kWh'] = 0

# Always update rates from new setting
    rate_data['Export_Rate'] = GivSettings.export_rate
    rate_data['Day_Rate'] = GivSettings.day_rate
    rate_data['Night_Rate'] = GivSettings.night_rate

    # if midnight then reset costs
    if datetime.datetime.now(GivLUT.timezone).hour == 0 and datetime.datetime.now(GivLUT.timezone).minute == 0:
        logger.critical("Midnight, so resetting Day/Night stats...")
        rate_data['Night_Cost'] = 0.00
        rate_data['Day_Cost'] = 0.00
        rate_data['Night_Energy_kWh'] = 0.00
        rate_data['Day_Energy_kWh'] = 0.00
        rate_data['Day_Start_Energy_kWh'] = import_energy
        rate_data['Night_Start_Energy_kWh'] = import_energy
        rate_data['Day_Energy_Total_kWh'] = 0
        rate_data['Night_Energy_Total_kWh'] = 0

    if GivSettings.dynamic_tariff is False:     ## If we use externally triggered rates then don't do the time check but assume the rate files are set elsewhere (default to Day if not set)
        if day_rate_start.hour == datetime.datetime.now(GivLUT.timezone).hour and day_rate_start.minute == datetime.datetime.now(GivLUT.timezone).minute:
            open(GivLUT.dayRateRequest, 'w',encoding='ascii').close()
        elif night_rate_start.hour == datetime.datetime.now(GivLUT.timezone).hour and night_rate_start.minute == datetime.datetime.now(GivLUT.timezone).minute:
            open(GivLUT.nightRateRequest, 'w',encoding='ascii').close()
        # Otherwise check to see if dynamic trigger has been received to change rate type

    if exists(GivLUT.nightRateRequest):
        os.remove(GivLUT.nightRateRequest)
        if not exists(GivLUT.nightRate):
            #Save last total from todays dayrate so far
            rate_data['Day_Energy_Total_kWh']=rate_data['Day_Energy_kWh']       # save current day energy at the end of the slot
            logger.info("Saving current energy stats at start of night rate tariff (Dynamic)")
            rate_data['Night_Start_Energy_kWh'] = import_energy-rate_data['Night_Energy_Total_kWh']     #offset current night energy from current energy to combine into a single slot
            open(GivLUT.nightRate, 'w',encoding='ascii').close()
            if exists(GivLUT.dayRate):
                logger.debug(".dayRate exists so deleting it")
                os.remove(GivLUT.dayRate)
    elif exists(GivLUT.dayRateRequest):
        os.remove(GivLUT.dayRateRequest)
        if not exists(GivLUT.dayRate):
            rate_data['Night_Energy_Total_kWh']=rate_data['Night_Energy_kWh']   # save current night energy at the end of the slot
            logger.info("Saving current energy stats at start of day rate tariff (Dynamic)")
            rate_data['Day_Start_Energy_kWh'] = import_energy-rate_data['Day_Energy_Total_kWh']     # offset current day energy from current energy to combine into a single slot
            open(GivLUT.dayRate, 'w',encoding='ascii').close()
            if exists(GivLUT.nightRate):
                logger.debug(".nightRate exists so deleting it")
                os.remove(GivLUT.nightRate)

    if not exists(GivLUT.nightRate) and not exists(GivLUT.dayRate): #Default to Day if not previously set
        logger.info("No day/Night rate info so reverting to day")
        open(GivLUT.dayRate, 'w',encoding='ascii').close()

    if exists(GivLUT.dayRate):
        rate_data['Current_Rate_Type'] = "Day"
        rate_data['Current_Rate'] = GivSettings.day_rate
        logger.debug("Setting Rate to Day")
    else:
        rate_data['Current_Rate_Type'] = "Night"
        rate_data['Current_Rate'] = GivSettings.night_rate
        logger.debug("Setting Rate to Night")


    # now calc the difference for each value between the correct start pickle and now
    if import_energy>import_energy_old: # Only run if there has been more import
        logger.debug("Imported more energy so calculating current tariff costs: %s -> ",str(import_energy_old),str(import_energy))
#        if night_start <= datetime.datetime.now(GivLUT.timezone) < day_start:
        if exists(GivLUT.nightRate):
            logger.debug("Current Tariff is Night, calculating stats...")
            # Add change in energy this slot to previous rate_data
            rate_data['Night_Energy_kWh'] = import_energy-rate_data['Night_Start_Energy_kWh']
            logger.debug("Night_Energy_kWh=" +str(import_energy)+" - "+str(rate_data['Night_Start_Energy_kWh']))
            rate_data['Night_Cost'] = float(rate_data['Night_Energy_kWh'])*float(GivSettings.night_rate)
            logger.debug("Night_Cost= "+str(rate_data['Night_Energy_kWh'])+"kWh x £"+str(float(GivSettings.night_rate))+"/kWh = £"+str(rate_data['Night_Cost']))
            rate_data['Current_Rate'] = GivSettings.night_rate
        else:
            logger.debug("Current Tariff is Day, calculating stats...")
            rate_data['Day_Energy_kWh'] = import_energy-rate_data['Day_Start_Energy_kWh']
            logger.debug("Day_Energy_kWh=" + str(import_energy)+" - "+str(rate_data['Day_Start_Energy_kWh']))
            rate_data['Day_Cost'] = float(rate_data['Day_Energy_kWh'])*float(GivSettings.day_rate)
            logger.debug("Day_Cost= "+str(rate_data['Day_Energy_kWh'])+"kWh x £"+str(float(GivSettings.day_rate))+"/kWh = £"+str(rate_data['Day_Cost']))
            rate_data['Current_Rate'] = GivSettings.day_rate

        if (multi_output['Energy']['Today']['Load_Energy_Today_kWh']) != 0:
            rate_data['Import_ppkwh_Today'] = round((rate_data['Day_Cost']+rate_data['Night_Cost'])/(multi_output['Energy']['Today']['Import_Energy_Today_kWh']), 3)
            logger.debug("Import_ppkwh_Today= (£"+str(rate_data['Day_Cost'])+" + £"+str(rate_data['Night_Cost'])+") div "+str(multi_output['Energy']['Today']['Load_Energy_Today_kWh'])+"kWh = £"+str(rate_data['Import_ppkwh_Today'])+"/kWh")

    multi_output['Energy']['Rates'] = rate_data

    # dump current data to Pickle
    with open(GivLUT.ratedata, 'wb') as outp:
        pickle.dump(rate_data, outp, pickle.HIGHEST_PROTOCOL)

    return multi_output


def data_cleansing(data, reg_cache_stack):
    """Top level function to initiate data smoother"""
    logger.debug("Running the data cleansing process")
    # iterate multi_output to get each end result dict.
    # Loop that dict to validate against
    new_multi_output = loop_dict(data, reg_cache_stack, data["Last_Updated_Time"])
    return new_multi_output

def dict_to_list(array):
    """Helper function to convert dict to List"""
    safeoutput = []
    # finaloutput={}
    # arrayout={}
    for p_load in array:
        output = array[p_load]
        safeoutput.append(p_load)
        if isinstance(output, dict):
            safeoutput = safeoutput+dict_to_list(output)
    return safeoutput

def loop_dict(array, reg_cache_stack, last_update):
    """Helper function to loop through nested dict and send each item to data smoother"""
    safeoutput = {}
    # finaloutput={}
    # arrayout={}
    for p_load in array:
        output = array[p_load]
        if p_load == "raw":  # skip data cleansing for raw data
            safeoutput[p_load] = output
            continue
        if isinstance(output, dict):
            if p_load in reg_cache_stack:
                temp = loop_dict(output, reg_cache_stack[p_load], last_update)
                safeoutput[p_load] = temp
                logger.debug('Data cleansed for: '+str(p_load))
            else:
                logger.debug(str(p_load)+" has no data in the cache so using new value.")
                safeoutput[p_load] = output
        else:
            # run datasmoother on the data item
            # only run if old data exists otherwise return the existing value
            if p_load in reg_cache_stack:
                safeoutput[p_load] = data_smoother([p_load, output], [p_load, reg_cache_stack[p_load]], last_update)
            else:
                logger.debug(p_load+" has no data in the cache so using new value.")
                safeoutput[p_load] = output
    return safeoutput

def data_smoother(data_new, data_old, last_update):
    """Perform test to validate data and smooth out spikes"""
    new_data = data_new[1]
    old_data = data_old[1]
    name = data_new[0]
    lookup = givLUT[name]
    if GivSettings.data_smoother.lower() == "high":
        smooth_rate = 0.25
    elif GivSettings.data_smoother.lower() == "medium":
        smooth_rate = 0.35
    elif GivSettings.data_smoother.lower() == "none":
        return new_data
    else:
        smooth_rate = 0.50
    if isinstance(new_data, int) or isinstance(new_data, float):
        if old_data != 0:
            then = datetime.datetime.fromisoformat(last_update)
            now = datetime.datetime.now(GivLUT.timezone)
    ### Run checks against the conditions in GivLUT ###
            if now.minute == 0 and now.hour == 0 and "Today" in name:  # Treat Today stats as a special case
                logger.debug("Midnight and "+str(name)+" so accepting value as is")
                return data_new
            if new_data < float(lookup.min) or new_data > float(lookup.max):  # If outside min and max ranges
                logger.debug(str(name)+" is outside of allowable bounds so using old value. Out of bounds value is: "+str(new_data) + ". Min limit: " + str(lookup.min) + ". Max limit: " + str(lookup.max))
                return old_data
            if new_data == 0 and not lookup.allowZero:  # if zero and not allowed to be
                logger.debug(str(name)+" is Zero so using old value")
                return old_data
            if lookup.smooth:     # apply smoothing if required
                if new_data != old_data:  # Only if its not the same
                    time_delta = (now-then).total_seconds()
                    data_delta = abs(new_data-old_data)/old_data
                    if data_delta > smooth_rate and time_delta < 60:
                        logger.debug(str(name)+" jumped too far in a single read: "+str(old_data)+"->"+str(new_data)+" so using previous value")
                        return old_data
            if lookup.onlyIncrease:  # if data can only increase then check
                if (old_data-new_data) > 0.11:
                    logger.debug(str(name)+" has decreased so using old value")
                    return old_data
    return new_data


def calc_battery_value(multi_output):
    """Calculate the monetary value of the battery based on incoming energy (solar/grid)"""
    # get current data from read pickle
    batterystats = {}
    if exists(GivLUT.batterypkl):
        with open(GivLUT.batterypkl, 'rb') as inp:
            batterystats = pickle.load(inp)
    else:       # if no old AC charge, then set it to now and zero out value and ppkwh
        logger.critical("First time running so saving AC Charge status")
        batterystats['AC Charge last'] = float(multi_output['Energy']['Total']['AC_Charge_Energy_Total_kWh'])
        batterystats['Battery_Value'] = 0
        batterystats['Battery_ppkwh'] = 0
        batterystats['Battery_kWh_old'] = multi_output['Power']['Power']['SOC_kWh']

    if GivSettings.first_run or datetime.datetime.now(GivLUT.timezone).minute == 59 or datetime.datetime.now(GivLUT.timezone).minute == 29:
        if not exists(GivLUT.ppkwhtouch) and exists(GivLUT.batterypkl):      # only run this if there is no touchfile but there is a battery stat
            battery_kwh = multi_output['Power']['Power']['SOC_kWh']
            ac_charge = float(multi_output['Energy']['Total']['AC_Charge_Energy_Total_kWh'])-float(batterystats['AC Charge last'])
            logger.debug("Battery_kWh has gone from: "+str(batterystats['Battery_kWh_old'])+" -> "+str(battery_kwh))
            if float(battery_kwh) > float(batterystats['Battery_kWh_old']):
                logger.debug("Battery has been charged in the last 30mins so recalculating battery value and ppkwh: ")
                bat_val = batterystats['Battery_Value']
                money_in = round(ac_charge*float(multi_output['Energy']['Rates']['Current_Rate']), 2)
                logger.debug("Money_in= "+str(round(ac_charge, 2))+"kWh * £"+str(float(multi_output['Energy']['Rates']['Current_Rate']))+"/kWh = £"+str(money_in))
                batterystats['Battery_Value'] = round(float(batterystats['Battery_Value']) + money_in, 3)
                logger.debug("Battery_Value= £"+str(float(bat_val))+" + £"+str(money_in)+" = £"+str(batterystats['Battery_Value']))
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
            open(GivLUT.ppkwhtouch, 'w',encoding='ascii').close()       # set touch file  to stop repeated triggers in the single minute

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
    return multi_output


if __name__ == '__main__':
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])

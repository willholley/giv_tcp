"""LUT for GivTCP"""

import logging
import os
import zoneinfo
from logging.handlers import TimedRotatingFileHandler
import datetime
from redis import Redis
from rq import Queue
from givenergy_modbus.model.plant import Plant
from givenergy_modbus.client import GivEnergyClient
from settings import GivSettings

class GivClient:
    """Creates CLient to access inverter via modbus"""
    def __init__(self,fullrefresh:bool):
        self.fullrefresh=fullrefresh
    
    def get_data(self):
        """Gets Data from inverter using lib"""
        client= GivEnergyClient(host=GivSettings.invertorIP)
        numbat=GivSettings.numBatteries
        plant=Plant(number_batteries=numbat)
        client.refresh_plant(plant,GivSettings.is_AIO,GivSettings.is_AC,self.fullrefresh)
        return plant

class GivQueue:
    """Instantiates a Redis Q for use in GivTCP"""
    redis_connection = Redis(host='127.0.0.1', port=6379, db=0)
    q = Queue("GivTCP_"+str(GivSettings.givtcp_instance),connection=redis_connection)

class GEType:
    """Defines type for data objects"""
    def __init__(self,dT,sC,cF,mn,mx,aZ,sM,oI):
        self.devType = dT
        self.sensorClass=sC
        self.controlFunc=cF
        self.min=mn
        self.max=mx
        self.allowZero=aZ
        self.smooth=sM
        self.onlyIncrease=oI

class InvType:
    """Defines data type for Inverter model attributes"""
    def __init__(self,phase,model,invmaxrate,batmaxrate,generation):
        self.phase=phase
        self.model=model
        self.invmaxrate=invmaxrate
        self.batmaxrate=batmaxrate
        self.generation=generation

class GivLUT:
    """Creates LUT for use in GivTCP"""

    #Logging data
    logging.basicConfig(format='%(asctime)s - Inv'+ str(GivSettings.givtcp_instance)+
                        ' - %(module)-11s -  [%(levelname)-8s] - %(message)s')
    formatter = logging.Formatter('%(asctime)s - %(module)s - [%(levelname)s] - %(message)s')
    filehandler = TimedRotatingFileHandler(GivSettings.Debug_File_Location, when='midnight', backupCount=7)
    filehandler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(filehandler)
    if str(os.getenv("LOG_LEVEL")).lower()=="debug":
        logger.setLevel(logging.DEBUG)
    elif str(os.getenv("LOG_LEVEL")).lower()=="info":
        logger.setLevel(logging.INFO)
    elif str(os.getenv("LOG_LEVEL")).lower()=="critical":
        logger.setLevel(logging.CRITICAL)
    elif str(os.getenv("LOG_LEVEL")).lower()=="warning":
        logger.setLevel(logging.WARNING)
    else:
        logger.setLevel(logging.ERROR)

    # File paths for use
    lockfile=".lockfile"
    regcache=GivSettings.cache_location+"/regCache_"+str(GivSettings.givtcp_instance)+".pkl"
    ratedata=GivSettings.cache_location+"/rateData_"+str(GivSettings.givtcp_instance)+".pkl"
    lastupdate=GivSettings.cache_location+"/lastUpdate_"+str(GivSettings.givtcp_instance)+".pkl"
    forcefullrefresh=GivSettings.cache_location+"/.forceFullRefresh_"+str(GivSettings.givtcp_instance)
    batterypkl=GivSettings.cache_location+"/battery_"+str(GivSettings.givtcp_instance)+".pkl"
    reservepkl=GivSettings.cache_location+"/reserve_"+str(GivSettings.givtcp_instance)+".pkl"
    ppkwhtouch=".ppkwhtouch"
    schedule=".schedule"
    oldDataCount=GivSettings.cache_location+"/oldDataCount_"+str(GivSettings.givtcp_instance)+".pkl"
    nightRate=GivSettings.cache_location+"/.nightRate"
    dayRate=GivSettings.cache_location+"/.dayRate"
    nightRateRequest=GivSettings.cache_location+"/.nightRateRequest"
    dayRateRequest=GivSettings.cache_location+"/.dayRateRequest"
    invippkl=GivSettings.cache_location+"/invIPList.pkl"

    if hasattr(GivSettings,'timezone'):                        # If in Addon, use the HA Supervisor timezone
        timezone=zoneinfo.ZoneInfo(key=GivSettings.timezone)
    elif "TZ" in os.environ:                                    # Otherwise use the ENV (for Docker)
        timezone=zoneinfo.ZoneInfo(key=os.getenv("TZ"))
    else:
        timezone=zoneinfo.ZoneInfo(key="Europe/London")         # Otherwise Assume everyone is in UK!

    # Standard values for devices
    maxInvPower=11000
    maxPower=30000
    maxBatPower=7500
    maxTemp=100
    maxCellVoltage=4
    maxTotalEnergy=100000000
    maxTodayEnergy=100000
    maxCost=100
    maxRate=2
    Last_Updated_Time=GEType("sensor","timestamp","","","",False,False,False)

    entity_type={
        "Last_Updated_Time":GEType("sensor","timestamp","","","",False,False,False),
        "Time_Since_Last_Update":GEType("sensor","","",0,10000,True,False,False),
        "status":GEType("sensor","string","","","",False,False,False),
        "Export_Energy_Total_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,True,True),
        "Battery_Throughput_Total_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,True,True),
        "AC_Charge_Energy_Total_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,True,True),
        "Import_Energy_Total_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,True,True),
        "Invertor_Energy_Total_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,True,True),
        "PV_Energy_Total_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,True,True),
        "Load_Energy_Total_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,True,True),
        "Battery_Charge_Energy_Total_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,True,True),
        "Battery_Discharge_Energy_Total_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,True,True),
        "Self_Consumption_Energy_Total_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,True,True),
        "Battery_Throughput_Today_kWh":GEType("sensor","energy","",0,maxTodayEnergy,True,False,False),
        "PV_Energy_Today_kWh":GEType("sensor","energy","",0,maxTodayEnergy,True,False,False),
        "Import_Energy_Today_kWh":GEType("sensor","energy","",0,maxTodayEnergy,True,False,False),
        "Export_Energy_Today_kWh":GEType("sensor","energy","",0,maxTodayEnergy,True,False,False),
        "AC_Charge_Energy_Today_kWh":GEType("sensor","energy","",0,maxTodayEnergy,True,False,False),
        "Invertor_Energy_Today_kWh":GEType("sensor","energy","",0,maxTodayEnergy,True,False,False),
        "Battery_Charge_Energy_Today_kWh":GEType("sensor","energy","",0,maxTodayEnergy,True,False,False),
        "Battery_Discharge_Energy_Today_kWh":GEType("sensor","energy","",0,maxTodayEnergy,True,False,False),
        "Self_Consumption_Energy_Today_kWh":GEType("sensor","energy","",0,maxTodayEnergy,True,False,False),
        "Load_Energy_Today_kWh":GEType("sensor","energy","",0,maxTodayEnergy,True,False,False),
        "PV_Power_String_1":GEType("sensor","power","",0,10000,True,False,False),
        "PV_Power_String_2":GEType("sensor","power","",0,10000,True,False,False),
        "PV_Power":GEType("sensor","power","",0,maxPower,True,False,False),
        "PV_Voltage_String_1":GEType("sensor","voltage","",0,550,True,False,False),
        "PV_Voltage_String_2":GEType("sensor","voltage","",0,550,True,False,False),
        "PV_Current_String_1":GEType("sensor","current","",0,20,True,False,False),
        "PV_Current_String_2":GEType("sensor","current","",0,20,True,False,False),
        "Grid_Power":GEType("sensor","power","",-maxPower,maxPower,True,False,False),
        "Grid_Current":GEType("sensor","current","",-120,120,False,False,False),
        "Grid_Voltage":GEType("sensor","voltage","",150,300,False,True,False),
        "Import_Power":GEType("sensor","power","",0,maxPower,True,False,False),
        "Export_Power":GEType("sensor","power","",0,maxInvPower,True,False,False),
        "EPS_Power":GEType("sensor","power","",0,10000,True,False,False),
        "Invertor_Power":GEType("sensor","power","",-maxInvPower,maxInvPower,True,False,False),
        "Load_Power":GEType("sensor","power","",0,maxPower,True,False,False),
        "AC_Charge_Power":GEType("sensor","power","",0,maxBatPower,True,False,False),
        "Self_Consumption_Power":GEType("sensor","power","",0,maxInvPower,True,False,False),
        "Battery_Power":GEType("sensor","power","",-maxBatPower,maxBatPower,True,False,False),
        "Charge_Power":GEType("sensor","power","",0,maxBatPower,True,False,False),
        "Discharge_Power":GEType("sensor","power","",0,maxBatPower,True,False,False),
        "SOC":GEType("sensor","battery","",0,100,False,False,False),
        "SOC_kWh":GEType("sensor","energy","",0,50,True,False,False),
        "Solar_to_House":GEType("sensor","power","",0,maxInvPower,True,False,False),
        "Solar_to_Battery":GEType("sensor","power","",0,maxInvPower,True,False,False),
        "Solar_to_Grid":GEType("sensor","power","",0,maxInvPower,True,False,False),
        "Battery_to_House":GEType("sensor","power","",0,maxBatPower,True,False,False),
        "Grid_to_Battery":GEType("sensor","power","",0,maxPower,True,False,False),
        "Grid_to_House":GEType("sensor","power","",0,maxPower,True,False,False),
        "Battery_to_Grid":GEType("sensor","power","",0,maxBatPower,True,False,False),
        "Battery_Type":GEType("sensor","string","","","",False,False,False),
        "Battery_Capacity_kWh":GEType("sensor","","",0,maxBatPower,True,True,False),
        "Invertor_Serial_Number":GEType("sensor","string","","","",False,False,False),
        "Invertor_Time":GEType("sensor","timestamp","","","",False,False,False),
        "Invertor_Max_Inv_Rate":GEType("sensor","","",0,maxInvPower,True,False,False),
        "Invertor_Max_Bat_Rate":GEType("sensor","","",0,maxBatPower,True,False,False),
        "Active_Power_Rate":GEType("number","","setActivePowerRate",0,100,True,False,False),
        "Invertor_Firmware":GEType("sensor","string","",0,10000,False,False,False),
        "Modbus_Version":GEType("sensor","","",1,10,False,True,False),
        "Meter_Type":GEType("sensor","string","","","",False,False,False),
        "Invertor_Type":GEType("sensor","string","","","",False,False,False),
        "Invertor_Temperature":GEType("sensor","temperature","",-maxTemp,maxTemp,True,True,False),

        "Discharge_start_time_slot_1":GEType("select","","setDischargeStart1","","",False,False,False),
        "Discharge_end_time_slot_1":GEType("select","","setDischargeEnd1","","",False,False,False),
        "Discharge_start_time_slot_2":GEType("select","","setDischargeStart2","","",False,False,False),
        "Discharge_end_time_slot_2":GEType("select","","setDischargeEnd2","","",False,False,False),
        "Discharge_start_time_slot_3":GEType("select","","setDischargeStart3","","",False,False,False),
        "Discharge_end_time_slot_3":GEType("select","","setDischargeEnd3","","",False,False,False),
        "Discharge_start_time_slot_4":GEType("select","","setDischargeStart4","","",False,False,False),
        "Discharge_end_time_slot_4":GEType("select","","setDischargeEnd4","","",False,False,False),
        "Discharge_start_time_slot_5":GEType("select","","setDischargeStart5","","",False,False,False),
        "Discharge_end_time_slot_5":GEType("select","","setDischargeEnd5","","",False,False,False),
        "Discharge_start_time_slot_6":GEType("select","","setDischargeStart6","","",False,False,False),
        "Discharge_end_time_slot_6":GEType("select","","setDischargeEnd6","","",False,False,False),
        "Discharge_start_time_slot_7":GEType("select","","setDischargeStart7","","",False,False,False),
        "Discharge_end_time_slot_7":GEType("select","","setDischargeEnd7","","",False,False,False),
        "Discharge_start_time_slot_8":GEType("select","","setDischargeStart8","","",False,False,False),
        "Discharge_end_time_slot_8":GEType("select","","setDischargeEnd8","","",False,False,False),
        "Discharge_start_time_slot_9":GEType("select","","setDischargeStart9","","",False,False,False),
        "Discharge_end_time_slot_9":GEType("select","","setDischargeEnd9","","",False,False,False),
        "Discharge_start_time_slot_10":GEType("select","","setDischargeStart10","","",False,False,False),
        "Discharge_end_time_slot_10":GEType("select","","setDischargeEnd10","","",False,False,False),
        "Battery_pause_start_time_slot":GEType("select","","setPauseStart","","",False,False,False),
        "Battery_pause_end_time_slot":GEType("select","","setPauseEnd","","",False,False,False),

        "Charge_start_time_slot_1":GEType("select","","setChargeStart1","","",False,False,False),
        "Charge_end_time_slot_1":GEType("select","","setChargeEnd1","","",False,False,False),
        "Charge_start_time_slot_2":GEType("select","","setChargeStart2","","",False,False,False),
        "Charge_end_time_slot_2":GEType("select","","setChargeEnd2","","",False,False,False),
        "Charge_start_time_slot_3":GEType("select","","setChargeStart3","","",False,False,False),
        "Charge_end_time_slot_3":GEType("select","","setChargeEnd3","","",False,False,False),
        "Charge_start_time_slot_4":GEType("select","","setChargeStart4","","",False,False,False),
        "Charge_end_time_slot_4":GEType("select","","setChargeEnd4","","",False,False,False),
        "Charge_start_time_slot_5":GEType("select","","setChargeStart5","","",False,False,False),
        "Charge_end_time_slot_5":GEType("select","","setChargeEnd5","","",False,False,False),
        "Charge_start_time_slot_6":GEType("select","","setChargeStart6","","",False,False,False),
        "Charge_end_time_slot_6":GEType("select","","setChargeEnd6","","",False,False,False),
        "Charge_start_time_slot_7":GEType("select","","setChargeStart7","","",False,False,False),
        "Charge_end_time_slot_7":GEType("select","","setChargeEnd7","","",False,False,False),
        "Charge_start_time_slot_8":GEType("select","","setChargeStart8","","",False,False,False),
        "Charge_end_time_slot_8":GEType("select","","setChargeEnd8","","",False,False,False),
        "Charge_start_time_slot_9":GEType("select","","setChargeStart9","","",False,False,False),
        "Charge_end_time_slot_9":GEType("select","","setChargeEnd9","","",False,False,False),
        "Charge_start_time_slot_10":GEType("select","","setChargeStart10","","",False,False,False),
        "Charge_end_time_slot_10":GEType("select","","setChargeEnd10","","",False,False,False),

        "Battery_Serial_Number":GEType("sensor","string","","","",False,True,False),
        "Battery_SOC":GEType("sensor","battery","",0,100,False,False,False),
        "Battery_Capacity":GEType("sensor","","",0,250,False,True,False),
        "Battery_Design_Capacity":GEType("sensor","","",0,250,False,True,False),
        "Battery_Remaining_Capacity":GEType("sensor","","",0,250,True,True,False),
        "Battery_Firmware_Version":GEType("sensor","string","",500,5000,False,False,False),
        "Battery_Cells":GEType("sensor","","",0,24,False,True,False),
        "Battery_Cycles":GEType("sensor","","",0,5000,False,True,False),
        "Battery_USB_present":GEType("binary_sensor","","",0,2,True,False,False),
        "Battery_Temperature":GEType("sensor","temperature","",-maxTemp,maxTemp,True,True,False),
        "Battery_Voltage":GEType("sensor","voltage","",0,100,False,True,False),
        "Battery_Cell_1_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_2_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_3_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_4_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_5_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_6_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_7_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_8_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_9_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_10_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_11_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_12_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_13_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_14_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_15_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_16_Voltage":GEType("sensor","voltage","",0,maxCellVoltage,False,True,False),
        "Battery_Cell_1_Temperature":GEType("sensor","temperature","",-maxTemp,maxTemp,True,True,False),
        "Battery_Cell_2_Temperature":GEType("sensor","temperature","",-maxTemp,maxTemp,True,True,False),
        "Battery_Cell_3_Temperature":GEType("sensor","temperature","",-maxTemp,maxTemp,True,True,False),
        "Battery_Cell_4_Temperature":GEType("sensor","temperature","",-maxTemp,maxTemp,True,True,False),
        "Mode":GEType("select","","setBatteryMode","","",False,False,False),
        "Battery_Power_Reserve":GEType("number","","setBatteryReserve",4,100,False,False,False),
        "Battery_Power_Cutoff":GEType("number","","setBatteryCutoff",4,100,False,False,False),
        "Target_SOC":GEType("number","","setChargeTarget",4,100,False,False,False),
        "Charge_Target_SOC_2":GEType("number","","setChargeTarget2",4,100,False,False,False),
        "Charge_Target_SOC_3":GEType("number","","setChargeTarget3",4,100,False,False,False),
        "Charge_Target_SOC_4":GEType("number","","setChargeTarget4",4,100,False,False,False),
        "Charge_Target_SOC_5":GEType("number","","setChargeTarget5",4,100,False,False,False),
        "Charge_Target_SOC_6":GEType("number","","setChargeTarget6",4,100,False,False,False),
        "Charge_Target_SOC_7":GEType("number","","setChargeTarget7",4,100,False,False,False),
        "Charge_Target_SOC_8":GEType("number","","setChargeTarget8",4,100,False,False,False),
        "Charge_Target_SOC_9":GEType("number","","setChargeTarget9",4,100,False,False,False),
        "Charge_Target_SOC_10":GEType("number","","setChargeTarget10",4,100,False,False,False),
        "Discharge_Target_SOC_1":GEType("number","","setDischargeTarget",4,100,False,False,False),
        "Discharge_Target_SOC_2":GEType("number","","setDischargeTarget2",4,100,False,False,False),
        "Discharge_Target_SOC_3":GEType("number","","setDischargeTarget3",4,100,False,False,False),
        "Discharge_Target_SOC_4":GEType("number","","setDischargeTarget4",4,100,False,False,False),
        "Discharge_Target_SOC_5":GEType("number","","setDischargeTarget5",4,100,False,False,False),
        "Discharge_Target_SOC_6":GEType("number","","setDischargeTarget6",4,100,False,False,False),
        "Discharge_Target_SOC_7":GEType("number","","setDischargeTarget7",4,100,False,False,False),
        "Discharge_Target_SOC_8":GEType("number","","setDischargeTarget8",4,100,False,False,False),
        "Discharge_Target_SOC_9":GEType("number","","setDischargeTarget9",4,100,False,False,False),
        "Discharge_Target_SOC_10":GEType("number","","setDischargeTarget10",4,100,False,False,False),
        "Enable_Charge_Schedule":GEType("switch","","enableChargeSchedule","","",False,False,False),
        "Enable_Discharge_Schedule":GEType("switch","","enableDishargeSchedule","","",False,False,False),
        "Enable_Discharge":GEType("switch","","enableDischarge","","",False,False,False),
        "Battery_Charge_Rate":GEType("number","","setChargeRate",0,10000,True,False,False),
        "Battery_Discharge_Rate":GEType("number","","setDischargeRate",0,10000,True,False,False),
        "Night_Start_Energy_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,False,False),
        "Night_Energy_kWh":GEType("sensor","energy","",0,maxTodayEnergy,False,False,False),
        "Night_Cost":GEType("sensor","money","",0,maxCost,True,False,False),
        "Night_Rate":GEType("sensor","money","",0,maxRate,True,False,False),
        "Day_Start_Energy_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,False,False),
        "Day_Energy_kWh":GEType("sensor","energy","",0,maxTodayEnergy,False,False,False),
        "Night_Energy_Total_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,False,False),
        "Day_Energy_Total_kWh":GEType("sensor","energy","",0,maxTotalEnergy,False,False,False),
        "Day_Cost":GEType("sensor","money","",0,maxCost,True,False,False),
        "Day_Rate":GEType("sensor","money","",0,maxRate,True,False,False),
        "Current_Rate":GEType("sensor","money","",0,maxRate,True,False,False),
        "Current_Rate_Type":GEType("select","","switchRate","","",True,False,False),
        "Export_Rate":GEType("sensor","money","",0,maxRate,True,False,False),
        "Import_ppkwh_Today":GEType("sensor","money","",0,maxRate,True,False,False),
        "Battery_Value":GEType("sensor","money","",0,maxCost,True,False,False),
        "Battery_ppkwh":GEType("sensor","money","",0,maxRate,True,False,False),
        "Temp_Pause_Discharge":GEType("select","","tempPauseDischarge","","",True,False,False),
        "Temp_Pause_Charge":GEType("select","","tempPauseCharge","","",True,False,False),
        "Force_Charge":GEType("select","","forceCharge","","",True,False,False),
        "Force_Export":GEType("select","","forceExport","","",True,False,False),
        "Reboot_Invertor":GEType("switch","","rebootInverter","","",False,False,False),
        "Reboot_Addon":GEType("switch","","rebootAddon","","",False,False,False),
        "Discharge_Time_Remaining":GEType("sensor","","",0,1000,True,False,False),
        "Charge_Time_Remaining":GEType("sensor","","",0,1000,True,False,False),
        "Charge_Completion_Time":GEType("sensor","timestamp","","","",False,False,False),
        "Discharge_Completion_Time":GEType("sensor","timestamp","","","",False,False,False),
        "Battery_Power_Mode":GEType("switch","","setBatteryPowerMode","","",False,False,False),
        "Local_control_mode":GEType("select","","setLocalControlMode","","",True,False,False),
        "Battery_pause_mode":GEType("select","","setBatteryPauseMode","","",True,False,False),
        "PV_input_mode":GEType("select","","setPVInputMode","","",True,False,False),
        "Grid_Frequency":GEType("sensor","frequency","",0,60,True,False,False),
        "Inverter_Output_Frequency":GEType("sensor","frequency","",0,60,True,False,False),
        }
    delay_times=["Normal","Running","Cancel","2","15","30","45","60","90","120","150","180"]
    modes=["Eco","Eco (Paused)","Timed Demand","Timed Export","Unknown"]
    rates=["Day","Night"]
    battery_pause_mode=["Disabled","PauseCharge","PauseDischarge","PauseBoth",]
    local_control_mode=["Load","Battery","Grid"]
    pv_input_mode=["Independent","1x2"]

    def create_times(self):
        """Generate timeslot options for time entities"""
        time_slots=[]
        for hh in range(0,23):
            for mm in range (0, 59):
                if len(str(mm))==1:
                    mm="0"+str(mm)
                if len(str(hh))==1:
                    hh="0"+str(hh)
                time_slots.append(str(hh)+":"+str(mm)+":00")
        return time_slots
    def get_time(timestamp: datetime.time):
        """Return inverter safe HH:MM from timestamp"""
        timeslot=timestamp.strftime("%H:%M")
        return timeslot

'''
Firmware Versions for each Model
AC coupled 5xx old, 2xx new. 28x, 29x beta
Gen1 4xx Old, 1xx New. 19x Beta
Gen 2 909+ New. 99x Beta
Gen3 303+ New 39x Beta
AIO 6xx New 69x Beta
'''
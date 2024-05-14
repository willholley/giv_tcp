'''Test Module for GivEVC'''
from pymodbus.client.sync import ModbusTcpClient
import datetime
import time
import pickle
from os.path import exists
import os
from threading import Lock
import json
import read as rd
from settings import GiV_Settings
from GivLUT import GivLUT
import sys

logger = GivLUT.logger
cacheLock = Lock()

class EVCType:
    """Defines type for data objects"""
    def __init__(self,dT,sC,cF):
        self.devType = dT
        self.sensorClass=sC
        self.controlFunc=cF

class EVCLut:
    regcache=GiV_Settings.cache_location+"/evc_regCache.pkl"
    status=[
        'Unknown',
        'Idle',
        'Connected',
        'Starting',
        'Charging',
        'Startup Failure',
        'End of Charging',
        'System Failure',
        'Scheduled',
        'Updating',
        'Unstable CP'
    ]
    cable_status=[
        'Not Connected',
        'Connected',
    ]
    error_codes={
        0:'Clear',
        11:'CP voltage is abnormal',
        12:'Emergency stop',
        13:'Undervoltage',
        14:'Overvoltage',
        15:'Over temperature',
        16:'Meter failure',
        17:'Leakage fault',
        18:'Output short circuit',
        19:'Overcurrent',
        21:'Vehicle response timeout',
        22:'No diode at the vehicle end',
        23:'Relay sticking',
        24:'Leakage current device failure',
        25:'Ground fault',
        26:'Failed to start process',
    }

    evc_lut={
        0: ('Charging_State',status),
        2: ('Connection_Status',cable_status),
        4: ('Error_Code',error_codes),
        6: 'Current_L1',
        8: 'Current_L2',
        10: 'Current_L3',
        13: 'Active_Power',
        17: 'Active_Power_L1',
        20: 'Active_Power_L2',
        24: 'Active_Power_L3',
        29: 'Meter_Energy',
        32: 'Evse_Max_Current',
        34: 'Evse_Min_Current',
        36: 'Charge_Limit',
        72: 'Charge_Session_Energy',
        79: 'Charge_Session_Duration',
        93: 'Plug_and_Go',
        94: ('Charge_Control',GivLUT.charge_control),
        109: 'Voltage_L1',
        111: 'Voltage_L2',
        113: 'Voltage_L3'}

def getEVC():
    regs=[]
    output={}
    multi_output={}
    try:
        client = ModbusTcpClient(GiV_Settings.evc_ip_address)
        client.connect()
        if not client.is_socket_open():
            logger.error("Modbus connection failed, check EVC WiFi/LAN connection")
            return output
        result = client.read_holding_registers(0,60)
        result2 = client.read_holding_registers(60,55)
        client.close()
        regs=result.registers+result2.registers
        for reg in EVCLut.evc_lut.items():
            if isinstance(reg[1],tuple):
                output[reg[1][0]]=reg[1][1][regs[reg[0]]]
            else:
                if 'Current' in str(reg[1]):
                    val=regs[reg[0]]/10
                elif 'Voltage' in str(reg[1]):
                    val=regs[reg[0]]/10
                elif 'Energy' in str(reg[1]):
                    val=regs[reg[0]]/10
                elif 'Limit' in str(reg[1]):
                    val=regs[reg[0]]/10
                else:
                    val=regs[reg[0]]
                output[reg[1]]=val
        SN=''
        for num in regs[38:69]:
            if not num==0:
                SN=SN+chr(num)
        output['Serial_Number']=SN

        if exists(EVCLut.regcache):
            with open(EVCLut.regcache, 'rb') as inp:
                evcRegCache= pickle.load(inp)

            if output['Charge_Session_Energy']==0 and not output['Charging_State']=='Charging':     #If charging has finished, then hold the previous charge session energy
                output['Charge_Session_Energy']=evcRegCache['Charger']['Charge_Session_Energy']
            

            startTime=datetime.datetime.now().replace(hour=regs[74],minute=regs[75],second=regs[76],microsecond=0,tzinfo=datetime.timezone.utc).isoformat()
            endtime=datetime.datetime.now().replace(hour=regs[82],minute=regs[83],second=regs[84],microsecond=0,tzinfo=datetime.timezone.utc).isoformat()
            if startTime==evcRegCache['Charger']['Charge_Start_Time']:
                output['Charge_Start_Time']=evcRegCache['Charger']['Charge_Start_Time']
            else:
                output['Charge_Start_Time']=datetime.datetime.now().replace(hour=regs[74],minute=regs[75],second=regs[76],microsecond=0,tzinfo=datetime.timezone.utc).isoformat()

            if str(endtime)==evcRegCache['Charger']['Charge_End_Time']:
                output['Charge_End_Time']=evcRegCache['Charger']['Charge_End_Time']
            else:
                output['Charge_End_Time']=datetime.datetime.now().replace(hour=regs[82],minute=regs[83],second=regs[84],microsecond=0,tzinfo=datetime.timezone.utc).isoformat()
            
            if not "Import_Cap" in evcRegCache['Charger']:
                output['Import_Cap']=0
            else:
                output['Import_Cap']=evcRegCache['Charger']['Import_Cap']

            if not "Charging_Mode" in evcRegCache['Charger']:
                output['Charging_Mode']="Grid"
            else:
                output['Charging_Mode']=evcRegCache['Charger']['Charging_Mode']

            if not 'Max_Session_Energy' in evcRegCache['Charger']:
                output['Max_Session_Energy']=0
            else:
                output['Max_Session_Energy']=evcRegCache['Charger']['Max_Session_Energy']
        else:
            ts=datetime.datetime.now().replace(hour=regs[82],minute=regs[83],second=regs[84],microsecond=0)
            output['Charge_End_Time']=ts.replace(tzinfo=datetime.timezone.utc).isoformat()
            ts=datetime.datetime.now().replace(hour=regs[74],minute=regs[75],second=regs[76],microsecond=0)
            output['Charge_Start_Time']=ts.replace(tzinfo=datetime.timezone.utc).isoformat()
            output['Import_Cap']=0
            output['Charging_Mode']="Grid"
            output['Max_Session_Energy']=0
        if regs[0]==4:
            output['Charge_Control']='Start'
        else:
            output['Charge_Control']='Stop'
        
        if regs[93]==0:
            output['Plug_and_Go']='enable'
        else:
            output['Plug_and_Go']='disable'

        evcTime=datetime.datetime(regs[97],regs[98],regs[99],regs[100],regs[101],regs[102])
        now=datetime.datetime.utcnow()
        delta=now-evcTime

        #if abs(delta.total_seconds())>90:
        #    # Send system time update to EVC
        #    logger.info("EVC Time is "+ str(delta.total_seconds()) +"s out from local time. Syncing time...")
        #    setDateTime(now)
        #    evcTime=now

        output['System_Time']= evcTime.replace(tzinfo=datetime.timezone.utc).isoformat()

        td=datetime.timedelta(seconds=int(regs[79]))
        output['Charge_Session_Duration']=str(td)
        multi_output['Charger']=output
        # Save new data to Pickle

        with cacheLock:
            with open(EVCLut.regcache, 'wb') as outp:
                pickle.dump(multi_output, outp, pickle.HIGHEST_PROTOCOL)
    except Exception:
        e = sys.exc_info()
        #logger.error("Error: "+ str(e))
    return output

def pubFromPickle():  # Publish last cached EVC Data
    multi_output = {}
    result = "Success"
    if not exists(EVCLut.regcache):  # if there is no cache, create it
        result = "Please get data from Inverter first, either by calling runAll or waiting until the self-run has completed"
    if "Success" in result:
        with cacheLock:
            with open(EVCLut.regcache, 'rb') as inp:
                multi_output = pickle.load(inp)
        SN = multi_output['Charger']['Serial_Number']
        publishOutput(multi_output, SN)
    else:
        multi_output['result'] = result
    return json.dumps(multi_output, indent=4, sort_keys=True, default=str)

def runAll():  # Read from EVC put in cache and publish
    # full_refresh=True
    result=getEVC()
    # Step here to validate data against previous pickle?
    multi_output = pubFromPickle()
    return multi_output

def self_run2():
    while True:
        runAll()
        time.sleep(GiV_Settings.evc_self_run_timer)

# Additional Publish options can be added here.
# A separate file in the folder can be added with a new publish "plugin"
# then referenced here with any settings required added into settings.py
def publishOutput(array, SN):
    tempoutput = {}
    tempoutput = iterate_dict(array)
    if GiV_Settings.MQTT_Output:
        if GiV_Settings.first_run_evc:
            updateFirstRun(SN)              # 09=July=23 - Always do this first irrespective of HA setting.
            if GiV_Settings.HA_Auto_D:        # Home Assistant MQTT Discovery
                logger.critical("Publishing Home Assistant Discovery messages")
                from HA_Discovery import HAMQTT
                HAMQTT.publish_discovery(tempoutput, SN)
            GiV_Settings.first_run_evc = False  
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
### Check if evc or inv and adjust the right line ###
    isSN = False
    script_dir = os.path.dirname(__file__)  # <-- absolute dir the script is in
    rel_path = "settings.py"
    abs_file_path = os.path.join(script_dir, rel_path)
    #check for settings lockfile before
    count=0
    while True:
        logger.debug("Opening settings for first run evc")
        if exists('.settings_lockfile'):
            logger.debug("Waiting for settings to be availble")
            time.sleep(1)
            count=count+1
            if count==50:
                logger.error("Could not access settings file to update EVC Serial Number")
                break
        else:
            logger.debug("Settings available evc")
            #Create setting lockfile
            open(".settings_lockfile",'a').close()

            with open(abs_file_path, "r") as f:
                lines = f.readlines()
            with open(abs_file_path, "w") as f:
                for line in lines:
                    if line.strip("\n") == "    first_run_evc= True":
                        f.write("    first_run_evc= False\n")
                    else:
                        f.write(line)
                    if "serial_number_evc" in line:
                        logger.debug("serial number aready exists: \""+line+"\"")
                        isSN = True

                if not isSN:
                    logger.debug("serial number not in file, adding now")
                    f.writelines("    serial_number_evc = \""+SN+"\"\n")  # only add SN if its not there
            # Delete settings_lockfile
            os.remove('.settings_lockfile')
            logger.debug("removing lockfile")
            break

def iterate_dict(array):        # Create a publish safe version of the output (convert non-string or int datapoints)
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
        elif isinstance(output, float):
            safeoutput[p_load] = round(output, 3)
        else:
            safeoutput[p_load] = output
    return(safeoutput)

def getEVCCache():
    if exists(EVCLut.regcache):
        with open(EVCLut.regcache, 'rb') as inp:
            evcRegCache= pickle.load(inp)
        return json.dumps(evcRegCache)
    else:
        return json.dumps("No EVC data found",indent=4)

def setChargeMode(mode):
    if mode=="enable":
        val=0
    elif mode=="disable":
        val=1
    else:
        logger.error("Invalid control mode called: "+str(mode))
        return
    logger.info("Setting Charge mode to: "+ mode)
    logger.debug("numeric value "+str(val)+ " sent to EVC")
    try:
        client=ModbusTcpClient(GiV_Settings.evc_ip_address)
        client.write_registers(93,val)
    except:
        e=sys.exc_info()
        logger.error("Error controlling EVC: "+str(e))

def setChargeControl(mode):
    if mode in GivLUT.charge_control:
        logger.info("Setting Charge control to: "+ mode)
        val=GivLUT.charge_control.index(mode)
        logger.debug("numeric value "+str(val)+ " sent to EVC")
        try:
            client=ModbusTcpClient(GiV_Settings.evc_ip_address)
            client.write_registers(95,val)
        except:
            e=sys.exc_info()
            logger.error("Error controlling EVC: "+str(e))
    else:
        logger.error("Invalid selection for Charge Control ("+str(mode)+")")

def setCurrentLimit(val):
    #Check limit is between 6 and MAX SAFE LIMIT
    with cacheLock:
        with open(EVCLut.regcache, 'rb') as inp:
            evcRegCache= pickle.load(inp)
    safeMax=int(evcRegCache['Charger']['Evse_Max_Current'])
    safeMin=int(evcRegCache['Charger']['Evse_Min_Current'])
    val=max(val,safeMin)  #Force to 6 if less than
    val=min(val,safeMax) # Get safe MAX value from pkl
    logger.info("Setting Charge current limit to: "+ str(val))
    try:
        client=ModbusTcpClient(GiV_Settings.evc_ip_address)
        client.write_registers(91,(val*10))
    except:
        e=sys.exc_info()
        logger.error("Error controlling EVC: "+str(e))

def test():
    client=ModbusTcpClient(GiV_Settings.evc_ip_address)
    result=client.write_registers(95,2)
    client.close()
    #getEVC()
    print (result)

def chargeMode(once=False):
    while True:
        #Run a regular check and manage load based on current mode and session energy
        if exists(EVCLut.regcache):
            with open(EVCLut.regcache, 'rb') as inp:
                evcRegCache= pickle.load(inp)                
            if evcRegCache['Charger']['Charging_State']=="Charging" or evcRegCache['Charger']['Charging_State']=="Connected":
                if evcRegCache['Charger']['Charging_Mode']=="Hybrid":
                    hybridmode()
                elif evcRegCache['Charger']['Charging_Mode']=="Solar":
                    solarmode()
            if not evcRegCache['Charger']['Max_Session_Energy']==0 and evcRegCache['Charger']['Charge_Session_Energy']>=evcRegCache['Charger']['Max_Session_Energy'] and evcRegCache['Charger']['Charge_Control']=="Start":
                logger.info("Session energy limit reached: "+str(evcRegCache['Charger']['Charge_Session_Energy'])+"kWh stopping charge")
                setChargeControl("Stop")
            if not int(evcRegCache['Charger']['Import_Cap'])==0:
                if exists(GivLUT.regcache):
                    with open(GivLUT.regcache, 'rb') as inp:
                        invRegCache= pickle.load(inp)
                    if float(invRegCache[4]['Power']['Power']['Grid_Current'])>(float(evcRegCache['Charger']['Import_Cap'])*0.95):
                        target=float(evcRegCache['Charger']['Import_Cap'])*0.9
                        reduction=(float(invRegCache[4]['Power']['Power']['Grid_Current']))-target
                        newlimit=int(float(evcRegCache['Charger']['Charge_Limit'])-reduction)
                        if not int(evcRegCache['Charger']['Charge_Limit'])==4:
                            logger.info("Grid import threshold within 5%, reducing EVC charge current to: "+str(newlimit))
                            setCurrentLimit(newlimit)
                        else:
                            logger.info("Grid import threshold within 5%, cannot reduce Charge limit below 6A. Stopping Charge")
                            setChargeControl("Stop")
        if once:
            break
        time.sleep(60)
    

def hybridmode():
    if exists(EVCLut.regcache) and exists(GivLUT.regcache):
        # Set charging current to min 6A plus the level of excess solar
        with open(EVCLut.regcache, 'rb') as inp:
            evcRegCache= pickle.load(inp)
        with open(GivLUT.regcache, 'rb') as inp:
            invRegCache= pickle.load(inp)
        sparePower=invRegCache[4]['Power']['Power']['PV_Power']-invRegCache[4]['Power']['Power']['Load_Power']+evcRegCache['Charger']['Active_Power_L1']
        spareCurrent=int(max((sparePower/invRegCache[4]['Power']['Power']['Grid_Voltage']),0)+6)   #Spare current cannot be negative
        if not spareCurrent==evcRegCache['Charger']['Charge_Limit']:
            logger.info("Topping up min charge with Solar curent ("+str(spareCurrent-6)+"A), setting EVC charge to: "+str(spareCurrent)+"A")
            setCurrentLimit(spareCurrent)

def gridmode():
    # Just don't do anything in Grid Mode and leave charging current as it was
    return

def solarmode():
    # Set charging current to the level of excess solar
    if exists(EVCLut.regcache) and exists(GivLUT.regcache):
        with open(EVCLut.regcache, 'rb') as inp:
            evcRegCache= pickle.load(inp)
        with open(GivLUT.regcache, 'rb') as inp:
            invRegCache= pickle.load(inp)
        sparePower=invRegCache[4]['Power']['Power']['PV_Power']-invRegCache[4]['Power']['Power']['Load_Power']+evcRegCache['Charger']['Active_Power_L1']
        spareCurrent=sparePower/invRegCache[4]['Power']['Power']['Grid_Voltage']
        if sparePower>6:    #only if there's excess above min evse level
            if not spareCurrent==evcRegCache['Charger']['Current_L1']:
                logger.info("Spare Solar curent ("+str(spareCurrent)+"), setting EVC charge to: "+str(spareCurrent)+"A")
                setChargeControl("Start")
                setCurrentLimit(spareCurrent)
        else:
            if not evcRegCache['Charger']['Charge_Control']=="Stop":
                logger.info("Solar excess dropped to below 6A, stopping charge")
                setChargeControl("Stop")

def importcap():
    # Check grid import and ensure its not exceeding threshold
    if exists(EVCLut.regcache) and exists(GivLUT.regcache):
        with open(GivLUT.regcache, 'rb') as inp:
            invRegCache= pickle.load(inp)
        with open(EVCLut.regcache, 'rb') as inp:
            evcRegCache= pickle.load(inp)
        importcurrent=float(invRegCache[4]['Power']['Power']['Grid_Current'])
        evccurrent=float(evcRegCache['Charger']['Current_L1'])
        if importcurrent>GiV_Settings.evc_import_max_current:
            excess=importcurrent-GiV_Settings.evc_import_max_current
            newcurrent=int(max(6,evccurrent-excess))    #newcurrent must be at least 6A
            logger.info("Import current exceeded ("+str(excess)+"), reducing EVC charge to: "+str(newcurrent)+"A")
            setCurrentLimit(newcurrent)


def setMaxSessionEnergy(val):
    if exists(EVCLut.regcache):
        logger.info("Setting Max Session energy to: "+str(val))
        with open(EVCLut.regcache, 'rb') as inp:
            evcRegCache= pickle.load(inp)
        evcRegCache['Charger']['Max_Session_Energy']=val
        with cacheLock:
            with open(EVCLut.regcache, 'wb') as outp:
                pickle.dump(evcRegCache, outp, pickle.HIGHEST_PROTOCOL)


def setImportCap(val):
    if exists(EVCLut.regcache):
        logger.info("Setting Import Cap to: "+str(val))
        with open(EVCLut.regcache, 'rb') as inp:
            evcRegCache= pickle.load(inp)
        evcRegCache['Charger']['Import_Cap']=val
        with cacheLock:
            with open(EVCLut.regcache, 'wb') as outp:
                pickle.dump(evcRegCache, outp, pickle.HIGHEST_PROTOCOL)

def setChargingMode(mode):
    if mode in GivLUT.charging_mode:
        if exists(EVCLut.regcache):
            logger.info("Setting Charging Mode to: "+str(mode))
            with open(EVCLut.regcache, 'rb') as inp:
                evcRegCache= pickle.load(inp)
            evcRegCache['Charger']['Charging_Mode']=mode
            with cacheLock:
                with open(EVCLut.regcache, 'wb') as outp:
                    pickle.dump(evcRegCache, outp, pickle.HIGHEST_PROTOCOL)
            chargeMode(True)    # Run an initial call when changing modes
    else:
        logger.error("Invalid selection for Charge Mode ("+str(mode)+")")

def setDateTime(sysTime):
    temp={}
    try:
        if not isinstance(sysTime,datetime.datetime):
            sysTime=datetime.strptime(sysTime,"%d/%m/%Y %H:%M:%S")   #format '12/11/2021 09:15:32'
        logger.info("Setting EVC time to: "+sysTime.isoformat())
        #Set Date and Time on inverter
        try:
            client=ModbusTcpClient(GiV_Settings.evc_ip_address)
            res=client.write_registers(97,2023)
            res=client.write_registers(100,5)
            #client.write_registers(99,11)
            #client.write_registers(100,21)
            #client.write_registers(101,5)
            #client.write_registers(102,35)
            logger.info("Time Set")
        except:
            e=sys.exc_info()
            logger.error("Error Setting EVC Time: "+str(e))
    except:
        e = sys.exc_info()
        temp['result']="Setting inverter DateTime failed: " + str(e) 
        logger.error (temp['result'])
    return json.dumps(temp)

if __name__ == '__main__':
    if len(sys.argv) == 2:
        globals()[sys.argv[1]]()
    elif len(sys.argv) == 3:
        globals()[sys.argv[1]](sys.argv[2])
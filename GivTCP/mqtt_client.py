import paho.mqtt.client as mqtt
import time, sys, importlib, time
import os
from os.path import exists
from settings import GiV_Settings
import write as wr
import evc as evc
import pickle, settings
from GivLUT import GivLUT
from pickletools import read_uint1

sys.path.append(GiV_Settings.default_path)

logger = GivLUT.logger

if GiV_Settings.MQTT_Port=='':
    MQTT_Port=1883
else:
    MQTT_Port=int(GiV_Settings.MQTT_Port)
MQTT_Address=GiV_Settings.MQTT_Address
if GiV_Settings.MQTT_Username=='':
    MQTTCredentials=False
else:
    MQTTCredentials=True
    MQTT_Username=GiV_Settings.MQTT_Username
    MQTT_Password=GiV_Settings.MQTT_Password
if GiV_Settings.MQTT_Topic=='':
    MQTT_Topic='GivEnergy'
else:
    MQTT_Topic=GiV_Settings.MQTT_Topic

def isfloat(num):
    try:
        float(num)
        return True
    except ValueError:
        return False

def on_message(client, userdata, message):
    payload={}
    logger.debug("MQTT Message Recieved: "+str(message.topic)+"= "+str(message.payload.decode("utf-8")))
    writecommand={}
    try:
        command=str(message.topic).split("/")[-1]
        if command=="setDischargeRate":
            writecommand['dischargeRate']=str(message.payload.decode("utf-8"))
            wr.setDischargeRate(writecommand)
        elif command=="setChargeRate":
            writecommand['chargeRate']=str(message.payload.decode("utf-8"))
            wr.setChargeRate(writecommand)
        elif command=="setDischargeRateAC":
            writecommand['dischargeRate']=str(message.payload.decode("utf-8"))
            wr.setDischargeRateAC(writecommand)
        elif command=="setChargeRateAC":
            writecommand['chargeRate']=str(message.payload.decode("utf-8"))
            wr.setChargeRateAC(writecommand)
        elif command=="rebootInverter":
            wr.rebootinverter()
        elif command=="rebootAddon":
            wr.rebootAddon()
        elif command=="setActivePowerRate":
            writecommand['activePowerRate']=str(message.payload.decode("utf-8"))
            wr.setActivePowerRate(writecommand)
        elif command=="enableChargeTarget":
            writecommand['state']=str(message.payload.decode("utf-8"))
            wr.enableChargeTarget(writecommand)
        elif command=="enableChargeSchedule":
            writecommand['state']=str(message.payload.decode("utf-8"))
            wr.enableChargeSchedule(writecommand)
        elif command=="enableDishargeSchedule":
            writecommand['state']=str(message.payload.decode("utf-8"))
            wr.enableDischargeSchedule(writecommand)
        elif command=="setBatteryPowerMode":
            writecommand['state']=str(message.payload.decode("utf-8"))
            wr.setBatteryPowerMode(writecommand)
        elif command=="setBatteryPauseMode":
            writecommand['state']=str(message.payload.decode("utf-8"))
            wr.setBatteryPauseMode(writecommand)
        elif command=="setLocalControlMode":
            writecommand['state']=str(message.payload.decode("utf-8"))
            wr.setLocalControlMode(writecommand)
        elif command=="setPVInputMode":
            writecommand['state']=str(message.payload.decode("utf-8"))
            wr.setPVInputMode(writecommand)
        elif command=="setCarChargeBoost":
            writecommand['state']=str(message.payload.decode("utf-8"))
            wr.setCarChargeBoost(writecommand)
        elif command=="setBatteryCalibration":
            writecommand['state']=str(message.payload.decode("utf-8"))
            wr.setBatteryCalibration(writecommand)
        elif command=="setExportLimit":
            writecommand['state']=str(message.payload.decode("utf-8"))
            wr.setExportLimit(writecommand)
        elif command=="enableDischarge":
            writecommand['state']=str(message.payload.decode("utf-8"))
            wr.enableDischarge(writecommand)
        elif command=="setChargeTarget":
            writecommand['chargeToPercent']=str(message.payload.decode("utf-8"))
            wr.setChargeTarget(writecommand)
        elif command=="setChargeTarget1":
            writecommand['chargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=1
            wr.setChargeTarget2(writecommand)
        elif command=="setChargeTarget2":
            writecommand['chargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=2
            wr.setChargeTarget2(writecommand)
        elif command=="setChargeTarget3":
            writecommand['chargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=3
            wr.setChargeTarget2(writecommand)
        elif command=="setChargeTarget4":
            writecommand['chargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=4
            wr.setChargeTarget2(writecommand)
        elif command=="setChargeTarget5":
            writecommand['chargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=5
            wr.setChargeTarget2(writecommand)
        elif command=="setChargeTarget6":
            writecommand['chargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=6
            wr.setChargeTarget2(writecommand)
        elif command=="setChargeTarget7":
            writecommand['chargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=7
            wr.setChargeTarget2(writecommand)
        elif command=="setChargeTarget8":
            writecommand['chargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=8
            wr.setChargeTarget2(writecommand)
        elif command=="setChargeTarget9":
            writecommand['chargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=9
            wr.setChargeTarget2(writecommand)
        elif command=="setChargeTarget10":
            writecommand['chargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=10
            wr.setChargeTarget2(writecommand)
        elif command=="setBatteryReserve":
            writecommand['reservePercent']=str(message.payload.decode("utf-8"))
            wr.setBatteryReserve(writecommand)
        elif command=="setBatteryCutoff":
            writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
            wr.setBatteryCutoff(writecommand)
        elif command=="setBatteryMode":
            writecommand['mode']=str(message.payload.decode("utf-8"))
            wr.setBatteryMode(writecommand)
        elif command=="setDateTime":
            writecommand['dateTime']=str(message.payload.decode("utf-8"))
            wr.setDateTime(writecommand)
        elif command=="setShallowCharge":
            writecommand['val']=str(message.payload.decode("utf-8"))
            wr.setShallowCharge(writecommand)
        elif command=="setChargeStart1":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=1
            wr.setChargeSlotStart(payload)
        elif command=="setChargeEnd1":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=1
            wr.setChargeSlotEnd(payload)
        elif command=="setChargeStart2":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=2
            wr.setChargeSlotStart(payload)
        elif command=="setChargeEnd2":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=2
            wr.setChargeSlotEnd(payload)
        elif command=="setChargeStart3":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=3
            wr.setChargeSlotStart(payload)
        elif command=="setChargeEnd3":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=3
            wr.setChargeSlotEnd(payload)
        elif command=="setChargeStart4":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=4
            wr.setChargeSlotStart(payload)
        elif command=="setChargeEnd4":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=4
            wr.setChargeSlotEnd(payload)
        elif command=="setChargeStart5":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=5
            wr.setChargeSlotStart(payload)
        elif command=="setChargeEnd5":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=5
            wr.setChargeSlotEnd(payload)
        elif command=="setChargeStart6":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=6
            wr.setChargeSlotStart(payload)
        elif command=="setChargeEnd6":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=6
            wr.setChargeSlotEnd(payload)
        elif command=="setChargeStart7":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=7
            wr.setChargeSlotStart(payload)
        elif command=="setChargeEnd7":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=7
            wr.setChargeSlotEnd(payload)
        elif command=="setChargeStart8":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=8
            wr.setChargeSlotStart(payload)
        elif command=="setChargeEnd8":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=8
            wr.setChargeSlotEnd(payload)
        elif command=="setChargeStart9":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=9
            wr.setChargeSlotStart(payload)
        elif command=="setChargeEnd9":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=9
            wr.setChargeSlotEnd(payload)
        elif command=="setChargeStart10":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=10
            wr.setChargeSlotStart(payload)
        elif command=="setChargeEnd10":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=10
            wr.setChargeSlotEnd(payload)

        elif command=="setEMSChargeStart1":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=1
            payload['EMS']=True
            wr.setChargeSlotStart(payload)
        elif command=="setEMSChargeEnd1":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=1
            payload['EMS']=True
            wr.setChargeSlotEnd(payload)
        elif command=="setEMSChargeStart2":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=2
            payload['EMS']=True
            wr.setChargeSlotStart(payload)
        elif command=="setEMSChargeEnd2":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=2
            payload['EMS']=True
            wr.setChargeSlotEnd(payload)
        elif command=="setEMSChargeStart3":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=3
            payload['EMS']=True
            wr.setChargeSlotStart(payload)
        elif command=="setEMSChargeEnd3":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=3
            payload['EMS']=True
            wr.setChargeSlotEnd(payload)

        elif command=="setDischargeStart1":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=1
            wr.setDischargeSlotStart(payload)
        elif command=="setDischargeEnd1":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=1
            wr.setDischargeSlotEnd(payload)
        elif command=="setDischargeStart2":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=2
            wr.setDischargeSlotStart(payload)
        elif command=="setDischargeEnd2":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=2
            wr.setDischargeSlotEnd(payload)
        elif command=="setDischargeStart3":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=3
            wr.setDischargeSlotStart(payload)
        elif command=="setDischargeEnd3":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=3
            wr.setDischargeSlotEnd(payload)
        elif command=="setDischargeStart4":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=4
            wr.setDischargeSlotStart(payload)
        elif command=="setDischargeEnd4":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=4
            wr.setDischargeSlotEnd(payload)
        elif command=="setDischargeStart5":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=5
            wr.setDischargeSlotStart(payload)
        elif command=="setDischargeEnd5":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=5
            wr.setDischargeSlotEnd(payload)
        elif command=="setDischargeStart6":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=6
            wr.setDischargeSlotStart(payload)
        elif command=="setDischargeEnd6":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=6
            wr.setDischargeSlotEnd(payload)
        elif command=="setDischargeStart7":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=7
            wr.setDischargeSlotStart(payload)
        elif command=="setDischargeEnd7":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=7
            wr.setDischargeSlotEnd(payload)
        elif command=="setDischargeStart8":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=8
            wr.setDischargeSlotStart(payload)
        elif command=="setDischargeEnd8":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=8
            wr.setDischargeSlotEnd(payload)
        elif command=="setDischargeStart9":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=9
            wr.setDischargeSlotStart(payload)
        elif command=="setDischargeEnd9":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=9
            wr.setDischargeSlotEnd(payload)
        elif command=="setDischargeStart10":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=10
            wr.setDischargeSlotStart(payload)
        elif command=="setDischargeEnd10":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=10
            wr.setDischargeSlotEnd(payload)
        elif command=="setEMSDischargeStart1":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=1
            payload['EMS']=True
            wr.setDischargeSlotStart(payload)
        elif command=="setEMSDischargeEnd1":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=1
            payload['EMS']=True
            wr.setDischargeSlotEnd(payload)
        elif command=="setEMSDischargeStart2":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=2
            payload['EMS']=True
            wr.setDischargeSlotStart(payload)
        elif command=="setEMSDischargeEnd2":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=2
            payload['EMS']=True
            wr.setDischargeSlotEnd(payload)
        elif command=="setEMSDischargeStart3":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=3
            payload['EMS']=True
            wr.setDischargeSlotStart(payload)
        elif command=="setEMSDischargeEnd3":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=3
            payload['EMS']=True
            wr.setDischargeSlotEnd(payload)
        elif command=="setExportStart1":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=1
            wr.setExportSlotStart(payload)
        elif command=="setExportEnd1":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=1
            wr.setExportSlotEnd(payload)
        elif command=="setExportStart2":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=2
            wr.setExportSlotStart(payload)
        elif command=="setExportEnd2":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=2
            wr.setExportSlotEnd(payload)
        elif command=="setExportStart3":
            payload['start']=message.payload.decode("utf-8")[:5]
            payload['slot']=3
            wr.setExportSlotStart(payload)
        elif command=="setExportEnd3":
            payload['finish']=message.payload.decode("utf-8")[:5]
            payload['slot']=3
            wr.setExportSlotEnd(payload)
        elif command=="setExportTarget1":
            writecommand['exportToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=1
            wr.setExportTarget(writecommand)
        elif command=="setExportTarget2":
            writecommand['exportToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=2
            wr.setExportTarget(writecommand)
        elif command=="setExportTarget3":
            writecommand['exportToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=3
        elif command=="setDischargeTarget1":
            writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=1
            wr.setDischargeTarget(writecommand)
        elif command=="setDischargeTarget2":
            writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=2
            wr.setDischargeTarget(writecommand)
        elif command=="setDischargeTarget3":
            writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=3
            wr.setExportTarget(writecommand)
        elif command=="setDischargeTarget4":
            writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=4
            wr.setDischargeTarget(writecommand)
        elif command=="setDischargeTarget5":
            writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=5
            wr.setDischargeTarget(writecommand)
        elif command=="setDischargeTarget6":
            writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=6
            wr.setDischargeTarget(writecommand)
        elif command=="setDischargeTarget7":
            writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=7
            wr.setDischargeTarget(writecommand)
        elif command=="setDischargeTarget8":
            writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=8
            wr.setDischargeTarget(writecommand)
        elif command=="setDischargeTarget9":
            writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=9
            wr.setDischargeTarget(writecommand)
        elif command=="setDischargeTarget10":
            writecommand['dischargeToPercent']=str(message.payload.decode("utf-8"))
            writecommand['slot']=10
            wr.setDischargeTarget(writecommand)
        elif command=="setPauseStart":
            payload['start']=message.payload.decode("utf-8")[:5]
            wr.setPauseStart(payload)
        elif command=="setPauseEnd":
            payload['finish']=message.payload.decode("utf-8")[:5]
            wr.setPauseEnd(payload)
        elif command=="tempPauseDischarge":
            if message.payload.decode("utf-8") == "Cancel" or message.payload.decode("utf-8") == "Normal" or float(message.payload.decode("utf-8"))==0:
                # Get the Job ID from the touchfile
                if exists(".tpdRunning"):
                    jobid= str(open(".tpdRunning","r").readline().strip('\n'))
                    logger.info("Retrieved jobID to cancel Temp Pause Discharge: "+ str(jobid))
                    result=wr.cancelJob(jobid)
                else:
                    logger.error("Temp Pause Charge is not currently running")
            elif isfloat(message.payload.decode("utf-8")):
                writecommand=float(message.payload.decode("utf-8"))
                wr.tempPauseDischarge(writecommand)
        elif command=="tempPauseCharge":
            if message.payload.decode("utf-8") == "Cancel" or message.payload.decode("utf-8") == "Normal" or float(message.payload.decode("utf-8"))==0:
                # Get the Job ID from the touchfile
                if exists(".tpcRunning"):
                    jobid= str(open(".tpcRunning","r").readline().strip('\n'))
                    logger.info("Retrieved jobID to cancel Temp Pause Charge: "+ str(jobid))
                    result=wr.cancelJob(jobid)
                else:
                    logger.error("Temp Pause Charge is not currently running")
            elif isfloat(message.payload.decode("utf-8")):
                writecommand=float(message.payload.decode("utf-8"))
                wr.tempPauseCharge(writecommand)
        elif command=="forceCharge":
            if message.payload.decode("utf-8") == "Cancel" or message.payload.decode("utf-8") == "Normal" or float(message.payload.decode("utf-8"))==0:
                # Get the Job ID from the touchfile
                if exists(".FCRunning"):
                    jobid= str(open(".FCRunning","r").readline().strip('\n'))
                    logger.info("Retrieved jobID to cancel Force Charge: "+ str(jobid))
                    result=wr.cancelJob(jobid)
                else:
                    logger.error("Force Charge is not currently running")
            elif isfloat(message.payload.decode("utf-8")):
                writecommand=float(message.payload.decode("utf-8"))
                wr.forceCharge(writecommand)
        elif command=="forceExport":
            if message.payload.decode("utf-8") == "Cancel" or message.payload.decode("utf-8") == "Normal" or float(message.payload.decode("utf-8"))==0:
                # Get the Job ID from the touchfile
                if exists(".FERunning"):
                    jobid= str(open(".FERunning","r").readline().strip('\n'))
                    logger.info("Retrieved jobID to cancel Force Export: "+ str(jobid))
                    result=wr.cancelJob(jobid)
                else:
                    logger.error("Force Export is not currently running")
            elif isfloat(message.payload.decode("utf-8")):
                writecommand=float(message.payload.decode("utf-8"))
                wr.forceExport(writecommand)
        elif command=="switchRate":
            writecommand=message.payload.decode("utf-8")
            wr.switchRate(writecommand)
        elif command=="chargeMode":
            writecommand=message.payload.decode("utf-8")
            evc.setChargeMode(writecommand)
        elif command=="controlCharge":
            writecommand=message.payload.decode("utf-8")
            evc.setChargeControl(writecommand)
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        logger.error("MQTT.OnMessage Exception: "+str(e))
        return
    
    #Do something with the result??

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code==0:
        client.connected_flag=True #set flag
        logger.debug("connected OK Returned code="+str(reason_code))
        #Subscribe to the control topic for this inverter - relies on serial_number being present
        client.subscribe(MQTT_Topic+"/control/"+GiV_Settings.serial_number+"/#")
        logger.debug("Subscribing to "+MQTT_Topic+"/control/"+GiV_Settings.serial_number+"/#")
    else:
        logger.error("Bad connection Returned code= "+str(reason_code))

logger.critical("Connecting to MQTT broker for control- "+str(GiV_Settings.MQTT_Address))
#loop till serial number has been found
count=0          # 09-July-2023  set start point

while not hasattr(GiV_Settings,'serial_number'):
    time.sleep(5)
    #del sys.modules['settings.GiV_Settings']
    importlib.reload(settings)
    from settings import GiV_Settings
    count=count + 1      # 09-July-2023  previous +1 only simply reset value to 1 so loop was infinite
    if count==50:
        logger.error("No serial_number found in MQTT queue. MQTT Control not available. Double check logs for connection errors and restart GivTCP or ensure correct AIO/firmware settings")
        exit
if hasattr(GiV_Settings,'serial_number'):
    logger.debug("Serial Number retrieved: "+GiV_Settings.serial_number)

    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "GivEnergy_GivTCP_"+str(GiV_Settings.givtcp_instance)+"_Control")
    mqtt.Client.connected_flag=False        			#create flag in class
    if MQTTCredentials:
        client.username_pw_set(MQTT_Username,MQTT_Password)
    client.on_connect=on_connect     			        #bind call back function
    client.on_message=on_message                        #bind call back function
    #client.loop_start()

    logger.debug ("Connecting to broker(sub): "+ MQTT_Address)
    client.connect(MQTT_Address,port=MQTT_Port)
    client.loop_forever()

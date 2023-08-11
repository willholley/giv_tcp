# version 2022.01.21
"""Module for generating HA auto discovery messages"""
import sys
import time
import json
import pickle
import paho.mqtt.client as mqtt
from mqtt import GivMQTT
from giv_lut import GivLUT
from os.path import exists
from settings import GivSettings

logger=GivLUT.logger

class HAMQTT():
    """Class for generating HA auto discovery messages"""
    if GivSettings.MQTT_Port=='':
        MQTT_Port=1883
    else:
        MQTT_Port=int(GivSettings.MQTT_Port)
    MQTT_Address=GivSettings.MQTT_Address
    if GivSettings.MQTT_Username=='':
        MQTTCredentials=False
    else:
        MQTTCredentials=True
        MQTT_Username=GivSettings.MQTT_Username
        MQTT_Password=GivSettings.MQTT_Password
    if GivSettings.MQTT_Topic=="":
        GivSettings.MQTT_Topic="GivEnergy"

    def get_inv_bat_max():
        """Gets inverter max rate from cache"""
        if exists(GivLUT.regcache):      # if there is a cache then grab it
            with open(GivLUT.regcache, 'rb') as inp:
                regCacheStack = pickle.load(inp)
                multi_output_old = regCacheStack[4]
            return int(multi_output_old['Invertor_Details']['Invertor_Max_Bat_Rate'])
        return 5000

    def on_connect(client, userdata, flags, rc):
        """Handles mqtt connection"""
        if rc==0:
            client.connected_flag=True #set flag
            logger.debug("connected OK Returned code="+str(rc))
            #client.subscribe(topic)
        else:
            logger.error("Bad connection Returned code= "+str(rc))

    def publish_discovery(array,serial_number):
        """Recieve multiple payloads with Topics and publish in a single MQTT connection"""
        mqtt.Client.connected_flag=False        			#create flag in class
        client=mqtt.Client("GivEnergy_GivTCP_"+str(GivSettings.givtcp_instance))
        root_topic=str(GivSettings.MQTT_Topic+"/"+serial_number+"/")
        if HAMQTT.MQTTCredentials:
            client.username_pw_set(HAMQTT.MQTT_Username,HAMQTT.MQTT_Password)
        try:
            client.on_connect=HAMQTT.on_connect     			#bind call back function
            client.loop_start()
            logger.debug("Connecting to broker: "+ HAMQTT.MQTT_Address)
            client.connect(HAMQTT.MQTT_Address,port=HAMQTT.MQTT_Port)
            while not client.connected_flag:        			#wait in loop
                logger.debug("In wait loop")
                time.sleep(0.2)

            logger.debug("Publishing MQTT: " + HAMQTT.MQTT_Address)

            ##publish the status message
            client.publish(GivSettings.MQTT_Topic+"/"+serial_number+"/status","online", retain=True)

            ### For each topic create a discovery message
            for p_load in array:
                if p_load != "raw":
                    payload=array[p_load]
                    logger.debug('Publishing: '+root_topic+p_load)
                    output=GivMQTT.iterate_dict(payload,root_topic+p_load)   #create LUT for MQTT publishing
                    for topic in output:
                        #Determine Entitiy type (switch/sensor/number) and publish the right message
                        if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].devType=="sensor":
                            if "Battery_Details" in topic:
                                client.publish("homeassistant/sensor/GivEnergy/"+str(topic).split("/")[-2]+"_"+str(topic).rsplit('/', maxsplit=1)[-1]+"/config",HAMQTT.create_device_payload(topic,serial_number),retain=True)
                            else:
                                client.publish("homeassistant/sensor/GivEnergy/"+serial_number+"_"+str(topic).rsplit('/', maxsplit=1)[-1]+"/config",HAMQTT.create_device_payload(topic,serial_number),retain=True)
                        elif GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].devType=="switch":
                            client.publish("homeassistant/switch/GivEnergy/"+serial_number+"_"+str(topic).rsplit('/', maxsplit=1)[-1]+"/config",HAMQTT.create_device_payload(topic,serial_number),retain=True)
                        elif GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].devType=="number":
                            client.publish("homeassistant/number/GivEnergy/"+serial_number+"_"+str(topic).rsplit('/', maxsplit=1)[-1]+"/config",HAMQTT.create_device_payload(topic,serial_number),retain=True)
                    #    elif GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]][0]=="binary_sensor":
                    #        client.publish("homeassistant2/binary_sensor/GivEnergy/"+str(topic).rsplit('/', maxsplit=1)[-1]+"/config",HAMQTT.create_binary_sensor_payload(topic,serial_number),retain=True)
                        elif GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].devType=="select":
                            client.publish("homeassistant/select/GivEnergy/"+serial_number+"_"+str(topic).rsplit('/', maxsplit=1)[-1]+"/config",HAMQTT.create_device_payload(topic,serial_number),retain=True)
            client.loop_stop()                      			#Stop loop
            client.disconnect()
        except Exception:
            e = sys.exc_info()
            logger.error("Error connecting to MQTT Broker: " + str(e))
        return

    def create_device_payload(self,topic,serial_number):
        """Creates device payload for HA auto discovery method"""
        temp_obj={}
        temp_obj['stat_t']=str(topic).replace(" ","_")
        temp_obj['avty_t'] = GivSettings.MQTT_Topic+"/"+serial_number+"/status"
        temp_obj["pl_avail"]= "online"
        temp_obj["pl_not_avail"]= "offline"
        temp_obj['device']={}
        givtcp_device=str(topic).split("/")[2]
        if "Battery_Details" in topic:
            temp_obj["name"]=GivSettings.ha_device_prefix+" "+str(topic).split("/")[3].replace("_"," ")+" "+str(topic).rsplit('/', maxsplit=1)[-1].replace("_"," ") #Just final bit past the last "/"
            temp_obj['uniq_id']=GivSettings.ha_device_prefix+"_"+str(topic).split("/")[3]+"_"+str(topic).rsplit('/', maxsplit=1)[-1]
            temp_obj['object_id']=GivSettings.ha_device_prefix+"_"+str(topic).split("/")[3]+"_"+str(topic).rsplit('/', maxsplit=1)[-1]
            temp_obj['device']['identifiers']=str(topic).split("/")[3]+"_"+givtcp_device
            temp_obj['device']['name']=GivSettings.ha_device_prefix+" "+str(topic).split("/")[3].replace("_"," ")+" "+givtcp_device.replace("_"," ")
        else:
            temp_obj['uniq_id']=GivSettings.ha_device_prefix+"_"+serial_number+"_"+str(topic).rsplit('/', maxsplit=1)[-1]
            temp_obj['object_id']=GivSettings.ha_device_prefix+"_"+serial_number+"_"+str(topic).rsplit('/', maxsplit=1)[-1]
            temp_obj['device']['identifiers']=serial_number+"_"+givtcp_device
            temp_obj['device']['name']=GivSettings.ha_device_prefix+" "+serial_number+" "+str(givtcp_device).replace("_"," ")
            temp_obj["name"]=GivSettings.ha_device_prefix+" "+str(topic).rsplit('/', maxsplit=1)[-1].replace("_"," ") #Just final bit past the last "/"
        temp_obj['device']['manufacturer']="GivEnergy"

        if not GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].controlFunc == "":
            temp_obj['command_topic']=GivSettings.MQTT_Topic+"/control/"+serial_number+"/"+GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].controlFunc

#set device specific elements here:
        if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].devType=="sensor":
            temp_obj['unit_of_meas']=""
            if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].sensorClass=="energy":
                temp_obj['unit_of_meas']="kWh"
                temp_obj['device_class']="Energy"
                if "soc" in str(topic.split("/")[-2]).lower():
                    temp_obj['state_class']="measurement"
                else:
                    temp_obj['state_class']="total_increasing"
            if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].sensorClass=="money":
                if "ppkwh" in str(topic).lower() or "rate" in str(topic).lower():
                    temp_obj['unit_of_meas']="{GBP}/kWh"
                else:
                    temp_obj['unit_of_meas']="{GBP}"
                temp_obj['device_class']="Monetary"
                temp_obj['icon_template']= "mdi:currency-gbp"
            if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].sensorClass=="power":
                temp_obj['unit_of_meas']="W"
                temp_obj['device_class']="Power"
                temp_obj['state_class']="measurement"
            if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].sensorClass=="temperature":
                temp_obj['unit_of_meas']="°C"
                temp_obj['device_class']="Temperature"
                temp_obj['state_class']="measurement"
            if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].sensorClass=="voltage":
                temp_obj['unit_of_meas']="V"
                temp_obj['device_class']="Voltage"
                temp_obj['state_class']="measurement"
            if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].sensorClass=="frequency":
                temp_obj['unit_of_meas']="Hz"
                temp_obj['device_class']="frequency"
                temp_obj['state_class']="measurement"
            if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].sensorClass=="current":
                temp_obj['unit_of_meas']="A"
                temp_obj['device_class']="Current"
                temp_obj['state_class']="measurement"
            if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].sensorClass=="battery":
                temp_obj['unit_of_meas']="%"
                temp_obj['device_class']="Battery"
                temp_obj['state_class']="measurement"
            if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].sensorClass=="timestamp":
                del(temp_obj['unit_of_meas'])
                temp_obj['device_class']="timestamp"
            if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].sensorClass=="datetime":
                del(temp_obj['unit_of_meas'])
            if GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].sensorClass=="string":
                del(temp_obj['unit_of_meas'])
        elif GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].devType=="switch":
            temp_obj['payload_on']="enable"
            temp_obj['payload_off']="disable"
    #    elif GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1].devType=="binary_sensor":
    #        client.publish("homeassistant/binary_sensor/GivEnergy/"+str(topic).rsplit('/', maxsplit=1)[-1]+"/config",HAMQTT.create_binary_sensor_payload(topic,serial_number),retain=True)
        elif GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].devType=="select":
            item=str(topic).rsplit('/', maxsplit=1)[-1]
            if item == "Battery_pause_mode":
                options=GivLUT.battery_pause_mode
            elif item == "Local_control_mode":
                options=GivLUT.local_control_mode
            elif item == "PV_input_mode":
                options=GivLUT.pv_input_mode
            elif "Mode" in item:
                options=GivLUT.modes
            elif "slot" in item:
                options=GivLUT.time_slots
            elif "Temp" in item:
                options=GivLUT.delay_times
            elif "Force" in item:
                options=GivLUT.delay_times
            elif "Rate" in item:
                options=GivLUT.rates
            temp_obj['options']=options
        elif GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].devType=="number":
            # If its a rate then change to Watts
            if "SOC" in str(topic).lower():
                temp_obj['unit_of_meas']="%"
            elif "charge" in str(topic).lower():
                temp_obj['unit_of_meas']="W"
                temp_obj['min']=0
                temp_obj['max']=HAMQTT.get_inv_bat_max()
                temp_obj['mode']="slider"
            else:
                temp_obj['unit_of_meas']="%"
        elif GivLUT.entity_type[str(topic).rsplit('/', maxsplit=1)[-1]].devType=="button":
            temp_obj['device_class']="restart"
            temp_obj['payload_press']="restart"
        ## Convert this object to json string
        return json.dumps(temp_obj)

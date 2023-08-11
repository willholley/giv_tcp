# version 2022.01.21
"""MQTT Class to publish inverter data"""
import sys
import time
from giv_lut import GivLUT
from settings import GivSettings
import paho.mqtt.client as mqtt

logger = GivLUT.logger

class GivMQTT():
    """MQTT Class to publish inverter data"""

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

    def on_connect(self,client, userdata, flags, rc):
        """MQTT on_connect overload"""
        if rc==0:
            client.connected_flag=True #set flag
            logger.debug("connected OK Returned code="+str(rc))
            #client.subscribe(topic)
        else:
            logger.error("Bad connection Returned code= "+str(rc))

    def single_mqtt_publish(topic,value):
        """Recieve multiple payloads with Topics and publish in a single MQTT connection"""
        mqtt.Client.connected_flag=False        			#create flag in class
        client=mqtt.Client("GivEnergy_GivTCP_"+str(GivSettings.givtcp_instance))

        if GivMQTT.MQTTCredentials:
            client.username_pw_set(GivMQTT.MQTT_Username,GivMQTT.MQTT_Password)
        try:
            client.on_connect=GivMQTT.on_connect     			#bind call back function
            client.loop_start()
            logger.debug ("Connecting to broker: "+ GivMQTT.MQTT_Address)
            client.connect(GivMQTT.MQTT_Address,port=GivMQTT.MQTT_Port)
            while not client.connected_flag:        			#wait in loop
                logger.debug ("In wait loop")
                time.sleep(0.2)
            client.publish(topic,value)
        except Exception:
            error = sys.exc_info()
            logger.error("Error connecting to MQTT Broker: " + str(error))
        client.loop_stop()                      			    #Stop loop
        client.disconnect()
        return client

    def multi_mqtt_publish(self,root_topic,array):
        """Recieve multiple payloads with Topics and publish in a single MQTT connection"""
        mqtt.Client.connected_flag=False        			    #create flag in class
        client=mqtt.Client("GivEnergy_GivTCP_"+str(GivSettings.givtcp_instance))
        ##Check if first run then publish auto discovery message
        if GivMQTT.MQTTCredentials:
            client.username_pw_set(GivMQTT.MQTT_Username,GivMQTT.MQTT_Password)
        try:
            client.on_connect=GivMQTT.on_connect     			#bind call back function
            client.loop_start()
            logger.debug ("Connecting to broker: "+ GivMQTT.MQTT_Address)
            client.connect(GivMQTT.MQTT_Address,port=GivMQTT.MQTT_Port)
            while not client.connected_flag:        			#wait in loop
                logger.debug ("In wait loop")
                time.sleep(0.2)
            for p_load in array:
                payload=array[p_load]
                logger.debug('Publishing: '+root_topic+p_load)
                output=GivMQTT.iterate_dict(payload,root_topic+p_load)   #create LUT for MQTT publishing
                for value in output.items():
                    if isinstance(output[value],(int, str, float, bytearray)):      #Only publish typesafe data
                        client.publish(value,output[value])
                    else:
                        logger.error("MQTT error trying to send a "+ str(type(output[value]))+" to the MQTT broker for: "+str(value))
        except Exception:
            error = sys.exc_info()
            logger.error("Error connecting to MQTT Broker: " + str(error))
        client.loop_stop()                      			    #Stop loop
        client.disconnect()
        return client

    def iterate_dict(array,topic):
        """Iterate through a dict to Create LUT of topics and datapoints"""
        mqtt_lut={}
        if isinstance(array, dict):
            # Create a publish safe version of the output
            for p_load in array:
                output=array[p_load]
                if isinstance(output, dict):
                    mqtt_lut.update(GivMQTT.iterate_dict(output,topic+"/"+p_load))
                    logger.debug('Prepping '+p_load+" for publishing")
                else:
                    mqtt_lut[topic+"/"+p_load]=output
        else:
            mqtt_lut[topic]=array
        return mqtt_lut

from datetime import datetime, timedelta, timezone, UTC
from os.path import exists
import os, pickle, subprocess, logging,shutil, shlex, schedule
from time import sleep
import json
import zoneinfo
import sys
import requests
import asyncio
from GivTCP.findInvertor import findInvertor
from GivTCP.findEVC import findEVC
import givenergy_modbus.model.inverter
from givenergy_modbus.client import GivEnergyClient
from GivTCP.givenergy_modbus_async.client.client import Client
from GivTCP.givenergy_modbus_async.model.inverter import Model, Generation
from pymodbus.client.sync import ModbusTcpClient

selfRun={}
mqttClient={}
gunicorn={}
webDash={}
rqWorker={}
redis={}
networks={}
SuperTimezone=""

logger = logging.getLogger("startup")
logging.basicConfig(format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
logger.setLevel(logging.INFO)
logging.getLogger("givenergy_modbus_async").setLevel(logging.CRITICAL)

# Check if config directory exists and creates it if not

def palm_job():
    subprocess.Popen(["/usr/local/bin/python3","/app/GivTCP_1/palm_soc.py"])

def validateEVC(HOST):
    logger.debug("Validating "+str(HOST))
    SN=""
    try:
        client = ModbusTcpClient(HOST)
        registers = client.read_holding_registers(97,6)
        if hasattr(registers,"registers"):
            regs=registers.registers
            systime=datetime(regs[0],regs[1],regs[2],regs[3],regs[4],regs[5]).replace(tzinfo=timezone.utc).isoformat()
            #get serial number here now and put in the settings file
            sn_regs = client.read_holding_registers(38,31).registers
            for num in sn_regs:
                if not num==0:
                    SN=SN+chr(num)
            #logger.info("EVC Serial Number is: "+ str(SN))
            return SN
        else:
            return False
    except:
        e=sys.exc_info()
        logger.info(e)
        return False

def get_regcache(cachelocation,inv):
    try:
        cachefile=".regcache_lockfile_"+str(inv)
        count=0
        if exists(cachefile):
            logger.debug("regcache in use, waiting...")
            while True:
                count +=1
                sleep(0.5)
                if not exists(cachefile):
                    logger.debug("regcache now available")
                    break
                if count==10:
                    # loop round for 5s waiting for it to become available
                    logger.error("Timed out waiting for regcache")
                    return None
        open(cachefile, 'w').close() #create lock file
        if exists(cachelocation):
            logger.debug("Opening regcache at: "+str(cachelocation))
            with open(cachelocation, 'rb') as inp:
                regCacheStack = pickle.load(inp)
            logger.debug("Removing lockfile")
            if exists(cachefile):
                os.remove(cachefile)
            return regCacheStack
        else:
            os.remove(cachefile)
            logger.debug("regcache doesn't exist...")
            return None
    except Exception:
        e=sys.exc_info()
        logger.error("Failed to get Cache: "+str(e))
        return None

async def getInvDeets(HOST):
    try:
        Stats={}
        client=Client(HOST,8899,3)
        await client.connect()
        await client.detect_plant(additional=False)
        await client.close()
        if not client.plant.inverter ==None:
            GEInv=client.plant.inverter
        elif not client.plant.ems ==None:
            GEInv=client.plant.ems
        elif not client.plant.gateway ==None:
            GEInv=client.plant.gateway

        SN= GEInv.serial_number
        gen=GEInv.generation
        model=GEInv.model
        fw=GEInv.arm_firmware_version
        numbats=client.plant.number_batteries

        Stats['Serial_Number']=SN
        Stats['Firmware']=fw
        Stats['Model']=model
        Stats['Generation']=gen
        Stats['Number_of_Batteries']=numbats
        Stats['IP_Address']=HOST
        logger.info(f'Inverter {str(SN)} which is a {str(gen.name.capitalize())} - {str(model.name.capitalize())} with {str(numbats)} batteries has been found at: {str(HOST)}')
        return Stats
    except:
        logger.debug("Gathering inverter details for " + str(HOST) + " failed.")
        return None
'''
def isitoldfw(invstats):
    # Firmware Versions for each Model
    # AC coupled 5xx old, 2xx new. 28x, 29x beta
    # Gen1 4xx Old, 1xx New. 19x Beta
    # Gen 2 909+ New. 99x Beta   Schedule Pause only for Gen2+
    # Gen 3 303+ New 39x Beta    New has 10 slots
    # AIO 6xx New 69x Beta       ALL has 10 slots
    if invstats['Model']==Model.AC and int(invstats['Firmware'])>500:
        return True
    elif invstats['Model']==Model.ALL_IN_ONE and int(invstats['Firmware'])<600:
        return True
    elif invstats['Generation']==Generation.GEN1 and int(invstats['Firmware'])>400:
        return True
    elif invstats['Generation']==Generation.GEN2 and int(invstats['Firmware'])<909:
        return True
    elif invstats['Generation']==Generation.GEN3 and int(invstats['Firmware'])<303:
        return True
    return False
'''

def createsettingsjson(inv):
    PATH= "/app/GivTCP_"+str(inv)
    SFILE="/config/GivTCP/allsettings.json"
    logger.debug("Recreating settings.py for invertor "+str(inv))
    with open(SFILE, 'r') as f1:
        setts=json.load(f1)

    if setts["Model_"+str(inv)]=="":
        inverter_type= asyncio.run(getInvDeets(str(setts["invertorIP_"+str(inv)])))
        setts["Model_"+str(inv)]= inverter_type['Model'].name.capitalize()
        with open(SFILE, 'w') as f:
            f.write(json.dumps(setts,indent=4))

    with open(PATH+"/settings.py", 'w') as outp:
        outp.write("class GiV_Settings:\n")
        outp.write("    invertorIP=\""+str(setts["invertorIP_"+str(inv)])+"\"\n")
        outp.write("    serial_number=\""+str(setts["serial_number_"+str(inv)])+"\"\n")
        outp.write("    inverter_type=\""+str(setts["Model_"+str(inv)])+"\"\n")
        if hasMQTT:
            outp.write("    MQTT_Address=\""+str(mqtt_host)+"\"\n")
            outp.write("    MQTT_Username=\""+str(mqtt_username)+"\"\n")
            outp.write("    MQTT_Password=\""+str(mqtt_password)+"\"\n")
            outp.write("    MQTT_Port="+str(mqtt_port)+"\n")
        else:
            outp.write("    MQTT_Address=\""+str(setts["MQTT_Address"])+"\"\n")
            outp.write("    MQTT_Username=\""+str(setts["MQTT_Username"])+"\"\n")
            outp.write("    MQTT_Password=\""+str(setts["MQTT_Password"])+"\"\n")
            outp.write("    MQTT_Port="+str(setts["MQTT_Port"])+"\n")
        outp.write("    MQTT_Retain="+str(setts["MQTT_Retain"]).capitalize()+"\n")
        outp.write("    MQTT_Topic=\""+str(setts["MQTT_Topic"])+"\"\n")
        if isAddon:
            outp.write("    HA_Auto_D=True\n")
            outp.write("    Print_Raw_Registers=True\n")
            outp.write("    MQTT_Output=True\n")
            outp.write("    isAddon=True\n")
        else:
            outp.write("    HA_Auto_D="+str(setts["HA_Auto_D"]).capitalize()+"\n")
            outp.write("    Print_Raw_Registers="+str(setts["Print_Raw_Registers"]).capitalize()+"\n")
            outp.write("    MQTT_Output="+str(setts["MQTT_Output"]).capitalize()+"\n")
            outp.write("    isAddon=False\n")
        outp.write("    ha_device_prefix=\""+str(setts["inverterName_"+str(inv)])+"\"\n")
        outp.write("    Log_Level=\""+str(setts["Log_Level"])+"\"\n")
        outp.write("    Influx_Output="+str(setts["Influx_Output"]).capitalize()+"\n")
        outp.write("    influxURL=\""+str(setts["influxURL"])+"\"\n")
        outp.write("    influxToken=\""+str(setts["influxToken"])+"\"\n")
        outp.write("    influxBucket=\""+str(setts["influxBucket"])+"\"\n")
        outp.write("    influxOrg=\""+str(setts["influxOrg"])+"\"\n")
        #outp.write("    first_run= True\n")
        outp.write("    first_run_evc= True\n")
        outp.write("    self_run_timer="+str(setts["self_run_timer"])+"\n")
        outp.write("    self_run_timer_full="+str(setts["self_run_timer_full"])+"\n")
        outp.write("    queue_retries="+str(setts["queue_retries"])+"\n")    
        outp.write("    givtcp_instance="+str(inv)+"\n")
        outp.write("    default_path=\""+str(PATH)+"\"\n")
        outp.write("    dynamic_tariff="+str(setts["dynamic_tariff"]).capitalize()+"\n")
        outp.write("    day_rate="+str(setts["day_rate"])+"\n")
        outp.write("    night_rate="+str(setts["night_rate"])+"\n")
        outp.write("    export_rate="+str(setts["export_rate"])+"\n")
        outp.write("    day_rate_start=\""+str(setts["day_rate_start"])+"\"\n")
        outp.write("    night_rate_start=\""+str(setts["night_rate_start"])+"\"\n")
        outp.write("    data_smoother=\""+str(setts["data_smoother"])+"\"\n")
        if str(setts["cache_location"])=="":
            outp.write("    cache_location=\"/config/GivTCP\"\n")
            outp.write("    Debug_File_Location=\"/config/GivTCP/log_inv_"+str(inv)+".log\"\n")
        else:
            outp.write("    cache_location=\""+str(setts["cache_location"])+"\"\n")
            outp.write("    Debug_File_Location=\""+str(setts["cache_location"])+"/log_inv_"+str(inv)+".log\"\n")
        outp.write("    inverter_num=\""+str(inv)+"\"\n")
        outp.write("    Smart_Target="+str(setts["dynamic_tariff"]).capitalize()+"\n")
        outp.write("    GE_API=\""+str(setts["GE_API"])+"\"\n")
        outp.write("    PALM_WINTER=\""+str(setts["PALM_WINTER"])+"\"\n")
        outp.write("    PALM_SHOULDER=\""+str(setts["PALM_SHOULDER"])+"\"\n")
        outp.write("    PALM_MIN_SOC_TARGET=\""+str(setts["PALM_MIN_SOC_TARGET"])+"\"\n")
        outp.write("    PALM_MAX_SOC_TARGET=\""+str(setts["PALM_MAX_SOC_TARGET"])+"\"\n")
        outp.write("    PALM_BATT_RESERVE=\""+str(setts["PALM_BATT_RESERVE"])+"\"\n")
        outp.write("    PALM_BATT_UTILISATION=\""+str(setts["PALM_BATT_UTILISATION"])+"\"\n")
        outp.write("    SOLCASTAPI=\""+str(setts["SOLCASTAPI"])+"\"\n")
        outp.write("    SOLCASTSITEID=\""+str(setts["SOLCASTSITEID"])+"\"\n")
        outp.write("    SOLCASTSITEID2=\""+str(setts["SOLCASTSITEID2"])+"\"\n")
        outp.write("    PALM_WEIGHT=\""+str(setts["PALM_WEIGHT"])+"\"\n")
        outp.write("    LOAD_HIST_WEIGHT=\""+str(setts["LOAD_HIST_WEIGHT"])+"\"\n")

        outp.write("    evc_enable="+str(setts["evc_enable"]).capitalize()+"\n")
        outp.write("    evc_ip_address=\""+str(setts["evc_ip_address"])+"\"\n")
        outp.write("    serial_number_evc=\""+str(setts["serial_number_evc"])+"\"\n")
        outp.write("    evc_self_run_timer="+str(setts["evc_self_run_timer"])+"\n")
        outp.write("    evc_import_max_current="+str(setts["evc_import_max_current"])+"\n")
        if SuperTimezone: outp.write("    timezone=\""+str(SuperTimezone)+"\"\n")

def findinv(networks):
    inverterStats={}
    if len(networks)>0:
    # For each interface scan for inverters
        logger.debug("Networks available for scanning are: "+str(networks))
        inverterStats={}
        invList={}
        list={}
        evclist={}
        logger.info("Scanning network for GivEnergy Devices...")
        try:
            for subnet in networks:
                if networks[subnet]:
                    count=0
                    # Get EVC Details
                    while len(evclist)<=0:
                        if count<2:
                            logger.debug("EVC- Scanning network ("+str(count+1)+"):"+str(networks[subnet]))
                            evclist=findEVC(networks[subnet])
                            if len(evclist)>0: break
                            count=count+1
                        else:
                            break
                    if evclist:
                        poplist=[]
                        for evc in evclist:
                            sn=validateEVC(evclist[evc])
                            if sn:
                                logger.debug("GivEVC "+str(sn)+" found at: "+str(evclist[evc]))
                                evclist[evc]=[evclist[evc],sn]
                            else:
                                logger.debug(evclist[evc]+" is not an EVC")
                                poplist.append(evc)
                        for pop in poplist:
                            evclist.pop(pop)    #remove the unknown modbus device(s)
                    # Get Inverter Details
                    count=0
                    while len(list)<=0:
                        if count<2:
                            logger.debug("INV- Scanning network ("+str(count+1)+"):"+str(networks[subnet]))
                            list=findInvertor(networks[subnet])
                            if len(list)>0: break
                            count=count+1
                        else:
                            break
                    if list:
                        logger.debug(str(len(list))+" Inverters found on "+str(networks[subnet])+" - "+str(list))
                        invList.update(list)
                        for inv in invList:
                            deets={}
                            logger.debug("Getting inverter stats for: "+str(invList[inv]))
                            count=0
                            while not deets:
                                if count<2:
                                    deets=asyncio.run(getInvDeets(invList[inv]))
                                    if deets:
                                        inverterStats[inv]=deets
                                        break   #If we found the deets then don't try again
                                    count=count+1
                                else:
                                    break
                    if len(invList)==0:
                        logger.info("No inverters found...")
                    else:
                    # write data to pickle
                        with open('invippkl.pkl', 'wb') as outp:
                            pickle.dump(inverterStats, outp, pickle.HIGHEST_PROTOCOL)
        except:
            e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
            logger.error("Error scanning for Inverters- "+str(e))
    else:
        logger.error("Unable to get host details from Supervisor\Container")
    return inverterStats, invList, evclist


SuperTimezone={}        # 02-Aug-23  default it to None so that it is defined for saving in settngs.py for non-HA usage (otherwise exception)
logger.info("========================== STARTING GivTCP================================")
try:
    logger.debug("SUPERVISOR_TOKEN is: "+ os.getenv("SUPERVISOR_TOKEN"))
    isAddon=True
    access_token = os.getenv("SUPERVISOR_TOKEN")
except:
    logger.debug("SUPERVISOR TOKEN does not exist")
    isAddon=False
    hasMQTT=False
    SuperTimezone=False

hostIP=""
if isAddon:
    #Get MQTT Details
    url="http://supervisor/services/mqtt"
    result = requests.get(url,
        headers={'Content-Type':'application/json',
                'Authorization': 'Bearer {}'.format(access_token)})
    mqttDetails=result.json()
    if mqttDetails['result']=="ok":
        logger.debug ("HA MQTT Service has been found at "+str(mqttDetails['data']['host']))
        mqtt_host=mqttDetails['data']['host']
        mqtt_username=mqttDetails['data']['username']
        mqtt_password=mqttDetails['data']['password']
        mqtt_port=mqttDetails['data']['port']
        hasMQTT=True
    else:
        hasMQTT=False
        logger.info("No HA MQTT service has been found. Install and run the Mosquitto addon, or manually configure your own MQTT broker.")

    #Get Timezone    
    url="http://supervisor/info"
    result = requests.get(url,
        headers={'Content-Type':'application/json',
                'Authorization': 'Bearer {}'.format(access_token)})
    info=result.json()
    SuperTimezone=info['data']['timezone']
    logger.debug("Supervisor Timezone: "+str(SuperTimezone))
    
    #Get addonslug/ingress url    
    url="http://supervisor/addons/self/info"
    result = requests.get(url,
        headers={'Content-Type':'application/json',
                'Authorization': 'Bearer {}'.format(access_token)})
    baseurl=result.json()['data']['ingress_url']
    logger.debug("Ingress URL is: "+str(baseurl))

    #Get Host Details    
    url="http://supervisor/network/info"
    result = requests.get(url,
        headers={'Content-Type':'application/json',
                'Authorization': 'Bearer {}'.format(access_token)})
    hostDetails=result.json()
    i=0
    for interface in hostDetails['data']['interfaces']:
        ip=str(interface['ipv4']['address']).split('/')[0][2:]
        if not ip == "":
            hostIP=ip
        networks[i]=interface['ipv4']['gateway']
        i=i+1
else:
    # Get subnet from docker if not addon
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        IP = s.getsockname()[0]
        s.close()
        networks[0]=IP
        hostIP=IP
        baseurl="/"
    except:
        e=sys.exc_info()
        logger.error("Could not get network info: "+ str(e))
logger.debug("Host IP Address is: "+str(hostIP))

sleep(2)        # Sleep to allow port scanning socket to close

#write ingress data to json file for config page to use
with open('/app/ingress/hostip.json', 'w') as f:
    f.write(json.dumps(hostIP,indent=4))
with open('/app/ingress/ingressurl.json', 'w') as f:
    f.write(json.dumps(baseurl,indent=4))

finv={}
i=0
while len(finv)==0:
    logger.info("Searching for Inverters")
    finv=findinv(networks)
    i=i+1
    if i==3: 
        break    
inverterStats=finv[0]
invList=finv[1]
evcList=finv[2]

logger.debug("GivTCP isAddon: "+str(isAddon))

redis=subprocess.Popen(["/usr/bin/redis-server","/app/redis.conf"])
logger.debug("Running Redis")

if not exists("/ssl/fullchain.pem"):
    shutil.copy("/app/ingress_no_ssl.conf","/etc/nginx/http.d/ingress.conf")

subprocess.Popen(["nginx","-g","daemon off;"])
logger.debug("Running nginx")

##########################################################################################################
#                                                                                                        #
#                                                                                                        #
#   Up to now everything is __init__ type prep, below is conifg setting (move to webpage and not ENV...) #
#                                                                                                        #
#                                                                                                        #
##########################################################################################################

########################################################
#  Set up the allsettings.json file ready for future use  #
########################################################

PATH= "/app/GivTCP_"
SFILE="/config/GivTCP/allsettings.json"
v3upgrade=True      #Check if its a new upgrade or already has new json config file
#SFILE="allsettings.json"
if not exists(SFILE):
    v3upgrade=False
    logger.debug("Copying in a template settings.json to: "+str(SFILE))
    #shutil.copyfile("/app/settings.json",SFILE)
    shutil.copyfile("settings.json",SFILE)
else:
    # If theres already a settings file, make sure its got any new elements

    with open(SFILE, 'r') as f1:
        setts=json.load(f1)
    with open("/app/settings.json", 'r') as f2:
    #with open("settings.json", 'r') as f2:
        templatesetts=json.load(f2)
    for setting in templatesetts:
        if not setting in setts:
            setts[setting]=templatesetts[setting]
    with open(SFILE, 'w') as f:
        f.write(json.dumps(setts,indent=4))

# Update json object with found data
logger.debug ("Creating master settings.json for all inverters.")
with open(SFILE, 'r') as f:
    setts=json.load(f)
if SuperTimezone: setts["TZ"]=str(SuperTimezone)
if hasMQTT:
    logger.debug("Using found MQTT data to autosetup settings.json")
    setts["MQTT_Output"]=True
    # Only autosetup if there's not already a setting, to stop overriding manual setup
    if setts["MQTT_Address"]=="": setts["MQTT_Address"]=mqtt_host
    if setts["MQTT_Username"]=="": setts["MQTT_Username"]=mqtt_username
    if setts["MQTT_Password"]=="": setts["MQTT_Password"]=mqtt_password
    setts["MQTT_Port"]=mqtt_port
if setts["MQTT_Address"]=="": setts['MQTT_Output']=False
for inv in inverterStats:
    logger.debug("Using found Inverter data to autosetup settings.json")
    # Check if serial number is already here and only update if IP address has changed
    if not inverterStats[inv]['Serial_Number'] in [setts["serial_number_1"],setts["serial_number_2"],setts["serial_number_3"],setts["serial_number_4"],setts["serial_number_5"]]:
        # find next empty slot and populate with details
        logger.info("Inverter "+ str(inverterStats[inv]['Serial_Number'])+ " not in settings file")
        for num in range(1,6):
            if setts["invertorIP_"+str(num)]=="":
                logger.info("Adding Inverter "+ str(inverterStats[inv]['Serial_Number'])+ " to slot "+ str(num))
                setts["invertorIP_"+str(num)]=inverterStats[inv]['IP_Address']
                setts["serial_number_"+str(num)]=inverterStats[inv]['Serial_Number']
                break
    else:
        for num in range(1,6):
            if inverterStats[inv]['Serial_Number'] == setts["serial_number_"+str(num)]:
                logger.info("Inverter "+ str(inverterStats[inv]['Serial_Number'])+ " already found in settings file (slot "+str(num)+"), checking IP address is unchanged...")
                if not setts["invertorIP_"+str(num)] == inverterStats[inv]['IP_Address']:
                    #If IP has changed, update it
                    logger.info("Inverter "+ str(inverterStats[inv]['Serial_Number'])+ " IP Address is different, updating: "+str(setts["invertorIP_"+str(num)])+" -> "+str(inverterStats[inv]['IP_Address']))
                    setts["invertorIP_"+str(num)]=inverterStats[inv]['IP_Address']
                break
    setts['Model_'+str(inv)]=inverterStats[inv]['Model'].name.capitalize()
        

if len(evcList)>0:
    logger.debug("evcList: "+str(evcList))
    if setts["evc_ip_address"]=="":
        setts["evc_ip_address"]=evcList[1][0]
    if setts["serial_number_evc"]=="":
        setts["serial_number_evc"]=evcList[1][1]

with open(SFILE, 'w') as f:
    f.write(json.dumps(setts,indent=4))

# Now its written to config folder, symlink to ingress so web frontend can deal with it
src=SFILE
dest="/app/ingress/allsettings.json"
if not exists(dest):
    os.symlink(src, dest)

if not exists(str(setts["cache_location"])):
    os.makedirs(str(setts["cache_location"]))
    logger.debug("No config directory exists, so creating it...")
else:
    logger.debug("Config directory already exists")

runninginv=[]

# Change this to only use those inverters set to enabled in settings (INDENT)
for inv in range(1,6):
    if setts['inverter_enable_'+str(inv)]:
        runninginv.append(inv)
        logger.info ("Setting up invertor: "+str(inv))
        PATH= "/app/GivTCP_"+str(inv)
    #    SFILE="/config/GivTCP/settings"+str(inv)+".json"
        firstrun="/config/GivTCP/.firstrun_"+str(inv)

        # Create folder per instance
        if not exists(PATH):
            shutil.copytree("/app/GivTCP", PATH)
        logger.debug("Copying in a template settings.json")
        shutil.copyfile("/app/settings.json",PATH+"/settings.json")
        # Remove old settings file
        if exists(PATH+"/settings.py"):
            os.remove(PATH+"/settings.py")
        if exists(firstrun):
            logger.debug("Removing firstrun")
            os.remove(firstrun)

    #####################################################
    #  Set up the settings.py file ready for use now    #
    #####################################################

        createsettingsjson(inv)
            
        ######
        #  Always delete lockfiles and FCRunning etc... but only delete pkl if too old?
        for file in os.listdir(setts["cache_location"]):
            filename = os.fsdecode(file)
            if not filename.endswith(".log") and not filename.startswith("rateData") and not filename.startswith("allsettings"): 
                # print(os.path.join(directory, filename))
                os.remove(setts['cache_location']+"/"+file)
        if exists(setts["cache_location"]+"/rateData_"+str(inv)+".pkl"):
            if "TZ" in os.environ:
                timezone=zoneinfo.ZoneInfo(key=setts["TZ"])
            else:
                timezone=zoneinfo.ZoneInfo(key="Europe/London")
            modDay= datetime.fromtimestamp(os.path.getmtime(setts["cache_location"]+"/rateData_"+str(inv)+".pkl")).date()
            if modDay<datetime.now(timezone).date():
                logger.debug("Old rate data cache not updated today, so deleting")
                os.remove(str(setts["cache_location"])+"/rateData_"+str(inv)+".pkl")
            else:
                logger.debug("Rate Data exists but is from today so keeping it")

        #####################################################
        #         Run the various processes needed          #
        # Check if settings.py exists then start processes  #
        # Still need to run the below process per inverter  #
        #####################################################
        logger.info("==============================================================")
        logger.info("====             Web Gui Config is at                     ====")
        logger.info("====     http://"+str(hostIP)+":8099/config.html             ====")
        logger.info("==============================================================")

        os.chdir(PATH)

        rqWorker[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/worker.py"])
        logger.debug("Running RQ worker to queue and process resume calls")

        if not hasMQTT and setts['MQTT_Address']=="127.0.0.1" and setts['MQTT_Output']==True:
            logger.info ("Starting Mosquitto on port "+str(setts['MQTT_Port']))
            mqttBroker=subprocess.Popen(["/usr/sbin/mosquitto", "-c",PATH+"/mqtt.conf"])

        if setts['self_run']==True: # Don't autorun if isAddon to prevent autostart creating rubbish before its checked by a user
            logger.info ("Running Invertor "+str(inv)+" ("+str(setts["serial_number_"+str(inv)])+") read loop every "+str(setts['self_run_timer'])+"/"+str(setts['self_run_timer_full'])+"s")
            selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/read.py", "start"])
        else:
            logger.info("======= Self Run is off, so no data collection is happening =======")
        
        GUPORT=6344+inv
        logger.debug ("Starting Gunicorn on port "+str(GUPORT))
        command=shlex.split("/usr/local/bin/gunicorn -w 3 -b :"+str(GUPORT)+" REST:giv_api")
        gunicorn[inv]=subprocess.Popen(command)

if setts['evc_enable']==True:
    if not setts['evc_ip_address']=="":
        logger.info ("Running EVC read loop every "+str(setts['evc_self_run_timer'])+"s")
        evcSelfRun=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "self_run2"])
#            logger.info ("Subscribing MQTT Broker for EVC control")
#            mqttClientEVC=subprocess.Popen(["/usr/local/bin/python3",PATH+"/mqtt_client_evc.py"])
        evcChargeModeLoop=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "chargeMode"])
        logger.debug ("Setting chargeMode loop to manage different charge modes every 60s")
    else:
        logger.info("EVC IP is missing from config. Please update and restart GivTCP")


if setts['Web_Dash']==True:
    # Create app.json
    logger.debug("Creating web dashboard config")
    os.chdir("/app/WebDashboard")
    with open("app.json", 'w') as outp:
        outp.write("{\n")
        outp.write("  \"givTcpHosts\": [\n")

        for inv in runninginv:
            GUPORT = 6344 + inv
            if inv > 1:
                outp.write("  ,{\n")
            else:
                outp.write("  {\n")
            outp.write("    \"name\": \""+setts['inverterName_'+str(inv)]+"\",\n")
            outp.write("    \"port\": \""+str(GUPORT)+"\"\n")
            outp.write("  }\n")

        outp.write("  ],\n")
        outp.write("  \"solarRate\": "+str(setts['day_rate'])+",\n")
        outp.write("  \"exportRate\": "+str(setts['export_rate'])+"\n")
        outp.write("}")
    WDPORT=int(setts['Web_Dash_Port'])
    logger.info ("Serving Web Dashboard from port "+str(WDPORT))
    command=shlex.split("/usr/bin/node /usr/local/bin/serve -p "+ str(WDPORT))
    webDash=subprocess.Popen(command)


if setts['Smart_Target']==True:
    starttime= datetime.strftime(datetime.strptime(setts['night_rate_start'],'%H:%M') - timedelta(hours=0, minutes=10),'%H:%M')
    logger.info("Setting daily charge target forecast job to run at: "+starttime)
    schedule.every().day.at(starttime).do(palm_job)

# Loop round checking all processes are running
while True:
    try:
        #if exists("/app/.reboot"):
        #    logger.critical("Stopping container as requested...")
        #    os.remove("/app/.reboot")
        #    exit()
        for inv in runninginv:
            regCacheStack=get_regcache(setts['cache_location']+"/regCache_"+str(inv)+".pkl",inv)
            if regCacheStack:
                timediff = datetime.now(UTC) - datetime.fromisoformat(regCacheStack[4]['Stats']['Last_Updated_Time'])
                timesince=(((timediff.seconds*1000000)+timediff.microseconds)/1000000)
                logger.debug("timesince last read= "+str(timesince))
            else:
                sleep(10)       #wait for first regcache then go back round loop
                continue
            PATH= "/app/GivTCP_"+str(inv)
            if setts['self_run']==True:
                if not selfRun[inv].poll()==None:
                    selfRun[inv].kill()
                    logger.error("Self Run loop process died. restarting...")
                    os.chdir(PATH)
                    logger.info ("Restarting Invertor read loop every "+str(setts['self_run_timer'])+"s")
                    selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/read.py", "start"])
                elif timesince>(float(setts['self_run_timer'])*5):
                    logger.error("Self Run loop process stuck. Killing and restarting...")
                    os.chdir(PATH)
                    selfRun[inv].kill()
                    logger.info ("Restarting Invertor read loop every "+str(setts['self_run_timer'])+"s")
                    selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/read.py", "start"])
            if not gunicorn[inv].poll()==None:
                gunicorn[inv].kill()
                logger.error("REST API process died. Restarting...")
                os.chdir(PATH)
                GUPORT=6344+inv
                logger.info ("Starting Gunicorn on port "+str(GUPORT))
                command=shlex.split("/usr/local/bin/gunicorn -w 3 -b :"+str(GUPORT)+" REST:giv_api")
                gunicorn[inv]=subprocess.Popen(command)
        
        if setts['Web_Dash'] == True:
            if not webDash.poll() == None:
                webDash.kill()
                logger.error("Web Dashboard process died. Restarting...")
                os.chdir("/app/WebDashboard")
                WDPORT = int(setts['Web_Dash_Port'])
                logger.info("Serving Web Dashboard from port " + str(WDPORT))
                command = shlex.split("/usr/bin/node /usr/local/bin/serve -p " + str(WDPORT))
                webDash = subprocess.Popen(command)

        if setts['MQTT_Address']=="127.0.0.1":
            if not mqttBroker.poll()==None:
                mqttBroker.kill()
                logger.error("MQTT Broker process died. Restarting...")
                os.chdir(PATH)
                logger.info ("Starting Mosquitto on port "+str(setts['MQTT_Port']))
                mqttBroker=subprocess.Popen(["/usr/sbin/mosquitto", "-c",PATH+"/mqtt.conf"])

        if setts['evc_enable']==True:
            if not evcSelfRun.poll()==None:
                evcSelfRun.kill()
                logger.error("EVC Self Run loop process died. restarting...")
                os.chdir(PATH)
                logger.info ("Restarting EVC read loop every "+str(setts['evc_self_run_timer'])+"s")
                selfRun[inv]=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "self_run2"])
            if not evcChargeModeLoop.poll()==None:
                evcChargeModeLoop.kill()
                logger.error("EVC Self Run loop process died. restarting...")
                os.chdir(PATH)
                logger.info ("Restarting EVC chargeMode loop every 60s")
                evcChargeModeLoop=subprocess.Popen(["/usr/local/bin/python3",PATH+"/evc.py", "chargeMode"])
    except:
        e=sys.exc_info()[0].__name__, os.path.basename(sys.exc_info()[2].tb_frame.f_code.co_filename), sys.exc_info()[2].tb_lineno
        logger.error("Error in watchdog loop: "+str(e))

    #Run jobs for smart target
    schedule.run_pending()
    sleep (60)

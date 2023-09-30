'''Test Module for GivEVC'''
from pymodbus.client import ModbusTcpClient
import datetime

class EVCType:
    """Defines type for data objects"""
    def __init__(self,dT,sC,cF):
        self.devType = dT
        self.sensorClass=sC
        self.controlFunc=cF

class EVCLut:

    status=[
        'Unknown',
        'Idle',
        'Connected',
        'Ready',
        'Starting',
        'Charging',
        'Startup Failure',
        'End of Charging',
        'System Failure',
        'Pre-Order (OCPP)',
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
    charge_mode=['Plug and Charge', 'Swipe to Charge']
    charge_control=['Start','Stop']

    evc_lut={
        0: ('CHARGING_STATE',status),
        2: ('CABLE_STATE',cable_status),
        4: ('ERROR_CODE',error_codes),
        6: 'CURRENT_L1',
        8: 'CURRENT_L2',
        10: 'CURRENT_L3',
        12: 'ACTIVE_POWER',
        16: 'ACTIVE_POWER_L1',
        20: 'ACTIVE_POWER_L2',
        24: 'ACTIVE_POWER_L3',
        28: 'METER_ENERGY',
        32: 'EVSE_MAX_CURRENT',
        34: 'EVSE_MIN_CURRENT',
        36: 'CABLE_MAX_CURRENT',
        72: 'CHARGE_ENERGY',
        78: 'CHARGE_SESSION_TIME',
        86: 'MAX_SAFE_CURRENT',
        88: 'COMM_TIMEOUT',
        90: 'CHARGE_CURRENT_LIMIT',
        92: ('CHARGE_MODE',charge_mode),
        94: ('CHARGE_CONTROL',charge_control),
        109: 'VOLTAGE_L1',
        111: 'VOLTAGE_L2',
        113: 'VOLTAGE_L3'}

    evc_entity_type={
        "CHARGING_STATE":EVCType("sensor","string",""),
        "CABLE_STATE":EVCType("sensor","string",""),
        "ERROR_CODE":EVCType("sensor","string",""),
        "CHARGE_MODE":EVCType("sensor","string","chargeMode"),
        "CHARGE_CONTROL":EVCType("sensor","string","controlCharge"),
        "CURRENT_L1":EVCType("sensor","current",""),
        "CURRENT_L2":EVCType("sensor","current",""),
        "CURRENT_L3":EVCType("sensor","current",""),
        "MAX_SAFE_CURRENT":EVCType("sensor","current",""),
        "EVSE_MAX_CURRENT":EVCType("sensor","current",""),
        "EVSE_MIN_CURRENT":EVCType("sensor","current",""),
        "CABLE_MAX_CURRENT":EVCType("sensor","current",""),
        "CHARGE_CURRENT_LIMIT":EVCType("sensor","current",""),
        "ACTIVE_POWER":EVCType("sensor","power",""),
        "ACTIVE_POWER_L1":EVCType("sensor","power",""),
        "ACTIVE_POWER_L2":EVCType("sensor","power",""),
        "ACTIVE_POWER_L3":EVCType("sensor","power",""),
        "METER_ENERGY":EVCType("sensor","energy",""),
        "CHARGE_ENERGY":EVCType("sensor","energy",""),
        "CHARGE_SESSION_TIME":EVCType("sensor","",""),
        "COMM_TIMEOUT":EVCType("sensor","",""),
        "VOLTAGE_L1":EVCType("sensor","voltage",""),
        "VOLTAGE_L2":EVCType("sensor","voltage",""),
        "VOLTAGE_L3":EVCType("sensor","voltage",""),
        }

regs=[]
output={}
try:
    client = ModbusTcpClient('192.168.2.58')
    result = client.read_holding_registers(0,60)
    result2 = client.read_holding_registers(60,54)
    client.close()
    regs=result.registers+result2.registers
    for reg in EVCLut.evc_lut.items():
        if isinstance(reg[1],tuple):
            output[reg[1][0]]=reg[1][1][regs[reg[0]]]
        else:
            if 'CURRENT' in str(reg[1]):
                val=regs[reg[0]]/10
            elif 'VOLTAGE' in str(reg[1]):
                val=regs[reg[0]]/10
            elif 'ENERGY' in str(reg[1]):
                val=regs[reg[0]]/10
            else:
                val=regs[reg[0]]
            output[reg[1]]=val
    SN=''
    for num in regs[38:69]:
        if not num==0:
            SN=SN+chr(num)
    output['SERIAL_NUMBER']=SN
    output['CHARGE_START_TIME']=datetime.time(regs[74],regs[75],regs[76])
    output['CHARGE_END_TIME']=datetime.time(regs[82],regs[83],regs[84])
    output['SYSTEM_TIME']=datetime.datetime(regs[97],regs[98],regs[99],regs[100],regs[101],regs[102])

    print (output)
except Exception:
    print("Error")


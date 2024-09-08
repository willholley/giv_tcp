# GivTCP Settings & Control Guide

## GivTCP Control (Inverters)
GivTCP provides a wide range of inverter control settings. When using HA an MQTT device is automatically created for each inverter:

<img src="docs/images/settings-1.png" width="400"> <img src="docs/images/settings-2.png" width="400">

| Control Function | Description | GivEnergy Cloud Equivalent |
| ------------- | ------------- | ------------- |
| Active Power Rate  | Sets the maximum active power output as a precentage. 100% = inverter rating | Inverter Max Output Active Power Percent |
| Battery Charge Rate | Sets the battery charge power in Watts | Battery Charge Power |
| Battery Charge Rate AC | Sets the inverter AC charge power as a percentage. 100% = inverter rating | Inverter Charge Power Precentage |
| Battery Discharge Rate | Sets the battery discharge power in Watts | Battery Discharge Power |
| Battery Discharge Rate AC | Sets the inverter AC dischrage power as a percentage. 100% = inverter rating | Inverter Discharge Power Precentage |
| Battery Pause Mode | Sets the battery operation mode. One of "Disabled","PauseCharge","PauseDischarge" or "PauseBoth" | Pause Battery |
| Battery Power Cutoff | ???? | Battery Cutoff % Limit |
| Battery Power Reserve | Sets the minimum battery discharge SOC as a precentage. 100% = battery capacity  | Battery Reserve % Limit |
Charge Target SOC (1-10) | xxx | xxx |
| Discharge Target (SOC 1-10) | xxx | xxx |
| Eco Mode | xxx | xxx |
| Enable Charge Schedule | xxx | xxx |
| Enable Discharge Schedule | xxx | xxx |
| Force Charge | xxx | xxx |
| Force Charge Num | xxx | xxx |
| Force Export | xxx | xxx |
| Force Export Num | xxx | xxx |
| Mode | xxx | xxx |
| Reboot Addon | xxx | xxx |
| Reboot Invertor | xxx | xxx |
| Sync Time | xxx | xxx |
| Target SOC | xxx | xxx |
| Temp Pause Charge | xxx | xxx |
| Temp Pause Charge Num | xxx | xxx |
| Temp Pause Discharge | xxx | xxx |
| Temp Pause Discharge Num | xxx | xxx |

## GivTCP MQTT Control (Inverters)

| Function                | Description                                                                                                                                                                                               | REST URL                 | REST payload                                               | MQTT Topic              | MQTT Payload                                               |
|-------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------|------------------------------------------------------------|-------------------------|------------------------------------------------------------|
| enableChargeTarget      | Sets   inverter to follow setChargeTarget value when charging from grid (will stop   charging when battery SOC= ChargeTarget)                                                                             | /enableChargeTarget      | {"state","enable"}                                         | enableChargeTarget      | enable                                                     |
| disableChargeTarget     | Sets   inverter to ignore setChargeTarget value when charging from grid (will   continue to charge to 100% during ChargeSlot)                                                                             | /disableChargeTarget     | {"state","enable"}                                         | disableChargeTarget     | enable                                                     |
| enableChargeSchedule    | Sets   the Charging schedule state, if disabled the battery will not charge as per   the schedule                                                                                                         | /enableChargeSchedule    | {"state","enable"}                                         | enableChargeSchedule    | enable                                                     |
| enableDischargeSchedule | Sets   the Discharging schedule state, if disabled the battery will will ignore rhe   discharge schedule and discharge as per demand (similar to eco mode)                                                | /enableDischargeSchedule | {"state","enable"}                                         | enableDischargeSchedule | enable                                                     |
| enableDischarge         | Enable/Disables Discharging to instantly pause discharging,   use 'enable' or 'disable'                                                                                                                   | /enableDischarge         | {"state","enable"}                                         | enableDischarge         | enable                                                     |
| setChargeRate           | Sets the charge power as a percentage. 100% == 2.6kW                                                                                                                                                      | /setChargeRate           | {"chargeRate","100"}                                    | setChargeRate           | 100                                                        |
| setDischargeRate        | Sets the discharge power as a percentage. 100% == 2.6kW                                                                                                                                                   | /setDischargeRate        | {"dischargeRate","100"}                                       | setDischargeRate        | 100                                                        |
| setChargeTarget         | Sets   the Target charge SOC                                                                                                                                                                              | /setChargeTarget         | {"chargeToPercent":"50"}                                   | setChargeTarget         | 50                                                         |
| setBatteryReserve       | Sets   the Battery Reserve discharge cut-off limit                                                                                                                                                        | /setBatteryReserve       | {"reservePercent":"5"}                                 | setBatteryReserve       | 5                                                          |
| setChargeSlot1          | Sets   the time and target SOC of the first chargeslot. Times must be expressed in   hhmm format. Enable flag show in the battery.api documentation is not needed   and chargeToPercent is optional       | /setChargeSlot1          | {"start":"0100","finish":"0400","chargeToPercent":"55"}    | setChargeSlot1          | {"start":"0100","finish":"0400","chargeToPercent":"55"}    |
| setDischargeSlot1       | Sets   the time and target SOC of the first dischargeslot. Times must be expressed   in hhmm format. Enable flag show in the battery.api documentation is not   needed and dischargeToPercent is optional | /setDischargeSlot1       | {"start":"0100","finish":"0400","dischargeToPercent":"55"} | setDischargeSlot1       | {"start":"0100","finish":"0400","dischargeToPercent":"55"} |
| setDischargeSlot2       | Sets   the time and target SOC of the first dischargeslot. Times must be expressed   in hhmm format. Enable flag show in the battery.api documentation is not   needed and dischargeToPercent is optional | /setDischargeSlot2       | {"start":"0100","finish":"0400","dischargeToPercent":"55"} | setDischargeSlot2       | {"start":"0100","finish":"0400","dischargeToPercent":"55"} |
| setBatteryMode          | Sets   battery operation mode. Mode value must be one of Eco, Timed Demand or Timed Export                                                                                                                                        | /setBatteryMode          | {"mode":"Eco"}                                               | setBatteryMode          | 1                                                          |
| setDateTime             | Sets   inverter time, format must be as define in payload                                                                                                                                                 | /setDateTime             | {"dateTime":"dd/mm/yyyy   hh:mm:ss"}                       | setDateTime             | "dd/mm/yyyy hh:mm:ss"                                      |
| setBatteryPauseMode          | Sets   battery operation mode. Mode value must be one of "Disabled","PauseCharge","PauseDischarge" or "PauseBoth"                                                                                                                                         | /setBatteryPauseMode          | {"state":"Disabled"}                                               | setBatteryPauseMode          | 1
| forceExport          | Forces battery to Export (discharge at Max power) for a given duration in Minutes. command must be "Cancel" or an integer value. Sending 0 will also call the cancel function                                                                                                                                         | /forceExport          | {"15"}                                               | forceExport          | 1
| forceCharge          | Forces battery to charge for a given duration in Minutes. Command must be "Cancel" or an integer value. Sending 0 will also call the cancel function                                                                                                                                         | /forceCharge          | {"15"}                                               | forceCharge          | 1
| tempPauseCharge          | Suspends charging for a for a given duration in Minutes. Command must be "Cancel" or an integer value. Sending 0 will also call the cancel function                                                                                                                                         | /tempPauseCharge          | {"15"}                                               | tempPauseCharge          | 1
| tempPauseDischarge          | Suspends discharging for a given duration in Minutes. command must be "Cancel" or an integer value. Sending 0 will also call the cancel function                                                                                                                                         | /tempPauseDischarge          | {"15"}                                               | tempPauseDischarge          | 1


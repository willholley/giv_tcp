import { defineStore } from 'pinia'
import { useStorage } from '@vueuse/core'

export const useTcpStore = defineStore('givtcp-form', {
  state: () => ({
    inverter: useStorage('inverter', {
      NUMINVERTORS: 1,
      invertorIP: "",
      numBatteries: 1,
      isAIO: false,
      isAC: false
    }),
    mqtt: useStorage('mqtt', {
      MQTT_Output: false,
      MQTT_Address: "",
      MQTT_Username: "",
      MQTT_Password: "",
      MQTT_Retain: true,
      //optional
      MQTT_Topic: "GivEnergy",
      MQTT_Port: 1883
    }),
    influx: useStorage('influx', {
      Influx_Output: false,
      influxURL: "",
      influxToken: "",
      influxBucket: "",
      influxOrg: ""
    }),
    homeAssistant: useStorage('homeAssistant', {
      HA_Auto_D: true,
      ha_device_prefix: "GivTCP"
      //PYTHONPATH: '/app',
    }),
    tariffs: useStorage('tariffs', {
      dynamic_tariff: false,
      export_rate: 0.04,
      day_rate:0.395,
      day_rate_start: "05:30",
      night_rate: 0.155,
      night_rate_start: "23:30",
    }),
    miscellaneous: useStorage('miscellaneous', {
      TZ: 'Europe/London',
      Print_Raw_Registers: true,
      Log_Level: "Info",
      self_run: true,
      self_run_timer: 15,
      queue_retries: 2,
      data_smoother: "medium",
      cache_location: "/config/GivTCP"
    }),
    web: useStorage('web', {
      Host_IP: "",
      Web_Dash: false,
      Web_Dash_Port: 3000
    }),
    palm: useStorage('palm', {
      Smart_Target: false,
      GE_API: "",
      SOLCASTAPI:"",
      SOLCASTSITEID:"",
      SOLCASTSITEID2:"",
      PALM_WINTER: "01,02,03,10,11,12",
      PALM_SHOULDER: "04,05,09",
      PALM_MIN_SOC_TARGET: 25,
      PALM_MAX_SOC_TARGET: 45,
      PALM_BATT_RESERVE: 4,
      PALM_BATT_UTILISATION: 0.85,
      PALM_WEIGHT: 35,
      LOAD_HIST_WEIGHT: 1
    }),
    evc: useStorage('evc', {
      evc_enable: false,
      evc_ip_address: "",
      evc_self_run_timer: 10,
      evc_import_max_current: 60
    })
  })
})

export const useStep = defineStore('step', {
  state: () => ({
    step: useStorage('step', -1),
    isNew: useStorage('isNew', true)
  })
})

export const useCard = defineStore('card', {
  state: () => ({
    inverter: {
      title: 'Inverter',
      subtitle: 'Setup your inverter configurations',
      fields: [
        {
          type: 'select',
          options: {
            label: 'Number Of Inverters',
            items: [1, 2, 3],
            parent: 'inverter',
            key: 'NUMINVERTORS'
          }
        },
        {
          type: 'select',
          options: {
            label: 'Number Of Batteries',
            items: [1, 2, 3],
            parent: 'inverter',
            key: 'numBatteries'
          }
        },
        {
          type: 'text',
          options: {
            label: 'IP Address',
            parent: 'inverter',
            key: 'invertorIP'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Is this Invertor an AIO?',
            parent: 'inverter',
            key: 'isAIO'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Is this Invertor on "old firmware"?',
            parent: 'inverter',
            key: 'isAC'
          }
        },
      ]
    },
    mqtt: {
      title: 'MQTT',
      subtitle: 'Setup the MQTT broker that stores information about your incoming inverter data',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'Enable',
            parent: 'mqtt',
            key: 'MQTT_Output'
          }
        },
        {
          type: 'text',
          options: {
            label: 'IP Address',
            parent: 'mqtt',
            key: 'MQTT_Address'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Username',
            parent: 'mqtt',
            key: 'MQTT_Username'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Password',
            parent: 'mqtt',
            key: 'MQTT_Password'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Topic',
            parent: 'mqtt',
            key: 'MQTT_Topic'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Port',
            parent: 'mqtt',
            key: 'MQTT_Port'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Retain',
            parent: 'mqtt',
            key: 'MQTT_Retain'
          }
        }
      ]
    },
    influx: {
      title: 'InfluxDB',
      subtitle: 'Setup your InfluxDB instance',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'Output',
            parent: 'influx',
            key: 'Influx_Output'
          }
        },
        {
          type: 'text',
          options: {
            label: 'URL',
            parent: 'influx',
            key: 'influxURL'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Token',
            parent: 'influx',
            key: 'influxToken'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Bucket',
            parent: 'influx',
            key: 'influxBucket'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Org',
            parent: 'influx',
            key: 'influxOrg'
          }
        }
      ]
    },
    homeAssistant: {
      title: 'Home Assistant',
      subtitle: 'Setup your Home Assistant instance',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'Auto Discovery',
            parent: 'homeAssistant',
            key: 'HA_Auto_D'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Device Prefix',
            parent: 'homeAssistant',
            key: 'ha_device_prefix'
          }
        }
      ]
    },
    tariffs: {
      title: 'Tariffs',
      subtitle: 'Setup your Tariffs',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'Dynamic',
            parent: 'tariffs',
            key: 'dynamic_tariff'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Export Rate',
            parent: 'tariffs',
            key: 'export_rate'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Day Rate',
            parent: 'tariffs',
            key: 'day_rate'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Day Start',
            parent: 'tariffs',
            key: 'day_rate_start'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Night Rate',
            parent: 'tariffs',
            key: 'night_rate'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Night Start',
            parent: 'tariffs',
            key: 'night_rate_start'
          }
        }
      ]
    },
    miscellaneous: {
      title: 'Miscellaneous',
      subtitle: 'Setup Any Miscellaneous variables',
      fields: [
        {
          type: 'text',
          options: {
            label: 'Timezone',
            parent: 'miscellaneous',
            key: 'TZ'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Log Level',
            parent: 'miscellaneous',
            key: 'Log_Level'
          }
        },
        {
          type: 'checkbox',
          options: {
            label: 'Print Raw',
            parent: 'miscellaneous',
            key: 'Print_Raw_Registers'
          }
        },{
          type: 'checkbox',
          options: {
            label: 'Self Run',
            parent: 'miscellaneous',
            key: 'self_run'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Self Run Loop Timer',
            parent: 'miscellaneous',
            key: 'self_run_timer'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Queue Retries',
            parent: 'miscellaneous',
            key: 'queue_retries'
          }
        },
        {
          type: 'select',
          options: {
            label: 'Smoothing',
            parent: 'miscellaneous',
            items: ["high", "medium", "low","none"],
            key: 'data_smoother'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Cache Location',
            parent: 'miscellaneous',
            key: 'cache_location'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Timezone',
            parent: 'miscellaneous',
            key: 'TZ'
          }
        },
      ]
    },
    web: {
      title: 'Web',
      subtitle: 'Web Dashboard',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'Dashboard',
            parent: 'web',
            key: 'Web_Dash'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Host IP',
            parent: 'web',
            key: 'Host_IP'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Port',
            parent: 'web',
            key: 'Web_Dash_Port'
          }
        }
      ]
    },
    palm: {
      title: 'Palm',
      subtitle: 'Setup your Smart Target variables',
      fields: [
        ,{
          type: 'checkbox',
          options: {
            label: 'Enable',
            parent: 'palm',
            key: 'Smart_Target'
          }
        },
        {
          type: 'text',
          options: {
            label: 'GivEnergy API',
            parent: 'palm',
            key: 'GE_API'
          }
        },
        {
          type: 'text',
          options: {
            label: 'SolCast API Key',
            parent: 'palm',
            key: 'Solcast_API'
          }
        },
        {
          type: 'text',
          options: {
            label: 'SolCast Site ID 1',
            parent: 'palm',
            key: 'Solcast_SiteID'
          }
        },
        {
          type: 'text',
          options: {
            label: 'SolCast Site ID 2',
            parent: 'palm',
            key: 'Solcast_SiteID2'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Winter',
            parent: 'palm',
            key: 'PALM_WINTER'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Shoulder',
            parent: 'palm',
            key: 'PALM_SHOULDER'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Minimum SoC Target',
            parent: 'palm',
            key: 'PALM_MIN_SOC_TARGET'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Maximum SoC Target',
            parent: 'palm',
            key: 'PALM_MAX_SOC_TARGET'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Battery Reserve',
            parent: 'palm',
            key: 'PALM_BATT_RESERVE'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Battery Utilisation',
            parent: 'palm',
            key: 'PALM_BATT_UTILISATION'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Weight',
            parent: 'palm',
            key: 'PALM_WEIGHT'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Historical Weight',
            parent: 'palm',
            key: 'LOAD_HIST_WEIGHT'
          }
        }
      ]
    },
    evc: {
      title: 'EVC',
      subtitle: 'Setup Any Web variables',
      fields: [
        {
          type: 'checkbox',
          options: {
            label: 'EVC Enable',
            parent: 'evc',
            key: 'evc_enable'
          }
        },
        {
          type: 'text',
          options: {
            label: 'EVC IP',
            parent: 'evc',
            key: 'evc_ip_address'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Timer',
            parent: 'evc',
            key: 'evc_self_run_timer'
          }
        },
        {
          type: 'text',
          options: {
            label: 'Max Import Current',
            parent: 'evc',
            key: 'evc_import_max_current'
          }
        }
      ]
    }
  })
})

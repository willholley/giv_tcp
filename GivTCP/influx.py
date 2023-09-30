# version 2022.01.31
"""Influx Module"""
import logging
from logging.handlers import TimedRotatingFileHandler
from influxdb_client import InfluxDBClient, WriteOptions
from settings import GivSettings

logger = logging.getLogger("GivTCP_Influx_"+str(GivSettings.givtcp_instance))
logging.basicConfig(format='%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
if GivSettings.Debug_File_Location!="":
    fh = TimedRotatingFileHandler(GivSettings.Debug_File_Location, when='D', interval=1, backupCount=7)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
if GivSettings.Log_Level.lower()=="debug":
    logger.setLevel(logging.DEBUG)
elif GivSettings.Log_Level.lower()=="info":
    logger.setLevel(logging.INFO)
elif GivSettings.Log_Level.lower()=="critical":
    logger.setLevel(logging.CRITICAL)
elif GivSettings.Log_Level.lower()=="warning":
    logger.setLevel(logging.WARNING)
else:
    logger.setLevel(logging.ERROR)


class GivInflux:
    """Class to handle writing data to Influx db"""

    def line_protocol(serial_number,readings):
        """Create Influx Line protocol"""
        return '%s,tagKey=%s %s',serial_number,'GivReal', readings

    def make_influx_string(datastr: str):
        """Create Influx Line string"""
        new_str=datastr.replace(" ","_")
        new_str=new_str.lower()
        return new_str

    def string_safe(data):
        """Create a safe string"""
        output=str(data)
        if isinstance(data,str):
            output="\""+str(data)+"\""
        return output

    def publish(serial_number,data):
        """Publish data to influx"""
        output_str=""
        power_output = data['Power']['Power']
        for key in power_output:
            logging.debug("Creating Power string for InfluxDB")
            output_str=output_str+str(GivInflux.make_influx_string(key))+'='+GivInflux.string_safe(power_output[key])+','
        flow_output = data['Power']['Flows']
        for key in flow_output:
            logging.debug("Creating Power Flow string for InfluxDB")
            output_str=output_str+str(GivInflux.make_influx_string(key))+'='+GivInflux.string_safe(flow_output[key])+','
        energy_today = data['Energy']['Today']
        for key in energy_today:
            logging.debug("Creating Energy/Today string for InfluxDB")
            output_str=output_str+str(GivInflux.make_influx_string(key))+'='+GivInflux.string_safe(energy_today[key])+','

        energy_total = data['Energy']['Total']
        for key in energy_total:
            logging.debug("Creating Energy/Total string for InfluxDB")
            output_str=output_str+str(GivInflux.make_influx_string(key))+'='+GivInflux.string_safe(energy_total[key])+','

        logging.debug("Data sending to Influx is: %s", output_str[:-1])
        data1=GivInflux.line_protocol(serial_number,output_str[:-1])
        _db_client = InfluxDBClient(url=GivSettings.influxURL, token=GivSettings.influxToken, org=GivSettings.influxOrg, debug=True)
        _write_api = _db_client.write_api(write_options=WriteOptions(batch_size=1))
        _write_api.write(bucket=GivSettings.influxBucket, record=data1)
        logging.info("Written to InfluxDB")

        _write_api.close()
        _db_client.close()

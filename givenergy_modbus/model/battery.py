from typing import Tuple

from givenergy_modbus.model import GivEnergyBaseModel


class Battery(GivEnergyBaseModel):
    """Structured format for all inverter attributes."""

    battery_serial_number: str
    v_battery_cell_01: float
    v_battery_cell_02: float
    v_battery_cell_03: float
    v_battery_cell_04: float
    v_battery_cell_05: float
    v_battery_cell_06: float
    v_battery_cell_07: float
    v_battery_cell_08: float
    v_battery_cell_09: float
    v_battery_cell_10: float
    v_battery_cell_11: float
    v_battery_cell_12: float
    v_battery_cell_13: float
    v_battery_cell_14: float
    v_battery_cell_15: float
    v_battery_cell_16: float
    temp_battery_cells_1: float
    temp_battery_cells_2: float
    temp_battery_cells_3: float
    temp_battery_cells_4: float
    v_battery_cells_sum: float
    temp_bms_mos: float
    v_battery_out: float
    battery_full_capacity: float
    battery_design_capacity: float
    battery_remaining_capacity: float
    battery_status_1_2: Tuple[int, int]
    battery_status_3_4: Tuple[int, int]
    battery_status_5_6: Tuple[int, int]
    battery_status_7: Tuple[int, int]
    battery_warning_1_2: Tuple[int, int]
    battery_num_cycles: int
    battery_num_cells: int
    bms_firmware_version: int
    battery_soc: int
    battery_design_capacity_2: float
    temp_battery_max: float
    temp_battery_min: float
    usb_inserted: bool
    e_battery_charge_total_2: float
    e_battery_discharge_total_2: float

class HVBMU(GivEnergyBaseModel):
    """Structured format for all inverter attributes."""
    """BMU Register structure Cell Volt and Temp"""
    v_battery_cell_01: float
    v_battery_cell_02: float
    v_battery_cell_03: float
    v_battery_cell_04: float
    v_battery_cell_05: float
    v_battery_cell_06: float
    v_battery_cell_07: float
    v_battery_cell_08: float
    v_battery_cell_09: float
    v_battery_cell_10: float
    v_battery_cell_11: float
    v_battery_cell_12: float
    v_battery_cell_13: float
    v_battery_cell_14: float
    v_battery_cell_15: float
    v_battery_cell_16: float
    v_battery_cell_17: float
    v_battery_cell_18: float
    v_battery_cell_19: float
    v_battery_cell_20: float
    v_battery_cell_21: float
    v_battery_cell_22: float
    v_battery_cell_23: float
    v_battery_cell_24: float
    temp_battery_cells_1: float
    temp_battery_cells_2: float
    temp_battery_cells_3: float
    temp_battery_cells_4: float
    temp_battery_cells_5: float
    temp_battery_cells_6: float
    temp_battery_cells_7: float
    temp_battery_cells_8: float
    temp_battery_cells_9: float
    temp_battery_cells_10: float
    temp_battery_cells_11: float
    temp_battery_cells_12: float
    temp_battery_cells_13: float
    temp_battery_cells_14: float
    temp_battery_cells_15: float
    temp_battery_cells_16: float
    temp_battery_cells_17: float
    temp_battery_cells_18: float
    temp_battery_cells_19: float
    temp_battery_cells_20: float
    temp_battery_cells_21: float
    temp_battery_cells_22: float
    temp_battery_cells_23: float
    temp_battery_cells_24: float

class HVBCU(GivEnergyBaseModel):
    pack_software_version: str
    number_of_module: float
    cells_per_module: float
    cluster_cell_voltage: float
    cluster_cell_temperature: float
    status: str
    battery_voltage: float
    load_voltage: float
    battery_current: float
    battery_power: float
    battery_soh: float  # should this be SOC?
    charge_energy_total: float
    discharge_energy_total: float
    charge_energy_capacity_total: float
    discharge_energy_capacity_total: float
    charge_energy_today: float
    discharge_energy_today: float
    charge_energy_capacity_today: float
    discharge_energy_capacity_today: float
    battery_capacity: float
    number_of_cycles: float
    min_discharge_voltage: float
    max_discharge_voltage: float
    min_discharge_current: float
    max_discharge_current: float
    max_cell_voltage: float
    max_voltage_module: float
    max_voltage_cell: float
    min_cell_voltage: float
    min_voltage_module: float
    min_voltage_cell: float
    max_cell_temperature: float
    max_temperature_module: float
    max_temperature_cell: float
    min_cell_temperature: float
    min_temperature_module: float
    min_temperature_cell: float
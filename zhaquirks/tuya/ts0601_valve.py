"""Collection of Tuya Valve devices e.g. water valves, gas valve etc."""

from datetime import datetime, timedelta, timezone

from zigpy.quirks.v2 import EntityPlatform, EntityType
from zigpy.quirks.v2.homeassistant import UnitOfTime
from zigpy.quirks.v2.homeassistant.sensor import SensorDeviceClass, SensorStateClass
import zigpy.types as t
from zigpy.zcl.clusters.general import BatterySize

from zhaquirks.tuya import TUYA_CLUSTER_ID
from zhaquirks.tuya.builder import TuyaQuirkBuilder
from zhaquirks.tuya.mcu import TuyaMCUCluster


class TuyaValveWeatherDelay(t.enum8):
    """Tuya Irrigation Valve weather delay enum."""

    Disabled = 0x00
    Delayed_24h = 0x01
    Delayed_48h = 0x02
    Delayed_72h = 0x03


class TuyaValveTimerState(t.enum8):
    """Tuya Irrigation Valve timer state enum."""

    Disabled = 0x00
    Active = 0x01
    Enabled = 0x02


(
    TuyaQuirkBuilder("_TZE200_81isopgh", "TS0601")
    .applies_to("_TZE200_1n2zev06", "TS0601")
    .tuya_onoff(dp_id=1)
    .tuya_metering(
        dp_id=5, scale=0.0295735
    )  # per z2m reports in fl oz, convert to liters
    .tuya_dp_attribute(
        dp_id=6,
        attribute_name="dp_6",
        type=t.uint32_t,
    )
    .tuya_battery(dp_id=7, battery_type=BatterySize.AA, battery_qty=4)
    .tuya_enum(
        dp_id=10,
        attribute_name="weather_delay",
        enum_class=TuyaValveWeatherDelay,
        translation_key="weather_delay",
        fallback_name="Weather delay",
        initially_disabled=True,
    )
    .tuya_sensor(
        dp_id=11,
        attribute_name="time_left",
        type=t.uint32_t,
        converter=lambda x: x / 60,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        unit=UnitOfTime.SECONDS,
        translation_key="time_left",
        fallback_name="Time left",
    )
    .tuya_enum(
        dp_id=12,
        attribute_name="timer_state",
        enum_class=TuyaValveTimerState,
        entity_platform=EntityPlatform.SENSOR,
        entity_type=EntityType.DIAGNOSTIC,
        translation_key="timer_state",
        fallback_name="Timer state",
    )
    .tuya_sensor(
        dp_id=15,
        attribute_name="last_valve_open_duration",
        type=t.uint32_t,
        divisor=60,
        entity_type=EntityType.DIAGNOSTIC,
        unit=UnitOfTime.MINUTES,
        translation_key="last_valve_open_duration",
        fallback_name="Last valve open duration",
    )
    .tuya_dp_attribute(
        dp_id=102,
        attribute_name="valve_position",
        type=t.uint32_t,
    )
    .skip_configuration()
    .add_to_registry()
)


class ParksideTuyaValveManufCluster(TuyaMCUCluster):
    """Manufacturer Specific Cluster for the _TZE200_htnnfasr water valve sold as PARKSIDE."""

    async def bind(self):
        """Bind cluster.

        When adding this device tuya gateway issues factory reset,
        we just need to reset the frost lock, because its state is unknown to us.
        """
        result = await super().bind()
        await self.write_attributes({self.attributes_by_name["frost_lock_reset"].id: 0})
        return result


(
    TuyaQuirkBuilder(
        "_TZE200_htnnfasr", "TS0601"
    )  # HG06875, Lidl - Parkside smart watering timer
    .tuya_onoff(dp_id=1)
    .tuya_number(
        dp_id=5,
        attribute_name="timer_duration",
        type=t.uint32_t,
        min_value=1,
        max_value=599,
        step=1,
        unit=UnitOfTime.MINUTES,
        translation_key="timer_duration",
        fallback_name="Timer duration",
    )
    .tuya_sensor(
        dp_id=6,
        attribute_name="time_left",
        type=t.uint32_t,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        unit=UnitOfTime.SECONDS,
        translation_key="time_left",
        fallback_name="Time left",
    )
    .tuya_battery(dp_id=11, battery_type=BatterySize.AA, battery_qty=4)
    .tuya_switch(
        dp_id=108,
        attribute_name="frost_lock",
        entity_type=EntityType.STANDARD,
        on_value=0,  # Invert
        off_value=1,
        translation_key="frost_lock",
        fallback_name="Frost lock",
    )
    .tuya_dp_attribute(
        dp_id=109,
        attribute_name="frost_lock_reset",
        type=t.Bool,
    )
    .write_attr_button(
        attribute_name="frost_lock_reset",
        cluster_id=TUYA_CLUSTER_ID,
        attribute_value=0x00,  # 0 resets frost lock
        translation_key="frost_lock_reset",
        fallback_name="Frost lock reset",
    )
    .skip_configuration()
    .add_to_registry(replacement_cluster=ParksideTuyaValveManufCluster)
)


GIEX_12HRS_AS_SEC = 43200
GIEX_24HRS_AS_MIN = 1440
UNIX_EPOCH_TO_ZCL_EPOCH = 946684800


class GiexIrrigationMode(t.enum8):
    """Giex Irrigation Mode Enum."""

    Duration = 0x00
    Capacity = 0x01


class GiexIrrigationWeatherDelay(t.enum8):
    """Giex Irrigation Weather Delay Enum."""

    NoDelay = 0x00
    TwentyFourHourDelay = 0x01
    FortyEightHourDelay = 0x02
    SeventyTwoHourDelay = 0x03


def giex_string_to_td(v: str) -> int:
    """Convert Giex String Duration to seconds."""
    dt = datetime.strptime(v, "%H:%M:%S,%f")
    return timedelta(hours=dt.hour, minutes=dt.minute, seconds=dt.second).seconds


def giex_string_to_ts(v: str) -> int | None:
    """Convert Giex String Duration datetime."""
    dev_tz = timezone(timedelta(hours=4))
    dev_dt = datetime.now(dev_tz)
    try:
        dt = datetime.strptime(v, "%H:%M:%S").replace(tzinfo=dev_tz)
        dev_dt.replace(hour=dt.hour, minute=dt.minute, second=dt.second)
    except ValueError:
        return None  # on initial start the device will return '--:--:--'
    return int(dev_dt.timestamp() + UNIX_EPOCH_TO_ZCL_EPOCH)


gx02_base_quirk = (
    TuyaQuirkBuilder()
    .tuya_battery(dp_id=108, battery_type=BatterySize.AA, battery_qty=4)
    .tuya_metering(dp_id=111)
    .tuya_onoff(dp_id=2)
    .tuya_number(
        dp_id=103,
        attribute_name="irrigation_cycles",
        type=t.uint8_t,
        min_value=0,
        max_value=100,
        step=1,
        translation_key="irrigation_cycles",
        fallback_name="Irrigation cycles",
    )
    .tuya_dp_attribute(
        dp_id=1,
        attribute_name="irrigation_mode",
        type=t.Bool,
    )
    .enum(
        attribute_name="irrigation_mode",
        cluster_id=TUYA_CLUSTER_ID,
        enum_class=GiexIrrigationMode,
        translation_key="irrigation_mode",
        fallback_name="Irrigation mode",
    )
    .tuya_enum(
        dp_id=107,
        attribute_name="weather_delay",
        enum_class=GiexIrrigationWeatherDelay,
        translation_key="weather_delay",
        fallback_name="Weather delay",
        initially_disabled=True,
    )
    .tuya_sensor(
        dp_id=114,
        attribute_name="irrigation_duration",
        type=t.uint32_t,
        converter=lambda x: giex_string_to_td(x),
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        unit=UnitOfTime.SECONDS,
        translation_key="irrigation_duration",
        fallback_name="Last irrigation duration",
    )
    .tuya_sensor(
        dp_id=101,
        attribute_name="irrigation_start_time",
        type=t.CharacterString,
        converter=lambda x: giex_string_to_ts(x),
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="irrigation_start_time",
        fallback_name="Irrigation start time",
    )
    .tuya_sensor(
        dp_id=102,
        attribute_name="irrigation_end_time",
        type=t.CharacterString,
        converter=lambda x: giex_string_to_ts(x),
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key="irrigation_end_time",
        fallback_name="Irrigation end time",
    )
    .skip_configuration()
)


(
    gx02_base_quirk.clone()
    .applies_to("_TZE200_sh1btabb", "TS0601")
    .tuya_number(
        dp_id=104,
        attribute_name="irrigation_target",
        type=t.uint32_t,
        min_value=0,
        max_value=GIEX_24HRS_AS_MIN,
        step=1,
        translation_key="irrigation_target",
        fallback_name="Irrigation target",
    )
    .tuya_number(
        dp_id=105,
        attribute_name="irrigation_interval",
        min_value=0,
        type=t.uint32_t,
        max_value=GIEX_24HRS_AS_MIN,
        step=1,
        unit=UnitOfTime.MINUTES,
        translation_key="irrigation_interval",
        fallback_name="Irrigation interval",
    )
    .add_to_registry()
)
(
    gx02_base_quirk.clone()
    .applies_to("_TZE200_a7sghmms", "TS0601")
    .applies_to("_TZE204_a7sghmms", "TS0601")
    .applies_to("_TZE200_7ytb3h8u", "TS0601")  # Giex GX02 Var 1
    .applies_to("_TZE204_7ytb3h8u", "TS0601")  # Giex GX02 Var 1
    .applies_to("_TZE284_7ytb3h8u", "TS0601")  # Giex GX02 Var 3
    .tuya_number(
        dp_id=104,
        attribute_name="irrigation_target",
        type=t.uint32_t,
        min_value=0,
        max_value=GIEX_12HRS_AS_SEC,
        step=1,
        translation_key="irrigation_target",
        fallback_name="Irrigation target",
    )
    .tuya_number(
        dp_id=105,
        attribute_name="irrigation_interval",
        type=t.uint32_t,
        min_value=0,
        max_value=GIEX_12HRS_AS_SEC,
        step=1,
        unit=UnitOfTime.SECONDS,
        translation_key="irrigation_interval",
        fallback_name="Irrigation interval",
    )
    .add_to_registry()
)


class GiexIrrigationStatus(t.enum8):
    """Giex Irrigation Status Enum."""

    Manual = 0x00
    Auto = 0x01
    Idle = 0x02


(
    TuyaQuirkBuilder("_TZE284_8zizsafo", "TS0601")  # Giex GX04
    .applies_to("_TZE284_eaet5qt5", "TS0601")  # Insoma SGW08W
    .tuya_battery(dp_id=59, battery_type=BatterySize.AA, battery_qty=4)
    .tuya_switch(
        dp_id=1,
        attribute_name="valve_on_off_1",
        entity_type=EntityType.STANDARD,
        translation_key="valve_on_off_1",
        fallback_name="Valve 1",
    )
    .tuya_switch(
        dp_id=2,
        attribute_name="valve_on_off_2",
        entity_type=EntityType.STANDARD,
        translation_key="valve_on_off_2",
        fallback_name="Valve 2",
    )
    .tuya_number(
        dp_id=13,
        attribute_name="valve_countdown_1",
        type=t.uint16_t,
        device_class=SensorDeviceClass.DURATION,
        unit=UnitOfTime.MINUTES,
        min_value=0,
        max_value=1440,
        step=1,
        translation_key="valve_countdown_1",
        fallback_name="Irrigation time 1",
    )
    .tuya_number(
        dp_id=14,
        attribute_name="valve_countdown_2",
        type=t.uint16_t,
        device_class=SensorDeviceClass.DURATION,
        unit=UnitOfTime.MINUTES,
        min_value=0,
        max_value=1440,
        step=1,
        translation_key="valve_countdown_2",
        fallback_name="Irrigation time 2",
    )
    .tuya_sensor(
        dp_id=25,
        attribute_name="valve_duration_1",
        type=t.uint32_t,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        unit=UnitOfTime.SECONDS,
        entity_type=EntityType.STANDARD,
        translation_key="irrigation_duration_1",
        fallback_name="Irrigation duration 1",
    )
    .tuya_sensor(
        dp_id=26,
        attribute_name="valve_duration_2",
        type=t.uint32_t,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        unit=UnitOfTime.SECONDS,
        entity_type=EntityType.STANDARD,
        translation_key="irriation_duration_2",
        fallback_name="Irrigation duration 2",
    )
    .tuya_enum(
        dp_id=104,
        attribute_name="valve_status_1",
        enum_class=GiexIrrigationStatus,
        entity_platform=EntityPlatform.SENSOR,
        entity_type=EntityType.STANDARD,
        translation_key="valve_status_1",
        fallback_name="Status 1",
    )
    .tuya_enum(
        dp_id=105,
        attribute_name="valve_status_2",
        enum_class=GiexIrrigationStatus,
        entity_platform=EntityPlatform.SENSOR,
        entity_type=EntityType.STANDARD,
        translation_key="valve_status_2",
        fallback_name="Status 2",
    )
    .skip_configuration()
    .add_to_registry()
)


(
    TuyaQuirkBuilder("_TZE200_2wg5qrjy", "TS0601")
    .tuya_onoff(dp_id=1)
    .tuya_battery(dp_id=7, battery_type=BatterySize.AA, battery_qty=2)
    # Water consumed (value comes in deciliters - convert it to liters)
    .tuya_metering(dp_id=5, scale=0.1)
    # Timer time left/remaining (raw value in seconds)
    .tuya_number(
        dp_id=11,
        attribute_name="timer_time_left",
        type=t.uint32_t,
        min_value=1,
        max_value=600,
        step=1,
        multiplier=1 / 60,
        unit=UnitOfTime.MINUTES,
        translation_key="timer_time_left",
        fallback_name="Timer time left",
    )
    # Weather delay
    .tuya_enum(
        dp_id=10,
        attribute_name="weather_delay",
        enum_class=TuyaValveWeatherDelay,
        translation_key="weather_delay",
        fallback_name="Weather delay",
        initially_disabled=True,
    )
    # Timer state - read-only
    .tuya_enum(
        dp_id=12,
        attribute_name="timer_state",
        enum_class=TuyaValveTimerState,
        entity_platform=EntityPlatform.SENSOR,
        entity_type=EntityType.DIAGNOSTIC,
        translation_key="timer_state",
        fallback_name="Timer state",
    )
    # Last valve open duration - read-only (raw value in seconds)
    .tuya_sensor(
        dp_id=15,
        attribute_name="last_valve_open_duration",
        type=t.uint32_t,
        divisor=60,
        entity_type=EntityType.DIAGNOSTIC,
        unit=UnitOfTime.MINUTES,
        translation_key="last_valve_open_duration",
        fallback_name="Last valve open duration",
    )
    .add_to_registry()
)

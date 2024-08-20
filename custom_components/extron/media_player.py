import logging

from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerEntityFeature, \
    MediaPlayerState
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity import DeviceInfo

from custom_components.extron.const import CONF_DEVICE_TYPE, DOMAIN
from custom_components.extron.extron import DeviceType, SurroundSoundProcessor, HDMISwitcher, DeviceInformation, \
    ExtronDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    _LOGGER.info('async_setup_entry')
    _LOGGER.info(entry.data)
    _LOGGER.info('Device type is %s', entry.data[CONF_DEVICE_TYPE])
    _LOGGER.info(DeviceType.SURROUND_SOUND_PROCESSOR.value)

    if entry.data[CONF_DEVICE_TYPE] == DeviceType.SURROUND_SOUND_PROCESSOR.value:
        ssp = SurroundSoundProcessor(entry.data['host'], entry.data['port'], entry.data['password'])
        await ssp.connect()

        # Query device information
        device_information = await ssp.query_device_information()
        _LOGGER.info(device_information)

        async_add_entities([ExtronSurroundSoundProcessor(ssp, device_information)])
    elif entry.data[CONF_DEVICE_TYPE] == DeviceType.HDMI_SWITCHER.value:
        hdmi_switcher = HDMISwitcher(entry.data['host'], entry.data['port'], entry.data['password'])
        await hdmi_switcher.connect()

        # Query device information
        device_information = await hdmi_switcher.query_device_information()
        _LOGGER.info(device_information)

        async_add_entities([ExtronHDMISwitcher(hdmi_switcher, device_information)])
    else:
        _LOGGER.info('configuring NOTHING')


class AbstractExtronMediaPlayerEntity(MediaPlayerEntity):
    def __init__(self, device: ExtronDevice, device_information: DeviceInformation) -> None:
        self._device = device
        self._device_information = device_information
        self._device_class = "receiver"

    @property
    def device_class(self):
        return self._device_class

    @property
    def unique_id(self) -> str | None:
        device_type = self._device.get_device_type()
        mac_address = format_mac(self._device_information.mac_address)

        return f'extron_{device_type.value}_{mac_address}'

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.name,
            manufacturer='Extron',
            model=self._device_information.model_name,
            sw_version=self._device_information.firmware_version,
            serial_number=self._device_information.part_number,
        )

    @property
    def name(self):
        return f'Extron {self._device_information.model_name}'


class ExtronSurroundSoundProcessor(AbstractExtronMediaPlayerEntity):
    def __init__(self, ssp: SurroundSoundProcessor, device_information: DeviceInformation):
        super().__init__(ssp, device_information)
        self._ssp = ssp

        self._state = MediaPlayerState.PLAYING
        self._source = None
        self._source_list = ['1', '2', '3', '4', '5']
        self._volume = None
        self._muted = False

    _attr_supported_features = (
            MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
    )

    @property
    def state(self):
        return self._state

    async def async_update(self):
        self._source = await self._ssp.view_input()
        self._muted = await self._ssp.is_muted()
        volume = await self._ssp.get_volume_level()
        self._volume = volume / 100

    @property
    def volume_level(self):
        return self._volume

    @property
    def volume_step(self):
        return 0.01

    @property
    def is_volume_muted(self):
        return self._muted

    @property
    def source(self):
        return self._source

    @property
    def source_list(self):
        return self._source_list

    def async_select_source(self, source):
        """Select input source"""
        # TODO
        _LOGGER.info(f'Switching to source {source}')

    async def async_mute_volume(self, mute: bool) -> None:
        await self._ssp.mute() if mute else await self._ssp.unmute()

    async def async_set_volume_level(self, volume: float) -> None:
        await self._ssp.set_volume_level(int(volume * 100))

    async def async_volume_up(self) -> None:
        await self._ssp.increment_volume()

    async def async_volume_down(self) -> None:
        await self._ssp.decrement_volume()


class ExtronHDMISwitcher(AbstractExtronMediaPlayerEntity):
    def __init__(self, hdmi_switcher: HDMISwitcher, device_information: DeviceInformation) -> None:
        super().__init__(hdmi_switcher, device_information)
        self._hdmi_switcher = hdmi_switcher

        self._state = MediaPlayerState.PLAYING
        self._source = None

    _attr_supported_features = MediaPlayerEntityFeature.SELECT_SOURCE

    @property
    def state(self):
        return self._state

    async def async_update(self):
        self._source = await self._hdmi_switcher.view_input()

    @property
    def source(self):
        return self._source

    @property
    def source_list(self):
        model_name = self._device_information.model_name
        foo = model_name.split(' ')[0]

        if foo == "SW2":
            return ['1', '2']
        elif foo == "SW4":
            return ['1', '2', '3', '4']
        elif foo == "SW6":
            return ['1', '2', '3', '4', '5', '6']
        else:
            return ['1', '2', '3', '4', '5', '6', '7', '8']

    def async_select_source(self, source):
        """Select input source"""
        # TODO
        _LOGGER.info(f'Switching to source {source}')

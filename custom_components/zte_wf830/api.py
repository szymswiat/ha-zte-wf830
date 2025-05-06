from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from http.client import RemoteDisconnected
import logging
import time
from xml.parsers.expat import ExpatError

# pylint: disable=no-name-in-module
from pydantic import BaseModel
import requests
import xmltodict

from .const import CHANGE_BAND_TIMEOUT, DEFAULT_REQUEST_TIMEOUT

PROTO: str = "http"
TOKEN_COOKIE_NAME: str = "-goahead-session-"


_LOGGER = logging.getLogger(__name__)


class SignalParams(BaseModel):
    strength: int
    network_type: str
    rsrp0: int
    rsrp1: int
    rsrq: int
    sinr: int
    network_status: str
    wan_ip_addr: str


class TransferStatus(BaseModel):
    # all in bytes
    current_download: int
    current_upload: int

    total_download: int
    total_upload: int


class LteBand(str, Enum):
    BAND_1 = "0031003B"
    BAND_3 = "0033003B"
    BAND_7 = "0037003B"
    BAND_20 = "00320030003B"

    @classmethod
    def get_from_band_index(cls, band_index: int) -> LteBand:
        if band_index == 1:
            return cls.BAND_1
        if band_index == 3:
            return cls.BAND_3
        if band_index == 7:
            return cls.BAND_7
        if band_index == 20:
            return cls.BAND_20
        raise ValueError(f"Invalid band index: {band_index}.")


class ZteNode(str, Enum):
    GET_ACTIVE_BANDS = "N_8_38"
    SET_ACTIVE_BANDS = "N_8_36"
    GET_SIGNAL_STRENGTH = "N_8_49"

    GET_NETWORK_TYPE = "N_8_45"
    GET_RSRP0 = "N_8_25"
    GET_RSRP1 = "N_8_26"
    GET_RSRQ = "N_8_22"
    GET_SINR = "N_8_35"
    GET_NETWORK_STATUS = "N_8_46"
    GET_WAN_IP_ADDR = "N_3_45"

    GET_CURRENT_DOWNLOAD = "N_5_58"
    GET_CURRENT_UPLOAD = "N_5_61"

    GET_SERIAL_NUMBER = "N_5_54"

    SET_REBOOT1 = "N_5_66"
    SET_REBOOT2 = "N_5_67"


class ZteCommands(str, Enum):
    NODE_GET = "OAM_MIDWARE_NODE_GET"
    NODEM_SET = "OAM_MIDWARE_NODEM_SET"
    NODE_SET = "OAM_MIDWARE_NODE_SET"

    LIST_FULL = "OAM_MIDWARE_LIST_FULL"


def _api_wprapper(func: Callable):
    def wrap(*args, **kwargs):
        self: ZteWf830ApiClient = args[0]

        while True:
            try:
                return func(*args, **kwargs)
            except ExpatError:
                self.authenticate()
            except requests.exceptions.ConnectionError as err:
                if not isinstance(err.args[0].args[1], RemoteDisconnected):
                    raise err
                time.sleep(0.1)
            except requests.exceptions.ReadTimeout:
                time.sleep(0.1)

    return wrap


class ZteWf830ApiClient:
    """ """

    session: requests.Session

    def __init__(self, host: str, smartadmin_password: str) -> None:
        self.host = host
        self.smartadmin_password = smartadmin_password

    def authenticate(self) -> bool:
        self.session = requests.Session()

        response = self.session.post(
            url=f"{PROTO}://{self.host}/action/login",
            data={
                "username": "smartadmin",
                "password": self.smartadmin_password,
            },
            timeout=DEFAULT_REQUEST_TIMEOUT,
        )

        return not "errString" in response.content.decode()

    @_api_wprapper
    def set_band(self, band: LteBand) -> str:
        response = self.session.get(
            url=f"{PROTO}://{self.host}/_request.xml",
            params={
                "cmd": ZteCommands.NODEM_SET,
                "node": ZteNode.SET_ACTIVE_BANDS,
                "value": ";".join([band]),
            },
            timeout=CHANGE_BAND_TIMEOUT,
        )

        xml_response = xmltodict.parse(response.content)

        return xml_response["data"]["result"]

    @_api_wprapper
    def get_node_value(self, nodes: list[ZteNode]) -> list[str]:
        response = self.session.get(
            url=f"{PROTO}://{self.host}/_request.xml",
            params={
                "cmd": ZteCommands.NODE_GET,
                "node": ";".join(nodes),
            },
            timeout=DEFAULT_REQUEST_TIMEOUT,
        )

        xml_response = xmltodict.parse(response.content)

        return [tag_value.strip(";") for tag_value in xml_response["data"].values()]

    def get_active_bands(self) -> list[LteBand]:
        (value,) = self.get_node_value([ZteNode.GET_ACTIVE_BANDS])
        bands = value.strip(";").split(";")

        return [LteBand.get_from_band_index(int(band)) for band in bands]

    @_api_wprapper
    def reboot(self) -> None:
        self.session.get(
            url=f"{PROTO}://{self.host}/_request.xml",
            params={
                "cmd": ZteCommands.NODE_SET,
                "node": ZteNode.SET_REBOOT1,
                "value": "1",
            },
            timeout=DEFAULT_REQUEST_TIMEOUT,
        )
        self.session.get(
            url=f"{PROTO}://{self.host}/_request.xml",
            params={
                "cmd": ZteCommands.NODE_SET,
                "node": ZteNode.SET_REBOOT2,
                "value": "1",
            },
            timeout=DEFAULT_REQUEST_TIMEOUT,
        )

    @_api_wprapper
    def get_transfer_status(self):
        response = self.session.get(
            url=f"{PROTO}://{self.host}/_request.xml",
            params={
                "cmd": ZteCommands.LIST_FULL,
                "list": "0",
            },
            timeout=DEFAULT_REQUEST_TIMEOUT,
        )

        xml_response = xmltodict.parse(response.content)

        [current_download, current_upload] = self.get_node_value(
            [ZteNode.GET_CURRENT_DOWNLOAD, ZteNode.GET_CURRENT_UPLOAD]
        )

        return TransferStatus(
            current_download=int(current_download),
            current_upload=int(current_upload),
            total_download=xml_response["data"]["list"][0]["L_1"],
            total_upload=xml_response["data"]["list"][0]["L_5"],
        )

    def get_signal_params(self) -> SignalParams:
        node_values = self.get_node_value(
            [
                ZteNode.GET_SIGNAL_STRENGTH,
                ZteNode.GET_NETWORK_TYPE,
                ZteNode.GET_RSRP0,
                ZteNode.GET_RSRP1,
                ZteNode.GET_RSRQ,
                ZteNode.GET_SINR,
                ZteNode.GET_NETWORK_STATUS,
                ZteNode.GET_WAN_IP_ADDR,
            ]
        )
        (
            signal_strength,
            network_type,
            rsrp0,
            rsrp1,
            rsrq,
            sinr,
            network_status,
            wan_ip_addr,
        ) = (value.strip(";") for value in node_values)

        return SignalParams(
            strength=int(signal_strength),
            network_type=network_type,
            rsrp0=int(rsrp0),
            rsrp1=int(rsrp1),
            rsrq=int(rsrq),
            sinr=int(sinr),
            network_status=network_status,
            wan_ip_addr=wan_ip_addr,
        )

    def get_serial_number(self) -> str:
        (serial_number,) = self.get_node_value([ZteNode.GET_SERIAL_NUMBER])

        return serial_number

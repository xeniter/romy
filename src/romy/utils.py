"""Helper functions """

import asyncio
import logging
import sys

import aiohttp

if sys.version_info >= (3, 11):
    async_timeout = asyncio.timeout
else:
    from async_timeout import timeout as async_timeout

_LOGGER = logging.getLogger(__name__)

async def async_query(host: str, port: int, command: str, timeout: int = 3, error_log_level : int = logging.ERROR) -> tuple[bool, str]:
    """Call function to Send a http query."""
    ret, resp, _ = await _async_query(host, port, command, timeout, error_log_level)
    return ret, resp


async def async_query_with_http_status(host: str, port: int, command: str, timeout: int = 3, error_log_level : int = logging.ERROR) -> tuple[bool, str, int]:
    """Call function to Send a http query which returns http status code additionally."""
    ret, resp, http_status = await _async_query(host, port, command, timeout, error_log_level)
    return ret, resp, http_status


async def _async_query(host: str, port: int, command: str, timeout: int, error_log_level : int) -> tuple[bool, str, int]:
    """Send a http query."""

    _LOGGER.debug("async_query host=%s, port=%s, command=%s error_log_level=%s", host, port, command, error_log_level)
    try:
        #websession = async_get_clientsession(hass)
        async with aiohttp.ClientSession() as websession:
            async with async_timeout(timeout):
                url = f"http://{host}:{port}/{command}"
                _LOGGER.debug("requesting url: %s", url)
                webresponse = await websession.get(url)
                _LOGGER.debug("http returned: %s", webresponse.status)

                # if we don't get http ok response return error
                ret = True
                if webresponse.status != 200:
                    ret = False
                response = await webresponse.read()
                response_decoded = response.decode("utf-8")
                _LOGGER.debug("web response: %s", response_decoded)

                return ret, response_decoded, webresponse.status

    except asyncio.TimeoutError:
        _LOGGER.log(error_log_level, "ROMY robot timed out")
        return False, "timeout", 0
    except aiohttp.ClientError as error:
        _LOGGER.log(error_log_level, "Error getting ROMY robot data: %s", error)
        return False, str(error), 0


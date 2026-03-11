#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import getpass
import json
import os
import re
import sys
import tempfile
import time
import uuid as uuidlib
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlencode

import requests

BASE_URL = "https://kyfw.12306.cn"
DEFAULT_COOKIE_FILE = os.path.expanduser("~/.kyfw_12306_cookies.json")
DEFAULT_QR_LOGIN_STATE_FILE = os.path.expanduser("~/.kyfw_12306_qr_login_state.json")
SM4_KEY = "tiekeyuankp12306"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.3.1 Safari/605.1.15"
)
BROWSER_ACCEPT_LANGUAGE = "zh-CN,zh-Hans;q=0.9"
SEAT_CODE_MAP: dict[str, str] = {
    "business": "9",
    "business_class": "9",
    "商务座": "9",
    "特等座": "P",
    "special_class": "P",
    "premier_class": "P",
    "first_class": "M",
    "一等座": "M",
    "premium_first_class": "D",
    "优选一等座": "D",
    "second_class": "O",
    "二等座": "O",
    "second_class_compartment": "S",
    "二等包座": "S",
    "deluxe_soft_sleeper": "6",
    "高级软卧": "6",
    "advanced_soft_sleeper": "A",
    "advanced_emu_sleeper": "A",
    "高级动卧": "A",
    "soft_sleeper": "4",
    "软卧": "4",
    "first_class_sleeper": "I",
    "一等卧": "I",
    "dynamic_sleeper": "F",
    "动卧": "F",
    "hard_sleeper": "3",
    "硬卧": "3",
    "second_class_sleeper": "J",
    "二等卧": "J",
    "soft_seat": "2",
    "软座": "2",
    "hard_seat": "1",
    "硬座": "1",
    "no_seat": "W",
    "standing": "W",
    "无座": "W",
    "wz": "W",
    "other": "H",
    "其他": "H",
}
PRICE_KEY_LABEL_MAP: dict[str, str] = {
    "9": "商务座",
    "A9": "商务座/特等座",
    "P": "特等座",
    "D": "优选一等座",
    "M": "一等座",
    "O": "二等座",
    "S": "二等包座",
    "6": "高级软卧",
    "A": "高级动卧",
    "4": "软卧",
    "F": "动卧",
    "I": "一等卧",
    "3": "硬卧",
    "J": "二等卧",
    "2": "软座",
    "1": "硬座",
    "W": "无座",
    "WZ": "无座",
}
TRANSFER_SEAT_FIELD_LABELS: list[tuple[str, str]] = [
    ("swz_num", "商务座"),
    ("tz_num", "特等座"),
    ("gg_num", "优选一等座"),
    ("zy_num", "一等座"),
    ("ze_num", "二等座"),
    ("gr_num", "高级软卧"),
    ("rw_num", "软卧"),
    ("srrb_num", "动卧"),
    ("yw_num", "硬卧"),
    ("rz_num", "软座"),
    ("yz_num", "硬座"),
    ("wz_num", "无座"),
    ("qt_num", "其他"),
]
CANDIDATE_SEAT_CONFIG: dict[str, dict[str, str]] = {
    "9": {"row_field": "business", "prefix": "SWZ", "hb_seat_code": "9", "label": "商务座"},
    "P": {"row_field": "special_class", "prefix": "TZ", "hb_seat_code": "P", "label": "特等座"},
    "D": {"row_field": "premium_first_class", "prefix": "GG", "hb_seat_code": "D", "label": "优选一等座"},
    "M": {"row_field": "first_class", "prefix": "ZY", "hb_seat_code": "M", "label": "一等座"},
    "O": {"row_field": "second_class", "prefix": "ZE", "hb_seat_code": "O", "label": "二等座"},
    "6": {"row_field": "deluxe_soft_sleeper", "prefix": "GR", "hb_seat_code": "6", "label": "高级软卧"},
    "4": {"row_field": "soft_sleeper", "prefix": "RW", "hb_seat_code": "4", "label": "软卧"},
    "F": {"row_field": "dynamic_sleeper", "prefix": "SRRB", "hb_seat_code": "F", "label": "动卧"},
    "3": {"row_field": "hard_sleeper", "prefix": "YW", "hb_seat_code": "3", "label": "硬卧"},
    "2": {"row_field": "soft_seat", "prefix": "RZ", "hb_seat_code": "2", "label": "软座"},
    "1": {"row_field": "hard_seat", "prefix": "YZ", "hb_seat_code": "1", "label": "硬座"},
}

FK = [0xA3B1BAC6, 0x56AA3350, 0x677D9197, 0xB27022DC]
CK = [
    0x00070E15,
    0x1C232A31,
    0x383F464D,
    0x545B6269,
    0x70777E85,
    0x8C939AA1,
    0xA8AFB6BD,
    0xC4CBD2D9,
    0xE0E7EEF5,
    0xFC030A11,
    0x181F262D,
    0x343B4249,
    0x50575E65,
    0x6C737A81,
    0x888F969D,
    0xA4ABB2B9,
    0xC0C7CED5,
    0xDCE3EAF1,
    0xF8FF060D,
    0x141B2229,
    0x30373E45,
    0x4C535A61,
    0x686F767D,
    0x848B9299,
    0xA0A7AEB5,
    0xBCC3CAD1,
    0xD8DFE6ED,
    0xF4FB0209,
    0x10171E25,
    0x2C333A41,
    0x484F565D,
    0x646B7279,
]
SBOX = [
    0xD6,
    0x90,
    0xE9,
    0xFE,
    0xCC,
    0xE1,
    0x3D,
    0xB7,
    0x16,
    0xB6,
    0x14,
    0xC2,
    0x28,
    0xFB,
    0x2C,
    0x05,
    0x2B,
    0x67,
    0x9A,
    0x76,
    0x2A,
    0xBE,
    0x04,
    0xC3,
    0xAA,
    0x44,
    0x13,
    0x26,
    0x49,
    0x86,
    0x06,
    0x99,
    0x9C,
    0x42,
    0x50,
    0xF4,
    0x91,
    0xEF,
    0x98,
    0x7A,
    0x33,
    0x54,
    0x0B,
    0x43,
    0xED,
    0xCF,
    0xAC,
    0x62,
    0xE4,
    0xB3,
    0x1C,
    0xA9,
    0xC9,
    0x08,
    0xE8,
    0x95,
    0x80,
    0xDF,
    0x94,
    0xFA,
    0x75,
    0x8F,
    0x3F,
    0xA6,
    0x47,
    0x07,
    0xA7,
    0xFC,
    0xF3,
    0x73,
    0x17,
    0xBA,
    0x83,
    0x59,
    0x3C,
    0x19,
    0xE6,
    0x85,
    0x4F,
    0xA8,
    0x68,
    0x6B,
    0x81,
    0xB2,
    0x71,
    0x64,
    0xDA,
    0x8B,
    0xF8,
    0xEB,
    0x0F,
    0x4B,
    0x70,
    0x56,
    0x9D,
    0x35,
    0x1E,
    0x24,
    0x0E,
    0x5E,
    0x63,
    0x58,
    0xD1,
    0xA2,
    0x25,
    0x22,
    0x7C,
    0x3B,
    0x01,
    0x21,
    0x78,
    0x87,
    0xD4,
    0x00,
    0x46,
    0x57,
    0x9F,
    0xD3,
    0x27,
    0x52,
    0x4C,
    0x36,
    0x02,
    0xE7,
    0xA0,
    0xC4,
    0xC8,
    0x9E,
    0xEA,
    0xBF,
    0x8A,
    0xD2,
    0x40,
    0xC7,
    0x38,
    0xB5,
    0xA3,
    0xF7,
    0xF2,
    0xCE,
    0xF9,
    0x61,
    0x15,
    0xA1,
    0xE0,
    0xAE,
    0x5D,
    0xA4,
    0x9B,
    0x34,
    0x1A,
    0x55,
    0xAD,
    0x93,
    0x32,
    0x30,
    0xF5,
    0x8C,
    0xB1,
    0xE3,
    0x1D,
    0xF6,
    0xE2,
    0x2E,
    0x82,
    0x66,
    0xCA,
    0x60,
    0xC0,
    0x29,
    0x23,
    0xAB,
    0x0D,
    0x53,
    0x4E,
    0x6F,
    0xD5,
    0xDB,
    0x37,
    0x45,
    0xDE,
    0xFD,
    0x8E,
    0x2F,
    0x03,
    0xFF,
    0x6A,
    0x72,
    0x6D,
    0x6C,
    0x5B,
    0x51,
    0x8D,
    0x1B,
    0xAF,
    0x92,
    0xBB,
    0xDD,
    0xBC,
    0x7F,
    0x11,
    0xD9,
    0x5C,
    0x41,
    0x1F,
    0x10,
    0x5A,
    0xD8,
    0x0A,
    0xC1,
    0x31,
    0x88,
    0xA5,
    0xCD,
    0x7B,
    0xBD,
    0x2D,
    0x74,
    0xD0,
    0x12,
    0xB8,
    0xE5,
    0xB4,
    0xB0,
    0x89,
    0x69,
    0x97,
    0x4A,
    0x0C,
    0x96,
    0x77,
    0x7E,
    0x65,
    0xB9,
    0xF1,
    0x09,
    0xC5,
    0x6E,
    0xC6,
    0x84,
    0x18,
    0xF0,
    0x7D,
    0xEC,
    0x3A,
    0xDC,
    0x4D,
    0x20,
    0x79,
    0xEE,
    0x5F,
    0x3E,
    0xD7,
    0xCB,
    0x39,
    0x48,
]


def _u32(x: int) -> int:
    return x & 0xFFFFFFFF


def _rotl(x: int, n: int) -> int:
    return _u32((x << n) | (x >> (32 - n)))


def _tau_transform(a: int) -> int:
    return (
        (SBOX[(a >> 24) & 0xFF] << 24)
        | (SBOX[(a >> 16) & 0xFF] << 16)
        | (SBOX[(a >> 8) & 0xFF] << 8)
        | SBOX[a & 0xFF]
    )


def _t_transform1(z: int) -> int:
    b = _tau_transform(z)
    return b ^ _rotl(b, 2) ^ _rotl(b, 10) ^ _rotl(b, 18) ^ _rotl(b, 24)


def _t_transform2(z: int) -> int:
    b = _tau_transform(z)
    return b ^ _rotl(b, 13) ^ _rotl(b, 23)


def _encrypt_round_keys(key: bytes) -> list[int]:
    if len(key) != 16:
        raise ValueError("SM4 key must be 16 bytes")
    mk = [int.from_bytes(key[i : i + 4], "big") for i in range(0, 16, 4)]
    k = [mk[i] ^ FK[i] for i in range(4)]
    keys: list[int] = []
    for i in range(32):
        nxt = _u32(k[i] ^ _t_transform2(k[i + 1] ^ k[i + 2] ^ k[i + 3] ^ CK[i]))
        k.append(nxt)
        keys.append(nxt)
    return keys


def _pkcs7_padding(data: bytes) -> bytes:
    pad = 16 - (len(data) % 16)
    return data + bytes([pad]) * pad


def encrypt_ecb(plaintext: str, key: str) -> str:
    plain = _pkcs7_padding(plaintext.encode("utf-8"))
    round_keys = _encrypt_round_keys(key.encode("utf-8"))
    cipher = bytearray()
    for block_idx in range(0, len(plain), 16):
        block = plain[block_idx : block_idx + 16]
        x = [int.from_bytes(block[i : i + 4], "big") for i in range(0, 16, 4)]
        for i in range(32):
            x.append(_u32(x[i] ^ _t_transform1(x[i + 1] ^ x[i + 2] ^ x[i + 3] ^ round_keys[i])))
        for v in [x[35], x[34], x[33], x[32]]:
            cipher.extend(v.to_bytes(4, "big"))
    return base64.b64encode(cipher).decode("ascii")


def encrypt_12306_password(raw_password: str) -> str:
    if raw_password.startswith("@"):
        return raw_password
    return "@" + encrypt_ecb(raw_password, SM4_KEY)


def parse_json_response(text: str) -> Any:
    body = (text or "").replace("\ufeff", "").strip()
    if not body:
        return {}
    if body.startswith("{") or body.startswith("["):
        return json.loads(body)
    # Handle jsonp: callback({...});
    match = re.match(r"^[^(]+\((.*)\)\s*;?$", body, re.S)
    if match:
        return json.loads(match.group(1))
    raise ValueError(f"Invalid JSON response: {body[:120]}")


def assert_ok(resp: dict[str, Any], field: str = "result_code") -> None:
    if not isinstance(resp, dict):
        raise RuntimeError(f"Unexpected response: {resp!r}")
    code = str(resp.get(field, ""))
    if code not in {"0", "200"}:
        msg = resp.get("result_message") or resp.get("msg") or resp.get("messages") or resp
        raise RuntimeError(f"Request failed ({field}={code}): {msg}")


def derive_qr_login_state_file(cookie_file: str | None) -> Path:
    if cookie_file:
        base = Path(cookie_file).expanduser()
        return base.with_name(base.name + ".qrlogin.json")
    return Path(DEFAULT_QR_LOGIN_STATE_FILE).expanduser()


def load_qr_login_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def save_qr_login_state(path: Path, payload: dict[str, Any]) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


class KyfwClient:
    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: int = 15,
        cookie_file: str | None = None,
        browser_headers: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cookie_file = cookie_file
        self.browser_headers = browser_headers
        self.session = requests.Session()
        session_headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        }
        if self.browser_headers:
            session_headers.update(
                {
                    "Accept-Language": BROWSER_ACCEPT_LANGUAGE,
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "If-Modified-Since": "0",
                }
            )
        self.session.headers.update(session_headers)
        self._station_index: dict[str, str] | None = None
        self._load_cookies()

    def _load_cookies(self) -> None:
        if not self.cookie_file:
            return
        path = Path(self.cookie_file).expanduser()
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            cookie_items: list[dict[str, Any]]
            if isinstance(payload, dict) and isinstance(payload.get("cookies"), list):
                cookie_items = payload["cookies"]
            elif isinstance(payload, list):
                cookie_items = payload
            else:
                return

            jar = requests.cookies.RequestsCookieJar()
            for item in cookie_items:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                value = item.get("value")
                if not name or value is None:
                    continue
                kwargs: dict[str, Any] = {
                    "name": str(name),
                    "value": str(value),
                    "path": item.get("path", "/"),
                    "secure": bool(item.get("secure", False)),
                }
                if item.get("domain"):
                    kwargs["domain"] = item["domain"]
                if item.get("expires") is not None:
                    kwargs["expires"] = int(item["expires"])
                rest = item.get("rest")
                if isinstance(rest, dict):
                    kwargs["rest"] = rest
                jar.set_cookie(requests.cookies.create_cookie(**kwargs))
            self.session.cookies.update(jar)
        except Exception:
            # Cookie file is best-effort.
            return

    def _save_cookies(self) -> None:
        if not self.cookie_file:
            return
        path = Path(self.cookie_file).expanduser()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            cookie_items: list[dict[str, Any]] = []
            for c in self.session.cookies:
                cookie_items.append(
                    {
                        "name": c.name,
                        "value": c.value,
                        "domain": c.domain,
                        "path": c.path,
                        "secure": bool(c.secure),
                        "expires": c.expires,
                        "rest": dict(getattr(c, "_rest", {}) or {}),
                    }
                )
            payload = {"version": 1, "cookies": cookie_items}
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        except Exception:
            # Cookie file is best-effort.
            return

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        referer: str | None = None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if self.browser_headers:
            headers.update(
                {
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Dest": "empty",
                }
            )
        if referer:
            headers["Referer"] = self._url(referer)
        if method.upper() == "POST":
            headers["Origin"] = self.base_url
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"

        resp = self.session.request(
            method=method.upper(),
            url=self._url(path),
            params=params,
            data=data,
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "").lower()
        body = resp.text or ""
        if "html" in content_type and "<!doctype html" in body.lower():
            final_url = resp.url
            if "error.html" in final_url:
                raise RuntimeError(
                    "12306 返回 error.html，通常是触发了风控或访问限制。"
                    "请在可访问 12306 的网络环境重试，或重新登录，或降低请求频率。"
                )
            raise RuntimeError(f"接口返回 HTML 页面而非 JSON: {final_url}")
        parsed = parse_json_response(resp.text)
        self._save_cookies()
        return parsed

    def _request_text(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        referer: str | None = None,
    ) -> str:
        headers: dict[str, str] = {}
        if self.browser_headers:
            headers.update(
                {
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Dest": "empty",
                }
            )
        if referer:
            headers["Referer"] = self._url(referer)
        if method.upper() == "POST":
            headers["Origin"] = self.base_url
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        resp = self.session.request(
            method=method.upper(),
            url=self._url(path),
            params=params,
            data=data,
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        final_url = resp.url
        if "error.html" in final_url:
            raise RuntimeError(
                "12306 返回 error.html，通常是触发了风控或访问限制。"
                "请在可访问 12306 的网络环境重试，或重新登录，或降低请求频率。"
            )
        self._save_cookies()
        return resp.text or ""

    @staticmethod
    def _pick_first_non_empty(data: dict[str, Any], keys: tuple[str, ...]) -> Any | None:
        for key in keys:
            if key not in data:
                continue
            value = data.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    continue
            return value
        return None

    @classmethod
    def _extract_user_profile(cls, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        data = payload.get("data") if isinstance(payload.get("data"), dict) else None
        sources: list[dict[str, Any]] = []
        if isinstance(data, dict):
            sources.append(data)
        sources.append(payload)

        field_map: dict[str, tuple[str, ...]] = {
            "name": ("name", "real_name", "display_name"),
            "username": ("user_name", "username", "login_name"),
            "email": ("ei_email", "email"),
            "mobile": ("mobile_no", "mobile", "phone", "phone_no"),
            "id_no": ("id_no", "id_card_no"),
            "born_date": ("born_date",),
            "user_status": ("user_status",),
        }
        profile: dict[str, Any] = {}
        for out_key, in_keys in field_map.items():
            for source in sources:
                value = cls._pick_first_non_empty(source, in_keys)
                if value is not None:
                    profile[out_key] = value
                    break
        return profile

    @staticmethod
    def _merge_user_profile(
        base: dict[str, Any] | None,
        incoming: dict[str, Any] | None,
    ) -> dict[str, Any]:
        merged = dict(base or {})
        for key, value in (incoming or {}).items():
            if key not in merged or merged[key] in (None, ""):
                merged[key] = value
        return merged

    def check_login_status(self) -> dict[str, Any]:
        result: dict[str, Any] = {"logged_in": False, "cookie_file": self.cookie_file}
        try:
            conf = self._request(
                "POST",
                "/otn/login/conf",
                referer="/otn/view/index.html",
            )
            result["conf"] = conf
            data = conf.get("data") if isinstance(conf, dict) else None
            if isinstance(data, dict):
                is_login = data.get("is_login")
                if isinstance(is_login, str):
                    result["logged_in"] = is_login.upper() == "Y"
                elif isinstance(is_login, bool):
                    result["logged_in"] = is_login
                elif any(data.get(k) for k in ("born_date", "ei_email", "name", "user_name")):
                    result["logged_in"] = True
            conf_user = self._extract_user_profile(conf)
            if conf_user:
                result["user"] = self._merge_user_profile(
                    result.get("user") if isinstance(result.get("user"), dict) else None,
                    conf_user,
                )
        except Exception as e:  # noqa: BLE001
            result["conf_error"] = str(e)

        if result["logged_in"] and isinstance(result.get("user"), dict) and result["user"]:
            return result

        try:
            info = self._request(
                "POST",
                "/otn/index/initMy12306Api",
                referer="/otn/view/index.html",
            )
            result["initMy12306Api"] = info
            data = info.get("data") if isinstance(info, dict) else None
            if isinstance(data, dict) and data.get("user_status") is not None:
                result["logged_in"] = True
            info_user = self._extract_user_profile(info)
            if info_user:
                result["user"] = self._merge_user_profile(
                    result.get("user") if isinstance(result.get("user"), dict) else None,
                    info_user,
                )
        except Exception as e:  # noqa: BLE001
            result["init_api_error"] = str(e)

        return result

    def check_login_verify(self, username: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/passport/web/checkLoginVerify",
            data={"username": username, "appid": "otn"},
            referer="/otn/resources/login.html",
        )

    def send_sms_code(self, username: str, id_last4: str) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9Xx]{4}", id_last4):
            raise ValueError("--id-last4 必须是证件号后4位（数字或X）")
        return self._request(
            "POST",
            "/passport/web/getMessageCode",
            data={"appid": "otn", "username": username, "castNum": id_last4.upper()},
            referer="/otn/resources/login.html",
        )

    def create_qr_login(self, *, appid: str = "otn") -> dict[str, Any]:
        appid = (appid or "otn").strip() or "otn"
        self.session.get(self._url("/otn/resources/login.html"), timeout=self.timeout)
        resp = self._request(
            "POST",
            "/passport/web/create-qr64",
            data={"appid": appid},
            referer="/otn/resources/login.html",
        )
        code = str(resp.get("result_code", ""))
        if code != "0":
            raise RuntimeError(f"生成二维码失败(result_code={code}): {self._extract_error_message(resp)}")
        uuid = str(resp.get("uuid") or "").strip()
        image = str(resp.get("image") or "").strip()
        if not uuid or not image:
            raise RuntimeError(f"create-qr64 返回缺少 uuid/image: {resp}")
        return {
            "step": "qr_created",
            "appid": appid,
            "uuid": uuid,
            "image": image,
            "result_code": code,
            "result_message": resp.get("result_message") or "",
            "createQr64": resp,
        }

    def check_qr_login(
        self,
        *,
        uuid: str,
        appid: str = "otn",
        finalize: bool = True,
    ) -> dict[str, Any]:
        uuid = (uuid or "").strip()
        if not uuid:
            raise ValueError("uuid 不能为空")
        appid = (appid or "otn").strip() or "otn"

        check_resp = self._request(
            "POST",
            "/passport/web/checkqr",
            data={"uuid": uuid, "appid": appid},
            referer="/otn/resources/login.html",
        )
        result_code = str(check_resp.get("result_code", ""))
        result_message = str(check_resp.get("result_message") or "")
        qr_status_map = {
            "0": "waiting_scan",
            "1": "waiting_confirm",
            "2": "authorized",
            "3": "expired",
            "5": "error",
        }
        qr_status = qr_status_map.get(result_code, "unknown")
        out: dict[str, Any] = {
            "step": "checked",
            "uuid": uuid,
            "appid": appid,
            "result_code": result_code,
            "result_message": result_message,
            "qr_status": qr_status,
            "checkqr": check_resp,
        }
        if result_code != "2":
            if result_code in {"0", "1"}:
                out["step"] = "pending"
            elif result_code == "3":
                out["step"] = "expired"
            elif result_code == "5":
                out["step"] = "error"
            else:
                out["step"] = "unknown"
            return out

        if not finalize:
            out["step"] = "authorized"
            return out

        # Match browser flow: authorized QR -> passport ticket -> uamtk -> uamauthclient.
        self.session.get(
            self._url("/otn/passport?redirect=/otn/login/userLogin"),
            timeout=self.timeout,
        )
        uamtk_resp = self._request(
            "POST",
            "/passport/web/auth/uamtk",
            data={"appid": appid},
            referer="/otn/passport?redirect=/otn/login/userLogin",
        )
        uamtk_code = str(uamtk_resp.get("result_code", ""))
        if uamtk_code != "0":
            raise RuntimeError(
                "扫码已确认，但 auth/uamtk 未通过: "
                f"result_code={uamtk_code}, message={self._extract_error_message(uamtk_resp)}"
            )
        tk = uamtk_resp.get("newapptk") or uamtk_resp.get("apptk")
        if not tk:
            raise RuntimeError(f"auth/uamtk 返回中缺少 tk: {uamtk_resp}")

        uamauth_resp = self._request(
            "POST",
            "/otn/uamauthclient",
            data={"tk": tk},
            referer="/otn/passport?redirect=/otn/login/userLogin",
        )
        assert_ok(uamauth_resp, "result_code")
        login_status = self.check_login_status()
        out.update(
            {
                "step": "logged_in",
                "uamtk": uamtk_resp,
                "uamauthclient": uamauth_resp,
                "login_status": login_status,
            }
        )
        if not login_status.get("logged_in"):
            out["warning"] = "uamauthclient 已返回成功，但 conf/initMy12306Api 尚未确认登录态。"
        return out

    def login(
        self,
        *,
        username: str,
        password: str,
        id_last4: str | None = None,
        sms_code: str | None = None,
        send_sms: bool = False,
    ) -> dict[str, Any]:
        verify = self.check_login_verify(username)
        if str(verify.get("result_code")) != "0":
            raise RuntimeError(f"checkLoginVerify 失败: {verify}")

        login_check_code = str(verify.get("login_check_code", ""))
        if login_check_code == "3" and send_sms:
            if not id_last4:
                raise RuntimeError("当前账号需要短信验证，请提供 --id-last4")
            sms_resp = self.send_sms_code(username, id_last4)
            if str(sms_resp.get("result_code")) != "0":
                if str(sms_resp.get("result_code")) == "11":
                    raise RuntimeError(
                        "发送短信验证码失败(result_code=11)：用户名与证件后4位不匹配。"
                        "请优先使用12306“登录用户名”（不要用手机号/邮箱别名），"
                        "并确认 --id-last4 是该账号绑定证件号后4位。"
                    )
                raise RuntimeError(f"发送短信验证码失败: {sms_resp}")
            return {
                "step": "sms_sent",
                "message": sms_resp.get("result_message") or "短信验证码已发送，请使用 --sms-code 重试登录。",
                "checkLoginVerify": verify,
                "getMessageCode": sms_resp,
            }
        if send_sms and login_check_code != "3":
            raise RuntimeError(
                f"当前账号登录校验类型为 {login_check_code}，不需要短信验证码发送。"
            )

        if login_check_code == "3":
            if not sms_code:
                raise RuntimeError("当前账号需要短信验证码，请传入 --sms-code（6位）")
            if not re.fullmatch(r"\d{6}", sms_code):
                raise RuntimeError("--sms-code 必须是6位数字")

        if login_check_code in {"1", "2"}:
            raise RuntimeError(
                f"当前账号登录校验类型为 {login_check_code}（滑块或图片验证码），"
                "此脚本暂不自动处理该校验。"
            )

        form_data = {
            "sessionId": "",
            "sig": "",
            "if_check_slide_passcode_token": "",
            "scene": "",
            "checkMode": "0" if login_check_code == "3" else "",
            "randCode": sms_code or "",
            "username": username,
            "password": encrypt_12306_password(password),
            "appid": "otn",
        }
        login_resp = self._request(
            "POST",
            "/passport/web/login",
            data=form_data,
            referer="/otn/resources/login.html",
        )
        assert_ok(login_resp, "result_code")

        uamtk_resp = self._request(
            "POST",
            "/passport/web/auth/uamtk",
            data={"appid": "otn"},
            referer="/otn/passport?redirect=/otn/login/userLogin",
        )
        assert_ok(uamtk_resp, "result_code")
        tk = uamtk_resp.get("newapptk") or uamtk_resp.get("apptk")
        if not tk:
            raise RuntimeError(f"auth/uamtk 返回中缺少 tk: {uamtk_resp}")

        uamauth_resp = self._request(
            "POST",
            "/otn/uamauthclient",
            data={"tk": tk},
            referer="/otn/passport?redirect=/otn/login/userLogin",
        )
        assert_ok(uamauth_resp, "result_code")
        self._save_cookies()

        return {
            "step": "logged_in",
            "checkLoginVerify": verify,
            "login": login_resp,
            "uamtk": uamtk_resp,
            "uamauthclient": uamauth_resp,
        }

    def query_my_order_no_complete(self) -> dict[str, Any]:
        return self._request(
            "POST",
            "/otn/queryOrder/queryMyOrderNoComplete",
            data={"_json_att": ""},
            referer="/otn/view/train_order.html",
        )

    def query_my_order(
        self,
        *,
        query_where: str = "G",
        start_date: str | None = None,
        end_date: str | None = None,
        page_index: int = 0,
        page_size: int = 8,
        query_type: int = 1,
        train_name: str = "",
    ) -> dict[str, Any]:
        end = dt.date.today() if end_date is None else dt.date.fromisoformat(end_date)
        start = end - dt.timedelta(days=30) if start_date is None else dt.date.fromisoformat(start_date)
        data = {
            "come_from_flag": "my_order",
            "pageIndex": str(page_index),
            "pageSize": str(page_size),
            "query_where": query_where,
            "queryStartDate": start.isoformat(),
            "queryEndDate": end.isoformat(),
            "queryType": str(query_type),
            "sequeue_train_name": train_name,
        }
        return self._request(
            "POST",
            "/otn/queryOrder/queryMyOrder",
            data=data,
            referer="/otn/view/train_order.html",
        )

    def query_candidate_queue(self) -> dict[str, Any]:
        self.session.get(self._url("/otn/view/lineUp_order.html"), timeout=self.timeout)
        data = self._request(
            "POST",
            "/otn/afterNateOrder/queryQueue",
            data={},
            referer="/otn/view/lineUp_order.html",
        )
        if str(data.get("httpstatus", "200")) != "200" or data.get("status") is False:
            raise RuntimeError(f"查询候补排队状态失败: {data}")
        payload = data.get("data")
        if not isinstance(payload, dict):
            raise RuntimeError(f"候补排队返回结构异常: {data}")
        return {
            "queue": {
                "flag": payload.get("flag"),
                "status": payload.get("status"),
                "is_async": payload.get("isAsync"),
            },
            "raw": data,
        }

    def query_candidate_orders(
        self,
        *,
        processed: bool = False,
        page_no: int = 0,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        start = dt.date.today() if start_date is None else dt.date.fromisoformat(start_date)
        end = start + dt.timedelta(days=29) if end_date is None else dt.date.fromisoformat(end_date)
        if start > end:
            raise ValueError("--start-date 不能晚于 --end-date")
        path = (
            "/otn/afterNateOrder/queryProcessedHOrder"
            if processed
            else "/otn/afterNateOrder/queryUnHonourHOrder"
        )

        self.session.get(self._url("/otn/view/lineUp_order.html"), timeout=self.timeout)
        data = self._request(
            "POST",
            path,
            data={
                "page_no": str(max(0, page_no)),
                "query_start_date": start.isoformat(),
                "query_end_date": end.isoformat(),
            },
            referer="/otn/view/lineUp_order.html",
        )
        if str(data.get("httpstatus", "200")) != "200" or data.get("status") is False:
            raise RuntimeError(f"查询候补订单失败: {data}")
        payload = data.get("data")
        rows = payload.get("list") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError(f"候补订单返回结构异常: {data}")

        parsed: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            needs = item.get("needs")
            need = needs[0] if isinstance(needs, list) and needs and isinstance(needs[0], dict) else {}
            passengers = item.get("passengers")
            passenger_names: list[str] = []
            if isinstance(passengers, list):
                for p in passengers:
                    if isinstance(p, dict) and p.get("passenger_name"):
                        passenger_names.append(str(p.get("passenger_name")))
            parsed.append(
                {
                    "reserve_no": item.get("reserve_no"),
                    "sequence_no": item.get("sequence_no"),
                    "status_name": item.get("status_name"),
                    "status_code": item.get("status_code"),
                    "reserve_time": item.get("reserve_time"),
                    "realize_limit_time": item.get("realize_limit_time"),
                    "prepay_amount": item.get("prepay_amount"),
                    "ticket_price": item.get("ticket_price"),
                    "refundable": item.get("refundable"),
                    "train_code": need.get("board_train_code"),
                    "train_date": need.get("train_date"),
                    "from_station": need.get("from_station_name"),
                    "to_station": need.get("to_station_name"),
                    "start_time": need.get("start_time"),
                    "arrive_time": need.get("arrive_time"),
                    "seat_name": need.get("seat_name"),
                    "passengers": passenger_names,
                }
            )
        return {
            "query": {
                "type": "processed" if processed else "unhonour",
                "page_no": str(max(0, page_no)),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
            "rows": parsed,
            "raw": data,
        }

    @staticmethod
    def _extract_error_message(resp: dict[str, Any]) -> str:
        if not isinstance(resp, dict):
            return str(resp)
        data = resp.get("data") if isinstance(resp.get("data"), dict) else {}
        for key in ("msg", "errMsg", "message", "result_message"):
            value = data.get(key)
            if value:
                return str(value)
        messages = resp.get("messages")
        if isinstance(messages, list) and messages:
            return str(messages[0])
        result_message = resp.get("result_message")
        if result_message:
            return str(result_message)
        return str(resp)

    def submit_candidate_order(
        self,
        *,
        train_date: str,
        from_station: str,
        to_station: str,
        train_code: str,
        seat: str,
        purpose_codes: str = "ADULT",
        endpoint: str = "queryG",
        force: bool = False,
    ) -> dict[str, Any]:
        seat_code = self.resolve_seat_code(seat)
        seat_cfg = CANDIDATE_SEAT_CONFIG.get(seat_code)
        if seat_cfg is None:
            supported = ", ".join(sorted(CANDIDATE_SEAT_CONFIG.keys()))
            raise RuntimeError(
                f"席别 {seat}({seat_code}) 暂不支持候补提交。"
                f"当前支持席别代码: {supported}"
            )

        left_ticket = self.query_left_ticket(
            train_date=train_date,
            from_station=from_station,
            to_station=to_station,
            purpose_codes=purpose_codes,
            endpoint=endpoint,
        )
        train_row = self._find_train_row(left_ticket.get("rows", []), train_code)
        seat_value = str(train_row.get(seat_cfg["row_field"], "--") or "--").strip() or "--"
        if seat_value != "无" and not force:
            raise RuntimeError(
                f"当前车次 {train_code} 的 {seat_cfg['label']} 余票为 {seat_value}，"
                "默认仅在余票为“无”时提交候补。若需强制尝试可加 --force。"
            )
        if str(train_row.get("houbu_train_flag") or "").strip() != "1":
            raise RuntimeError(
                f"车次 {train_code} 当前不支持该席别候补（houbu_train_flag={train_row.get('houbu_train_flag')}）。"
            )
        secret_str = str(train_row.get("secret_str") or "").strip()
        if not secret_str:
            raise RuntimeError("余票数据中缺少 secret_str，无法提交候补。")

        check_user_resp = self.check_user()
        check_user_data = check_user_resp.get("data") if isinstance(check_user_resp, dict) else None
        if (
            str(check_user_resp.get("httpstatus", "200")) != "200"
            or check_user_resp.get("status") is False
            or (isinstance(check_user_data, dict) and check_user_data.get("flag") is False)
        ):
            raise RuntimeError(f"checkUser 失败: {check_user_resp}")

        secret_list = f"{secret_str}#{seat_cfg['hb_seat_code']}|"
        submit = self._request(
            "POST",
            "/otn/afterNate/submitOrderRequest",
            data={"secretList": secret_list},
            referer="/otn/leftTicket/init",
        )

        data = submit.get("data") if isinstance(submit, dict) else None
        if isinstance(data, dict) and data.get("flag"):
            return {
                "step": "submitted",
                "train": train_row,
                "seat_code": seat_code,
                "seat_name": seat_cfg["label"],
                "seat_status": seat_value,
                "secret_list": secret_list,
                "checkUser": check_user_resp,
                "submitOrderRequest": submit,
                "next_url": self._url("/otn/view/lineUp_toPay.html"),
            }

        if isinstance(data, dict) and data.get("faceCheck"):
            return {
                "step": "face_check_required",
                "train": train_row,
                "seat_code": seat_code,
                "seat_name": seat_cfg["label"],
                "seat_status": seat_value,
                "secret_list": secret_list,
                "checkUser": check_user_resp,
                "submitOrderRequest": submit,
                "face_check_code": data.get("faceCheck"),
                "is_show_qrcode": data.get("is_show_qrcode"),
            }

        raise RuntimeError(f"提交候补失败: {self._extract_error_message(submit)}")

    def cancel_candidate_order(self, *, reserve_no: str) -> dict[str, Any]:
        reserve_no = reserve_no.strip()
        if not reserve_no:
            raise ValueError("--reserve-no 不能为空")

        self.session.get(self._url("/otn/view/lineUp_order.html"), timeout=self.timeout)
        check_resp = self._request(
            "POST",
            "/otn/afterNateOrder/reserveReturnCheck",
            data={"sequence_no": reserve_no},
            referer="/otn/view/lineUp_order.html",
        )
        check_data = check_resp.get("data") if isinstance(check_resp, dict) else None
        can_reserve_return = isinstance(check_data, dict) and bool(check_data.get("flag"))
        out: dict[str, Any] = {
            "reserve_no": reserve_no,
            "reserveReturnCheck": check_resp,
        }

        if can_reserve_return:
            reserve_return_resp = self._request(
                "POST",
                "/otn/afterNateOrder/reserveReturn",
                data={"sequence_no": reserve_no},
                referer="/otn/view/lineUp_order.html",
            )
            out["reserveReturn"] = reserve_return_resp
            reserve_return_data = (
                reserve_return_resp.get("data") if isinstance(reserve_return_resp, dict) else None
            )
            if isinstance(reserve_return_data, dict) and reserve_return_data.get("flag"):
                out["step"] = "cancelled"
                out["method"] = "reserveReturn"
                return out

        cancel_not_complete_resp = self._request(
            "POST",
            "/otn/afterNateOrder/cancelNotComplete",
            data={"reserve_no": reserve_no},
            referer="/otn/view/lineUp_payConfirm.html",
        )
        out["cancelNotComplete"] = cancel_not_complete_resp
        cancel_not_complete_data = (
            cancel_not_complete_resp.get("data") if isinstance(cancel_not_complete_resp, dict) else None
        )
        if isinstance(cancel_not_complete_data, dict) and cancel_not_complete_data.get("flag"):
            out["step"] = "cancelled"
            out["method"] = "cancelNotComplete"
            return out

        raise RuntimeError(
            "取消候补订单失败: "
            f"{self._extract_error_message(cancel_not_complete_resp)}"
        )

    def _load_station_index(self) -> dict[str, str]:
        if self._station_index is not None:
            return self._station_index
        url = self._url("/otn/resources/js/framework/station_name.js")
        text = self.session.get(url, timeout=self.timeout).text
        match = re.search(r"var\s+station_names\s*=\s*'([^']+)'", text)
        if not match:
            raise RuntimeError("解析 station_name.js 失败")
        raw = match.group(1).strip("@")

        index: dict[str, str] = {}
        for row in raw.split("@"):
            parts = row.split("|")
            if len(parts) < 3:
                continue
            station_name = parts[1]
            telecode = parts[2].upper()
            pinyin = parts[3] if len(parts) > 3 else ""
            short = parts[4] if len(parts) > 4 else ""
            index[station_name] = telecode
            index[station_name.lower()] = telecode
            if pinyin:
                index[pinyin.lower()] = telecode
            if short:
                index[short.lower()] = telecode
            index[telecode] = telecode
            index[telecode.lower()] = telecode
        self._station_index = index
        return index

    def station_to_code(self, station: str) -> str:
        if re.fullmatch(r"[A-Za-z]{3}", station.strip()):
            return station.strip().upper()
        index = self._load_station_index()
        key = station.strip()
        if key in index:
            return index[key]
        lower = key.lower()
        if lower in index:
            return index[lower]
        raise RuntimeError(f"未知车站: {station}")

    @staticmethod
    def _seat(fields: list[str], idx: int) -> str:
        if idx < len(fields) and fields[idx]:
            return fields[idx]
        return "--"

    def query_left_ticket(
        self,
        *,
        train_date: str,
        from_station: str,
        to_station: str,
        purpose_codes: str = "ADULT",
        endpoint: str = "queryG",
    ) -> dict[str, Any]:
        dt.date.fromisoformat(train_date)
        from_code = self.station_to_code(from_station)
        to_code = self.station_to_code(to_station)
        # Warm up left-ticket cookies/session before querying API.
        self.session.get(self._url("/otn/leftTicket/init"), timeout=self.timeout)
        data = self._request(
            "GET",
            f"/otn/leftTicket/{endpoint}",
            params={
                "leftTicketDTO.train_date": train_date,
                "leftTicketDTO.from_station": from_code,
                "leftTicketDTO.to_station": to_code,
                "purpose_codes": purpose_codes,
            },
            referer="/otn/leftTicket/init",
        )
        if str(data.get("httpstatus", "200")) != "200":
            raise RuntimeError(f"查询余票失败: {data}")
        payload = data.get("data", {})
        code_map = payload.get("map", {})
        rows = payload.get("result", [])
        parsed: list[dict[str, Any]] = []
        for row in rows:
            parts = row.split("|")
            if len(parts) < 33:
                continue
            item = {
                "secret_str": parts[0],
                "button_text_info": parts[1] if len(parts) > 1 else "",
                "train_no": parts[2],
                "train_code": parts[3],
                "from_station_code": parts[6],
                "to_station_code": parts[7],
                "from_station": code_map.get(parts[6], parts[6]),
                "to_station": code_map.get(parts[7], parts[7]),
                "start_time": parts[8],
                "arrive_time": parts[9],
                "duration": parts[10],
                "can_web_buy": parts[11],
                "yp_info": parts[12],
                "start_train_date": parts[13],
                "location_code": parts[15],
                "from_station_no": parts[16],
                "to_station_no": parts[17],
                "controlled_train_flag": parts[19] if len(parts) > 19 else "",
                "premium_first_class": self._seat(parts, 20),
                "deluxe_soft_sleeper": self._seat(parts, 21),
                "other": self._seat(parts, 22),
                "business": self._seat(parts, 32),
                "special_class": self._seat(parts, 25),
                "first_class": self._seat(parts, 31),
                "second_class": self._seat(parts, 30),
                "second_class_compartment": self._seat(parts, 27),
                "soft_sleeper": self._seat(parts, 23),
                "dynamic_sleeper": self._seat(parts, 33),
                "hard_sleeper": self._seat(parts, 28),
                "soft_seat": self._seat(parts, 24),
                "hard_seat": self._seat(parts, 29),
                "no_seat": self._seat(parts, 26),
                "yp_ex": parts[34] if len(parts) > 34 else "",
                "seat_types": parts[35] if len(parts) > 35 else "",
                "houbu_train_flag": parts[37] if len(parts) > 37 else "",
                "houbu_seat_limit": parts[38] if len(parts) > 38 else "",
                "yp_info_new": parts[39] if len(parts) > 39 else "",
            }
            price_data = self._parse_ticket_price_from_yp_info(
                str(item.get("yp_info_new") or item.get("yp_info") or "")
            )
            if price_data:
                item["ticket_price"] = price_data
                item["ticket_price_text"] = self._format_ticket_price(price_data)
            parsed.append(item)
        return {
            "query": {
                "date": train_date,
                "from_station": from_station,
                "to_station": to_station,
                "from_code": from_code,
                "to_code": to_code,
                "endpoint": endpoint,
                "purpose_codes": purpose_codes,
            },
            "rows": parsed,
            "raw": data,
        }

    def query_ticket_price(
        self,
        *,
        train_no: str,
        from_station_no: str,
        to_station_no: str,
        seat_types: str,
        train_date: str,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/otn/leftTicket/queryTicketPrice",
            params={
                "train_no": train_no,
                "from_station_no": from_station_no,
                "to_station_no": to_station_no,
                "seat_types": seat_types,
                "train_date": train_date,
            },
            referer="/otn/leftTicket/init",
        )

    @staticmethod
    def _format_ticket_price(price_data: dict[str, Any]) -> str:
        pairs: list[str] = []
        for key, value in price_data.items():
            if key in {"OT", "train_no"}:
                continue
            if key == "9" and "A9" in price_data:
                continue
            text = str(value or "").strip()
            if not text:
                continue
            if not text.startswith("¥") and re.fullmatch(r"\d+", text):
                text = f"¥{int(text) / 10:.1f}"
            label = PRICE_KEY_LABEL_MAP.get(key, key)
            pairs.append(f"{label}={text}")
        return ", ".join(pairs)

    @staticmethod
    def _parse_ticket_price_from_yp_info(yp_info: str) -> dict[str, str]:
        text = str(yp_info or "").strip()
        if not text:
            return {}
        seat_codes = sorted(
            [code for code in PRICE_KEY_LABEL_MAP if code != "OT"],
            key=len,
            reverse=True,
        )
        prices: dict[str, str] = {}
        idx = 0
        while idx < len(text):
            matched = False
            for seat_code in seat_codes:
                if not text.startswith(seat_code, idx):
                    continue
                seg_start = idx + len(seat_code)
                seg_end = seg_start + 9
                if seg_end > len(text):
                    continue
                seg = text[seg_start:seg_end]
                if not seg.isdigit():
                    continue
                amount_text = seg[:5]
                flag_text = seg[5:]
                normalized_code = "A9" if seat_code == "9" else seat_code
                amount = f"¥{int(amount_text) / 10:.1f}"
                if normalized_code not in prices:
                    prices[normalized_code] = amount
                if normalized_code == "W" and "WZ" not in prices:
                    prices["WZ"] = amount
                # 常见场景: O/1 的 3xxx 标记代表无座价格，补齐 WZ 便于统一展示。
                if flag_text.startswith("3") and normalized_code in {"O", "1"} and "WZ" not in prices:
                    prices["WZ"] = amount
                idx = seg_end
                matched = True
                break
            if not matched:
                idx += 1
        return prices

    @staticmethod
    def _extract_transfer_leg_seats(leg: dict[str, Any]) -> dict[str, str]:
        seats: dict[str, str] = {}
        for field, label in TRANSFER_SEAT_FIELD_LABELS:
            value = str(leg.get(field, "--") or "--").strip() or "--"
            if value == "--":
                continue
            seats[label] = value
        return seats

    @staticmethod
    def _format_transfer_leg_seats(seats: dict[str, str]) -> str:
        if not seats:
            return "--"
        return ", ".join(f"{label}={value}" for label, value in seats.items())

    def query_transfer_ticket(
        self,
        *,
        train_date: str,
        from_station: str,
        to_station: str,
        middle_station: str = "",
        result_index: int = 0,
        can_query: str = "Y",
        is_show_wz: str = "N",
        purpose_codes: str = "00",
        channel: str = "E",
        endpoint: str = "queryG",
    ) -> dict[str, Any]:
        dt.date.fromisoformat(train_date)
        can_query = can_query.strip().upper() or "Y"
        is_show_wz = is_show_wz.strip().upper() or "N"
        if can_query not in {"Y", "N"}:
            raise ValueError("--can-query 仅支持 Y/N")
        if is_show_wz not in {"Y", "N"}:
            raise ValueError("--show-wz 仅支持 Y/N")
        from_code = self.station_to_code(from_station)
        to_code = self.station_to_code(to_station)
        middle_raw = middle_station.strip()
        middle_code = self.station_to_code(middle_raw) if middle_raw else ""

        # Warm up lc-query cookies/session before querying API.
        self.session.get(self._url("/otn/lcQuery/init"), timeout=self.timeout)
        data = self._request(
            "GET",
            f"/lcquery/{endpoint}",
            params={
                "train_date": train_date,
                "from_station_telecode": from_code,
                "to_station_telecode": to_code,
                "middle_station": middle_code,
                "result_index": str(max(0, int(result_index))),
                "can_query": can_query,
                "isShowWZ": is_show_wz,
                "purpose_codes": purpose_codes,
                "channel": channel,
            },
            referer="/otn/lcQuery/init",
        )
        if data.get("status") is False:
            raise RuntimeError(f"查询中转车票失败: {data.get('errorMsg') or data}")
        payload = data.get("data")
        if not isinstance(payload, dict):
            raise RuntimeError(f"查询中转车票返回结构异常: {data}")

        rows = payload.get("middleList")
        parsed: list[dict[str, Any]] = []
        if isinstance(rows, list):
            for item in rows:
                if not isinstance(item, dict):
                    continue
                full = item.get("fullList")
                legs = [leg for leg in full if isinstance(leg, dict)] if isinstance(full, list) else []
                first_leg = legs[0] if len(legs) > 0 else {}
                second_leg = legs[1] if len(legs) > 1 else {}
                first_leg_seats = self._extract_transfer_leg_seats(first_leg)
                second_leg_seats = self._extract_transfer_leg_seats(second_leg)
                first_leg_price = self._parse_ticket_price_from_yp_info(str(first_leg.get("yp_info") or ""))
                second_leg_price = self._parse_ticket_price_from_yp_info(str(second_leg.get("yp_info") or ""))
                row_item = {
                    "from_station": item.get("from_station_name"),
                    "to_station": item.get("end_station_name"),
                    "start_time": item.get("start_time"),
                    "arrive_time": item.get("arrive_time"),
                    "total_duration": item.get("all_lishi"),
                    "total_duration_minutes": item.get("all_lishi_minutes"),
                    "wait_time": item.get("wait_time"),
                    "wait_time_minutes": item.get("wait_time_minutes"),
                    "middle_station": item.get("middle_station_name"),
                    "middle_station_code": item.get("middle_station_code"),
                    "same_train": item.get("same_train"),
                    "score": item.get("score"),
                    "score_str": item.get("score_str"),
                    "first_leg_train_code": first_leg.get("station_train_code"),
                    "first_leg_start_time": first_leg.get("start_time"),
                    "first_leg_arrive_time": first_leg.get("arrive_time"),
                    "first_leg_second_class": first_leg.get("ze_num", "--"),
                    "first_leg_first_class": first_leg.get("zy_num", "--"),
                    "first_leg_seats": first_leg_seats,
                    "first_leg_seat_text": self._format_transfer_leg_seats(first_leg_seats),
                    "first_leg_ticket_price": first_leg_price,
                    "first_leg_ticket_price_text": self._format_ticket_price(first_leg_price) if first_leg_price else "",
                    "second_leg_train_code": second_leg.get("station_train_code"),
                    "second_leg_start_time": second_leg.get("start_time"),
                    "second_leg_arrive_time": second_leg.get("arrive_time"),
                    "second_leg_second_class": second_leg.get("ze_num", "--"),
                    "second_leg_first_class": second_leg.get("zy_num", "--"),
                    "second_leg_seats": second_leg_seats,
                    "second_leg_seat_text": self._format_transfer_leg_seats(second_leg_seats),
                    "second_leg_ticket_price": second_leg_price,
                    "second_leg_ticket_price_text": self._format_ticket_price(second_leg_price) if second_leg_price else "",
                }
                parsed.append(row_item)

        return {
            "query": {
                "date": train_date,
                "from_station": from_station,
                "to_station": to_station,
                "middle_station": middle_station,
                "from_code": from_code,
                "to_code": to_code,
                "middle_code": middle_code,
                "endpoint": endpoint,
                "purpose_codes": purpose_codes,
                "can_query": can_query,
                "is_show_wz": is_show_wz,
                "channel": channel,
                "result_index": str(max(0, int(result_index))),
            },
            "meta": {
                "flag": payload.get("flag"),
                "result_index": payload.get("result_index"),
                "can_query": payload.get("can_query"),
                "middle_station_list": payload.get("middleStationList"),
            },
            "rows": parsed,
            "raw": data,
        }

    def query_route(
        self,
        *,
        train_no: str,
        train_date: str,
        from_station: str,
        to_station: str,
    ) -> dict[str, Any]:
        dt.date.fromisoformat(train_date)
        train_no = train_no.strip()
        if not train_no:
            raise ValueError("--train-no 不能为空")
        from_code = self.station_to_code(from_station)
        to_code = self.station_to_code(to_station)

        # Warm up lc-query cookies/session before querying API.
        self.session.get(self._url("/otn/lcQuery/init"), timeout=self.timeout)
        data = self._request(
            "GET",
            "/otn/czxx/queryByTrainNo",
            params={
                "train_no": train_no,
                "from_station_telecode": from_code,
                "to_station_telecode": to_code,
                "depart_date": train_date,
            },
            referer="/otn/lcQuery/init",
        )
        if str(data.get("httpstatus", "200")) != "200" or data.get("status") is False:
            raise RuntimeError(f"查询经停站失败: {data}")

        payload = data.get("data")
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError(f"查询经停站返回结构异常: {data}")

        parsed: list[dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            parsed.append(
                {
                    "station_no": item.get("station_no"),
                    "station_name": item.get("station_name"),
                    "arrive_time": item.get("arrive_time"),
                    "start_time": item.get("start_time"),
                    "stopover_time": item.get("stopover_time"),
                    "is_enabled": bool(item.get("isEnabled")),
                    "station_train_code": item.get("station_train_code"),
                    "start_station_name": item.get("start_station_name"),
                    "end_station_name": item.get("end_station_name"),
                    "train_class_name": item.get("train_class_name"),
                }
            )
        return {
            "query": {
                "train_no": train_no,
                "date": train_date,
                "from_station": from_station,
                "to_station": to_station,
                "from_code": from_code,
                "to_code": to_code,
            },
            "rows": parsed,
            "raw": data,
        }

    def resolve_train_no_by_train_code(
        self,
        *,
        train_date: str,
        from_station: str,
        to_station: str,
        train_code: str,
        endpoint: str = "queryG",
        purpose_codes: str = "ADULT",
    ) -> dict[str, Any]:
        left_ticket = self.query_left_ticket(
            train_date=train_date,
            from_station=from_station,
            to_station=to_station,
            purpose_codes=purpose_codes,
            endpoint=endpoint,
        )
        train_row = self._find_train_row(left_ticket.get("rows", []), train_code)
        train_no = str(train_row.get("train_no", "")).strip()
        if not train_no:
            raise RuntimeError(f"车次 {train_code} 未返回 train_no，无法查询经停站。")
        return {"train_no": train_no, "train": train_row, "left_ticket": left_ticket}

    @staticmethod
    def _extract_with_patterns(text: str, patterns: list[str], field: str) -> str:
        for pattern in patterns:
            matched = re.search(pattern, text, re.S)
            if matched and matched.group(1):
                return matched.group(1)
        raise RuntimeError(f"initDc 页面缺少字段: {field}")

    @classmethod
    def resolve_seat_code(cls, seat: str) -> str:
        raw = seat.strip()
        if re.fullmatch(r"[A-Za-z0-9]{1,2}", raw):
            upper = raw.upper()
            if upper == "WZ":
                return "W"
            return upper
        candidates = [
            raw,
            raw.lower(),
            re.sub(r"\s+", "", raw),
            re.sub(r"\s+", "", raw).lower(),
            re.sub(r"[\s\-]+", "_", raw),
            re.sub(r"[\s\-]+", "_", raw).lower(),
        ]
        for key in candidates:
            if key in SEAT_CODE_MAP:
                return SEAT_CODE_MAP[key]
        supported = ", ".join(sorted(k for k in SEAT_CODE_MAP if k.isascii()))
        raise RuntimeError(
            f"不支持的席别: {seat}。可用示例: {supported}，或直接传席别代码(O/M/9/P/W/1/2/3/4/6/A/D/F/I/J/S/H)。"
        )

    @staticmethod
    def _format_train_date_for_12306(date_value: dt.date) -> str:
        week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][date_value.weekday()]
        month = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ][date_value.month - 1]
        return f"{week} {month} {date_value.day:02d} {date_value.year} 00:00:00 GMT+0800 (中国标准时间)"

    @staticmethod
    def _find_train_row(rows: list[dict[str, Any]], train_code: str) -> dict[str, Any]:
        normalized = train_code.strip().upper()
        matches = [row for row in rows if str(row.get("train_code", "")).upper() == normalized]
        if not matches:
            sample = ", ".join(sorted({str(row.get("train_code", "")) for row in rows if row.get("train_code")})[:20])
            raise RuntimeError(f"未找到车次 {train_code}。可选车次示例: {sample or '无'}")
        buyable = [row for row in matches if str(row.get("can_web_buy", "")).upper() == "Y"]
        return buyable[0] if buyable else matches[0]

    def init_dc_context(self) -> dict[str, str]:
        html = self._request_text(
            "POST",
            "/otn/confirmPassenger/initDc",
            data={"_json_att": ""},
            referer="/otn/leftTicket/init",
        )
        token = self._extract_with_patterns(
            html,
            [
                r"globalRepeatSubmitToken\s*=\s*'([^']+)'",
                r'globalRepeatSubmitToken\s*=\s*"([^"]+)"',
            ],
            "globalRepeatSubmitToken",
        )
        key_check = self._extract_with_patterns(
            html,
            [
                r"'key_check_isChange'\s*:\s*'([^']+)'",
                r'"key_check_isChange"\s*:\s*"([^"]+)"',
                r"key_check_isChange\s*=\s*'([^']+)'",
            ],
            "key_check_isChange",
        )
        left_ticket_str = self._extract_with_patterns(
            html,
            [
                r"'leftTicketStr'\s*:\s*'([^']+)'",
                r'"leftTicketStr"\s*:\s*"([^"]+)"',
                r"leftTicketStr\s*=\s*'([^']+)'",
            ],
            "leftTicketStr",
        )
        train_location = self._extract_with_patterns(
            html,
            [
                r"'train_location'\s*:\s*'([^']+)'",
                r'"train_location"\s*:\s*"([^"]+)"',
                r"train_location\s*=\s*'([^']+)'",
            ],
            "train_location",
        )
        purpose_codes = "ADULT"
        for pattern in [
            r"'purpose_codes'\s*:\s*'([^']+)'",
            r'"purpose_codes"\s*:\s*"([^"]+)"',
            r"purpose_codes\s*=\s*'([^']+)'",
        ]:
            matched = re.search(pattern, html, re.S)
            if matched and matched.group(1):
                purpose_codes = matched.group(1)
                break
        return {
            "repeat_submit_token": token,
            "key_check_is_change": key_check,
            "left_ticket_str": left_ticket_str,
            "train_location": train_location,
            "purpose_codes": purpose_codes,
        }

    def get_passenger_dtos(self, repeat_submit_token: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/otn/confirmPassenger/getPassengerDTOs",
            data={
                "_json_att": "",
                "REPEAT_SUBMIT_TOKEN": repeat_submit_token,
            },
            referer="/otn/confirmPassenger/initDc?N",
        )

    def query_passengers(self) -> dict[str, Any]:
        errors: list[str] = []

        try:
            self.session.get(self._url("/otn/leftTicket/init"), timeout=self.timeout)
            init_context = self.init_dc_context()
            repeat_submit_token = init_context["repeat_submit_token"]
            resp = self.get_passenger_dtos(repeat_submit_token)
            data = resp.get("data") if isinstance(resp, dict) else None
            rows = data.get("normal_passengers") if isinstance(data, dict) else None
            if isinstance(rows, list):
                return {"source": "confirmPassenger/getPassengerDTOs", "passengers": rows, "raw": resp}
            errors.append(f"getPassengerDTOs 返回结构异常: {resp}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"getPassengerDTOs 路径失败: {e}")

        for method in ("POST", "GET"):
            try:
                req_kwargs: dict[str, Any] = {
                    "referer": "/otn/passengers/init",
                }
                payload = {
                    "pageIndex": "1",
                    "pageSize": "200",
                    "_json_att": "",
                }
                if method == "POST":
                    req_kwargs["data"] = payload
                else:
                    req_kwargs["params"] = payload
                resp = self._request(
                    method,
                    "/otn/passengers/query",
                    **req_kwargs,
                )
                data = resp.get("data") if isinstance(resp, dict) else None
                rows = None
                if isinstance(data, dict):
                    rows = data.get("datas") or data.get("normal_passengers")
                if isinstance(rows, list):
                    return {"source": f"passengers/query ({method})", "passengers": rows, "raw": resp}
                errors.append(f"passengers/query({method}) 返回结构异常: {resp}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"passengers/query({method}) 路径失败: {e}")

        raise RuntimeError("获取乘车人列表失败。详情: " + " | ".join(errors))

    def check_user(self) -> dict[str, Any]:
        return self._request(
            "POST",
            "/otn/login/checkUser",
            data={"_json_att": ""},
            referer="/otn/leftTicket/init",
        )

    @staticmethod
    def _select_passengers(passenger_resp: dict[str, Any], passenger_names: list[str]) -> list[dict[str, Any]]:
        data = passenger_resp.get("data") if isinstance(passenger_resp, dict) else None
        rows = data.get("normal_passengers") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise RuntimeError(f"获取乘客列表失败: {passenger_resp}")

        name_map: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("passenger_name", "")).strip()
            if name:
                name_map[name] = row

        selected: list[dict[str, Any]] = []
        missing: list[str] = []
        for requested in passenger_names:
            key = requested.strip()
            if not key:
                continue
            matched = name_map.get(key)
            if matched is None:
                missing.append(key)
                continue
            selected.append(matched)
        if missing:
            available = ", ".join(sorted(name_map.keys())[:30])
            raise RuntimeError(f"乘客不存在: {', '.join(missing)}。当前可选: {available or '无'}")
        if not selected:
            raise RuntimeError("没有可用乘客，请检查 --passengers 参数。")
        return selected

    @staticmethod
    def _build_passenger_payload(selected: list[dict[str, Any]], seat_code: str) -> tuple[str, str]:
        ticket_segments: list[str] = []
        old_segments: list[str] = []
        for item in selected:
            name = str(item.get("passenger_name", "")).strip()
            id_type = str(item.get("passenger_id_type_code", "")).strip()
            id_no = str(item.get("passenger_id_no", "")).strip()
            mobile = str(item.get("mobile_no", "")).strip()
            passenger_type = str(item.get("passenger_type") or "1").strip() or "1"
            all_enc_str = str(item.get("allEncStr") or "").strip()
            if not (name and id_type and id_no):
                raise RuntimeError(f"乘客信息不完整，无法下单: {item}")
            passenger_fields = [
                seat_code,
                "0",
                passenger_type,
                name,
                id_type,
                id_no,
                mobile,
                "N",
            ]
            if all_enc_str:
                passenger_fields.append(all_enc_str)
            ticket_segments.append(",".join(passenger_fields))
            old_segments.append(f"{name},{id_type},{id_no},{passenger_type}_")
        return "_".join(ticket_segments), "".join(old_segments)

    @staticmethod
    def _normalize_choose_seats(raw_choose_seats: str, passenger_count: int) -> str:
        text = (raw_choose_seats or "").strip().upper()
        if not text:
            return ""
        text = text.replace("，", ",").replace("、", ",")

        def normalize_token(token: str, index: int) -> str:
            tok = token.strip().upper()
            if not tok:
                return ""
            if re.fullmatch(r"[A-Z]", tok):
                return f"{index}{tok}"
            if re.fullmatch(r"[1-9][A-Z]", tok):
                return tok
            if re.fullmatch(r"[A-Z][1-9]", tok):
                return f"{tok[1]}{tok[0]}"
            return tok

        if "," in text:
            parts = [p.strip() for p in text.split(",") if p.strip()]
            normalized_parts: list[str] = []
            for idx, part in enumerate(parts, start=1):
                normalized_parts.append(normalize_token(part, idx))
            return "".join(normalized_parts)

        compact = re.sub(r"\s+", "", text)
        if re.fullmatch(r"[A-Z]+", compact):
            if len(compact) == 1:
                return f"1{compact}"
            return "".join(f"{idx}{seat}" for idx, seat in enumerate(compact, start=1))
        if re.fullmatch(r"[A-Z][1-9]", compact):
            return f"{compact[1]}{compact[0]}"
        if re.fullmatch(r"[1-9][A-Z]", compact):
            return compact
        return compact

    def check_order_info(
        self,
        *,
        repeat_submit_token: str,
        passenger_ticket_str: str,
        old_passenger_str: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/otn/confirmPassenger/checkOrderInfo",
            data={
                "cancel_flag": "2",
                "bed_level_order_num": "000000000000000000000000000000",
                "passengerTicketStr": passenger_ticket_str,
                "oldPassengerStr": old_passenger_str,
                "tour_flag": "dc",
                "whatsSelect": "1",
                "sessionId": "",
                "sig": "",
                "scene": "nc_login",
                "_json_att": "",
                "REPEAT_SUBMIT_TOKEN": repeat_submit_token,
            },
            referer="/otn/confirmPassenger/initDc?N",
        )

    def get_queue_count(
        self,
        *,
        repeat_submit_token: str,
        train_date: dt.date,
        seat_code: str,
        train_row: dict[str, Any],
        left_ticket_str: str,
        train_location: str,
        purpose_codes: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/otn/confirmPassenger/getQueueCount",
            data={
                "train_date": self._format_train_date_for_12306(train_date),
                "train_no": str(train_row.get("train_no", "")),
                "stationTrainCode": str(train_row.get("train_code", "")),
                "seatType": seat_code,
                "fromStationTelecode": str(train_row.get("from_station_code", "")),
                "toStationTelecode": str(train_row.get("to_station_code", "")),
                "leftTicket": left_ticket_str,
                "purpose_codes": purpose_codes,
                "train_location": train_location,
                "_json_att": "",
                "REPEAT_SUBMIT_TOKEN": repeat_submit_token,
            },
            referer="/otn/confirmPassenger/initDc?N",
        )

    def confirm_single_for_queue(
        self,
        *,
        repeat_submit_token: str,
        passenger_ticket_str: str,
        old_passenger_str: str,
        purpose_codes: str,
        key_check_is_change: str,
        left_ticket_str: str,
        train_location: str,
        choose_seats: str = "",
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/otn/confirmPassenger/confirmSingleForQueue",
            data={
                "passengerTicketStr": passenger_ticket_str,
                "oldPassengerStr": old_passenger_str,
                "purpose_codes": purpose_codes,
                "key_check_isChange": key_check_is_change,
                "leftTicketStr": left_ticket_str,
                "train_location": train_location,
                "choose_seats": choose_seats,
                "seatDetailType": "000",
                "is_jy": "N",
                "is_cj": "N",
                "encryptedData": "",
                "whatsSelect": "1",
                "roomType": "00",
                "dwAll": "N",
                "_json_att": "",
                "REPEAT_SUBMIT_TOKEN": repeat_submit_token,
            },
            referer="/otn/confirmPassenger/initDc?N",
        )

    def query_order_wait_time(self, *, repeat_submit_token: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/otn/confirmPassenger/queryOrderWaitTime",
            params={
                "random": str(int(time.time() * 1000)),
                "tourFlag": "dc",
                "_json_att": "",
                "REPEAT_SUBMIT_TOKEN": repeat_submit_token,
            },
            referer="/otn/confirmPassenger/initDc?N",
        )

    def wait_for_order_id(
        self,
        *,
        repeat_submit_token: str,
        max_wait_seconds: int = 30,
        poll_interval: float = 1.5,
    ) -> dict[str, Any]:
        started = time.time()
        while True:
            resp = self.query_order_wait_time(repeat_submit_token=repeat_submit_token)
            if str(resp.get("httpstatus", "200")) != "200" or resp.get("status") is False:
                raise RuntimeError(f"轮询排队状态失败: {resp}")
            data = resp.get("data") if isinstance(resp, dict) else None
            order_id = None
            if isinstance(data, dict):
                order_id = data.get("orderId") or data.get("order_id")
            if order_id:
                return {"order_id": str(order_id), "wait_time": data.get("waitTime"), "raw": resp}
            if time.time() - started >= max_wait_seconds:
                raise RuntimeError(f"排队超时（>{max_wait_seconds}s），最后一次响应: {resp}")
            time.sleep(max(0.3, poll_interval))

    def result_order_for_dc_queue(self, *, repeat_submit_token: str, order_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/otn/confirmPassenger/resultOrderForDcQueue",
            data={
                "orderSequence_no": order_id,
                "_json_att": "",
                "REPEAT_SUBMIT_TOKEN": repeat_submit_token,
            },
            referer="/otn/confirmPassenger/initDc?N",
        )

    def init_pay_order(self) -> str:
        random_value = str(int(time.time() * 1000))
        self._request_text(
            "GET",
            "/otn/payOrder/init",
            params={"random": random_value},
            referer="/otn/confirmPassenger/initDc?N",
        )
        return random_value

    def pay_check_new(self, *, init_random: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/otn/payOrder/paycheckNew",
            data={
                "batch_nos": "",
                "coach_nos": "",
                "seat_nos": "",
                "passenger_id_types": "",
                "passenger_id_nos": "",
                "passenger_names": "",
                "allEncStr": "",
                "insure_price": "0",
                "insure_types": "",
                "if_buy_insure_only": "N",
                "ins_selected_time": "",
                "ins_clause_time": "",
                "ins_notice_time": "",
                "hasBoughtIns": "",
                "ins_id": "1103_PLANA_30",
                "reserver_id_type": "",
                "reserver_id_no": "",
                "reserver_name": "",
                "inschild": "",
                "_json_att": "",
            },
            referer=f"/otn/payOrder/init?random={init_random}",
        )

    @staticmethod
    def _build_payment_result(pay_check_new_resp: dict[str, Any]) -> dict[str, Any]:
        data = pay_check_new_resp.get("data") if isinstance(pay_check_new_resp, dict) else None
        pay_form = data.get("payForm") if isinstance(data, dict) else None
        if not isinstance(pay_form, dict):
            raise RuntimeError(f"paycheckNew 返回结构异常: {pay_check_new_resp}")

        epayurl = str(pay_form.get("epayurl") or "").strip()
        if not epayurl:
            raise RuntimeError(f"paycheckNew 返回缺少 epayurl: {pay_check_new_resp}")

        pay_query_fields = (
            "payOrderId",
            "interfaceName",
            "interfaceVersion",
            "tranData",
            "merSignMsg",
            "appId",
            "transType",
        )
        pay_params: dict[str, str] = {}
        for key in pay_query_fields:
            value = pay_form.get(key)
            if value is None:
                continue
            text = str(value)
            if text:
                pay_params[key] = text
        pay_url = epayurl
        if pay_params:
            pay_url = f"{epayurl}?{urlencode(pay_params)}"
        return {
            "pay_url": pay_url,
            "epayurl": epayurl,
            "pay_params": pay_params,
            "pay_form": pay_form,
            "paycheckNew": pay_check_new_resp,
        }

    def report_confirm_log(self, *, repeat_submit_token: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/otn/basedata/log",
            data={
                "type": "dc",
                "_json_att": "",
                "REPEAT_SUBMIT_TOKEN": repeat_submit_token,
            },
            referer="/otn/confirmPassenger/initDc?N",
        )

    def book_ticket(
        self,
        *,
        train_date: str,
        from_station: str,
        to_station: str,
        train_code: str,
        seat: str,
        passenger_names: list[str],
        purpose_codes: str = "ADULT",
        endpoint: str = "queryG",
        choose_seats: str = "",
        max_wait_seconds: int = 30,
        poll_interval: float = 1.5,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        travel_date = dt.date.fromisoformat(train_date)
        seat_code = self.resolve_seat_code(seat)
        left_ticket = self.query_left_ticket(
            train_date=train_date,
            from_station=from_station,
            to_station=to_station,
            purpose_codes=purpose_codes,
            endpoint=endpoint,
        )
        train_row = self._find_train_row(left_ticket.get("rows", []), train_code)
        if str(train_row.get("can_web_buy", "")).upper() != "Y":
            raise RuntimeError(f"车次 {train_code} 当前不可预订（can_web_buy={train_row.get('can_web_buy')}）。")
        secret_str = str(train_row.get("secret_str", "")).strip()
        if not secret_str:
            raise RuntimeError("余票数据中缺少 secret_str，无法提交预订请求。")

        check_user_resp = self.check_user()
        check_user_data = check_user_resp.get("data") if isinstance(check_user_resp, dict) else None
        check_user_ok = (
            str(check_user_resp.get("httpstatus", "200")) == "200"
            and check_user_resp.get("status") is not False
            and (not isinstance(check_user_data, dict) or check_user_data.get("flag") is not False)
        )
        if not check_user_ok:
            raise RuntimeError(f"checkUser 失败: {check_user_resp}")

        submit_back_date = dt.date.today().isoformat()
        submit_from_station_name = str(train_row.get("from_station") or from_station)
        submit_to_station_name = str(train_row.get("to_station") or to_station)
        seat_discount_info = str(train_row.get("yp_info") or "")
        submit = self._request(
            "POST",
            "/otn/leftTicket/submitOrderRequest",
            data={
                "secretStr": unquote(secret_str),
                "train_date": travel_date.isoformat(),
                "back_train_date": submit_back_date,
                "tour_flag": "dc",
                "purpose_codes": purpose_codes,
                "query_from_station_name": submit_from_station_name,
                "query_to_station_name": submit_to_station_name,
                "bed_level_info": "",
                "seat_discount_info": seat_discount_info,
                "undefined": "",
            },
            referer="/otn/leftTicket/init",
        )
        if str(submit.get("httpstatus", "200")) != "200" or submit.get("status") is False:
            raise RuntimeError(f"submitOrderRequest 失败: {submit}")

        init_context = self.init_dc_context()
        repeat_submit_token = init_context["repeat_submit_token"]
        passengers_resp = self.get_passenger_dtos(repeat_submit_token)
        selected = self._select_passengers(passengers_resp, passenger_names)
        passenger_ticket_str, old_passenger_str = self._build_passenger_payload(selected, seat_code)
        normalized_choose_seats = self._normalize_choose_seats(choose_seats, len(selected))

        check_order = self.check_order_info(
            repeat_submit_token=repeat_submit_token,
            passenger_ticket_str=passenger_ticket_str,
            old_passenger_str=old_passenger_str,
        )
        check_data = check_order.get("data") if isinstance(check_order, dict) else None
        if str(check_order.get("httpstatus", "200")) != "200" or check_order.get("status") is False:
            raise RuntimeError(f"checkOrderInfo 失败: {check_order}")
        if isinstance(check_data, dict) and check_data.get("submitStatus") is False:
            raise RuntimeError(f"checkOrderInfo 未通过: {check_order}")

        queue_count = self.get_queue_count(
            repeat_submit_token=repeat_submit_token,
            train_date=travel_date,
            seat_code=seat_code,
            train_row=train_row,
            left_ticket_str=init_context["left_ticket_str"],
            train_location=init_context["train_location"],
            purpose_codes=init_context.get("purpose_codes") or purpose_codes,
        )
        if str(queue_count.get("httpstatus", "200")) != "200" or queue_count.get("status") is False:
            raise RuntimeError(f"getQueueCount 失败: {queue_count}")
        if dry_run:
            return {
                "step": "checked",
                "seat_code": seat_code,
                "train": train_row,
                "selected_passengers": [p.get("passenger_name") for p in selected],
                "checkUser": check_user_resp,
                "submitOrderRequest": submit,
                "checkOrderInfo": check_order,
                "getQueueCount": queue_count,
            }

        confirm = self.confirm_single_for_queue(
            repeat_submit_token=repeat_submit_token,
            passenger_ticket_str=passenger_ticket_str,
            old_passenger_str=old_passenger_str,
            purpose_codes=init_context.get("purpose_codes") or purpose_codes,
            key_check_is_change=init_context["key_check_is_change"],
            left_ticket_str=init_context["left_ticket_str"],
            train_location=init_context["train_location"],
            choose_seats=normalized_choose_seats,
        )
        confirm_data = confirm.get("data") if isinstance(confirm, dict) else None
        if str(confirm.get("httpstatus", "200")) != "200" or confirm.get("status") is False:
            raise RuntimeError(f"confirmSingleForQueue 失败: {confirm}")
        if isinstance(confirm_data, dict) and confirm_data.get("submitStatus") is False:
            raise RuntimeError(f"confirmSingleForQueue 未通过: {confirm}")
        try:
            confirm_log = self.report_confirm_log(repeat_submit_token=repeat_submit_token)
        except Exception as e:  # noqa: BLE001
            confirm_log = {"warning": f"basedata/log 失败（不影响下单流程）: {e}"}

        wait_info = self.wait_for_order_id(
            repeat_submit_token=repeat_submit_token,
            max_wait_seconds=max_wait_seconds,
            poll_interval=poll_interval,
        )
        order_id = wait_info["order_id"]
        result_order = self.result_order_for_dc_queue(
            repeat_submit_token=repeat_submit_token,
            order_id=order_id,
        )
        result_data = result_order.get("data") if isinstance(result_order, dict) else None
        if str(result_order.get("httpstatus", "200")) != "200" or result_order.get("status") is False:
            raise RuntimeError(f"resultOrderForDcQueue 失败: {result_order}")
        if isinstance(result_data, dict) and result_data.get("submitStatus") is False:
            raise RuntimeError(f"resultOrderForDcQueue 未通过: {result_order}")

        payment: dict[str, Any]
        try:
            init_random = self.init_pay_order()
            pay_check_new_resp = self.pay_check_new(init_random=init_random)
            if str(pay_check_new_resp.get("httpstatus", "200")) != "200" or pay_check_new_resp.get("status") is False:
                raise RuntimeError(f"paycheckNew 失败: {pay_check_new_resp}")
            pay_data = pay_check_new_resp.get("data") if isinstance(pay_check_new_resp, dict) else None
            if isinstance(pay_data, dict) and pay_data.get("flag") is False:
                raise RuntimeError(f"paycheckNew 返回 flag=false: {pay_check_new_resp}")
            payment = self._build_payment_result(pay_check_new_resp)
            payment["init_random"] = init_random
        except Exception as e:  # noqa: BLE001
            payment = {"warning": f"支付链接生成失败（订单已成功，可在12306待支付订单中继续支付）: {e}"}

        return {
            "step": "ordered",
            "order_id": order_id,
            "seat_code": seat_code,
            "train": train_row,
            "selected_passengers": [p.get("passenger_name") for p in selected],
            "checkUser": check_user_resp,
            "submitOrderRequest": submit,
            "checkOrderInfo": check_order,
            "getQueueCount": queue_count,
            "confirmSingleForQueue": confirm,
            "basedataLog": confirm_log,
            "queryOrderWaitTime": wait_info["raw"],
            "resultOrderForDcQueue": result_order,
            "payment": payment,
        }


def read_password(args: argparse.Namespace) -> str:
    if args.password:
        return args.password
    env_pwd = os.getenv("KYFW_PASSWORD")
    if env_pwd:
        return env_pwd
    return getpass.getpass("12306 password: ")


def print_orders(resp: dict[str, Any]) -> None:
    data = resp.get("data") or {}
    total = data.get("order_total_number", "0")
    orders = data.get("OrderDTODataList", [])
    print(f"订单总数: {total}, 当前页: {len(orders)}")
    for order in orders:
        order_date = order.get("order_date") or "--"
        # `order_date` 是下单时间，`start_train_date_page` 才是出行日期。
        travel_date = (
            order.get("start_train_date_page")
            or order.get("start_train_date")
            or order.get("train_date")
            or "--"
        )
        print(
            f"- 订单号: {order.get('sequence_no')} | 下单日期: {order_date} | 出行日期: {travel_date} | "
            f"{order.get('train_code_page')} {order.get('from_station_name_page')} -> {order.get('to_station_name_page')} | "
            f"{order.get('start_time_page')} -> {order.get('arrive_time_page')} | 人数: {order.get('ticket_totalnum')}"
        )
        for ticket in order.get("tickets", []):
            passenger = (ticket.get("passengerDTO") or {}).get("passenger_name") or ticket.get("book_user_name")
            print(
                f"  乘客: {passenger} | 席别: {ticket.get('seat_name')} | "
                f"车厢座位: {ticket.get('coach_no')}/{ticket.get('seat_no')} | 状态: {ticket.get('ticket_status_name')}"
            )


def print_candidate_queue(queue: dict[str, Any]) -> None:
    flag = queue.get("flag")
    status = queue.get("status")
    is_async = queue.get("is_async")
    print("候补查询开关:", "开启" if flag else "关闭")
    print("候补队列状态码:", status)
    print("异步处理:", "是" if is_async else "否")


def print_candidate_orders(rows: list[dict[str, Any]], limit: int) -> None:
    shown = rows[: max(0, limit)]
    print(f"候补订单总数: {len(rows)}, 展示: {len(shown)}")
    for item in shown:
        passengers = ",".join(item.get("passengers") or [])
        print(
            f"- 候补单: {item.get('reserve_no') or '--'} | 状态: {item.get('status_name') or '--'}({item.get('status_code') or '--'}) | "
            f"提交日期: {item.get('reserve_time') or '--'} | 截止兑现: {item.get('realize_limit_time') or '--'}"
        )
        print(
            f"  行程: {item.get('train_date') or '--'} {item.get('train_code') or '--'} "
            f"{item.get('from_station') or '--'} -> {item.get('to_station') or '--'} "
            f"{item.get('start_time') or '--'}->{item.get('arrive_time') or '--'} | "
            f"席别: {item.get('seat_name') or '--'} | 乘客: {passengers or '--'}"
        )
        print(
            f"  金额: 预付款={item.get('prepay_amount') or '--'} | 票款={item.get('ticket_price') or '--'} | 可退={item.get('refundable') or '--'}"
        )


def print_left_tickets(rows: list[dict[str, Any]], limit: int) -> None:
    print(f"共返回车次: {len(rows)}")
    header = "车次   出发->到达   时长   商务 特等 优一 一等 二等 包座 高软 软卧 硬卧 软座 硬座 无座"
    print(header)
    print("-" * len(header))
    for item in rows[:limit]:
        print(
            f"{item['train_code']:<5} "
            f"{item['start_time']}-{item['arrive_time']} "
            f"{item['duration']:<5} "
            f"{item['business']:<3} "
            f"{item['special_class']:<3} "
            f"{item['premium_first_class']:<3} "
            f"{item['first_class']:<3} "
            f"{item['second_class']:<3} "
            f"{item['second_class_compartment']:<3} "
            f"{item['deluxe_soft_sleeper']:<3} "
            f"{item['soft_sleeper']:<3} "
            f"{item['hard_sleeper']:<3} "
            f"{item['soft_seat']:<3} "
            f"{item['hard_seat']:<3} "
            f"{item['no_seat']:<3}"
        )
        price_text = str(item.get("ticket_price_text") or "").strip()
        if price_text:
            print(f"      票价: {price_text}")


def print_transfer_tickets(rows: list[dict[str, Any]], limit: int) -> None:
    shown = rows[: max(0, limit)]
    print(f"共返回中转方案: {len(rows)}, 展示: {len(shown)}")
    header = "序号 换乘站   车次(第一程->第二程)   发时->到时   总耗时   等待"
    print(header)
    print("-" * len(header))
    for idx, item in enumerate(shown, start=1):
        middle_station = str(item.get("middle_station") or "--")
        train_pair = f"{item.get('first_leg_train_code') or '--'}->{item.get('second_leg_train_code') or '--'}"
        time_pair = f"{item.get('start_time') or '--'}->{item.get('arrive_time') or '--'}"
        total_duration = str(item.get("total_duration") or "--")
        wait_time = str(item.get("wait_time") or "--")
        print(
            f"{idx:<4} {middle_station:<8} {train_pair:<24} {time_pair:<13} {total_duration:<8} {wait_time:<8}"
        )
        print(
            f"     第一程坐席: {item.get('first_leg_seat_text') or '--'}"
        )
        print(
            f"     第一程票价: {item.get('first_leg_ticket_price_text') or '--'}"
        )
        print(
            f"     第二程坐席: {item.get('second_leg_seat_text') or '--'}"
        )
        print(
            f"     第二程票价: {item.get('second_leg_ticket_price_text') or '--'}"
        )


def print_route(rows: list[dict[str, Any]], limit: int) -> None:
    shown = rows[: max(0, limit)]
    print(f"共返回经停站: {len(rows)}, 展示: {len(shown)}")
    header = "序号 站序 站名       到达     开车     停留"
    print(header)
    print("-" * len(header))
    for idx, item in enumerate(shown, start=1):
        station_no = str(item.get("station_no") or "--")
        station_name = str(item.get("station_name") or "--")
        arrive_time = str(item.get("arrive_time") or "--")
        start_time = str(item.get("start_time") or "--")
        stopover_time = str(item.get("stopover_time") or "--")
        marker = "*" if item.get("is_enabled") else " "
        print(
            f"{marker}{idx:<3} {station_no:<4} {station_name:<10} {arrive_time:<8} {start_time:<8} {stopover_time:<8}"
        )
    if shown:
        print("* 表示当前查询区间内的站点")


def _mask_middle(value: str, keep_head: int = 3, keep_tail: int = 2) -> str:
    text = (value or "").strip()
    if len(text) <= keep_head + keep_tail:
        return text
    return f"{text[:keep_head]}{'*' * (len(text) - keep_head - keep_tail)}{text[-keep_tail:]}"


def print_passengers(rows: list[dict[str, Any]], limit: int) -> None:
    shown = rows[: max(0, limit)]
    print(f"乘车人总数: {len(rows)}, 展示: {len(shown)}")
    for item in shown:
        name = item.get("passenger_name") or item.get("name") or "--"
        p_type = item.get("passenger_type_name") or item.get("passenger_type") or "--"
        id_type = item.get("passenger_id_type_name") or item.get("passenger_id_type_code") or "--"
        id_no_raw = str(item.get("passenger_id_no") or item.get("identity_no") or "")
        mobile_raw = str(item.get("mobile_no") or item.get("mobile") or "")
        id_no = _mask_middle(id_no_raw, keep_head=3, keep_tail=2) if id_no_raw else "--"
        mobile = _mask_middle(mobile_raw, keep_head=3, keep_tail=2) if mobile_raw else "--"
        print(f"- {name} | 类型: {p_type} | 证件: {id_type} {id_no} | 手机: {mobile}")


def add_auth_args(
    parser: argparse.ArgumentParser,
    *,
    require_username: bool = True,
    allow_send_sms: bool = True,
) -> None:
    parser.add_argument("--username", required=require_username, help="12306 用户名/邮箱/手机号")
    parser.add_argument("--password", help="12306 密码（不传则读取 KYFW_PASSWORD 或交互输入）")
    parser.add_argument("--id-last4", help="证件号后4位（短信验证码模式需要）")
    parser.add_argument("--sms-code", help="短信验证码（6位）")
    if allow_send_sms:
        parser.add_argument("--send-sms", action="store_true", help="仅发送短信验证码，不执行完整登录")


def resolve_qr_state_path(args: argparse.Namespace) -> Path:
    raw = getattr(args, "state_file", None)
    if raw:
        return Path(raw).expanduser()
    return derive_qr_login_state_file(getattr(args, "cookie_file", None))


def build_random_qr_image_path(*, use_tmp: bool = False) -> Path:
    name = f"12306_qr_login_{uuidlib.uuid4().hex[:12]}.png"
    if use_tmp:
        return Path(tempfile.gettempdir()) / name
    return Path(__file__).resolve().parent / name


def decode_qr_image_bytes(image_b64: str) -> bytes:
    text = (image_b64 or "").strip()
    if not text:
        raise ValueError("二维码内容为空")
    padding = "=" * (-len(text) % 4)
    return base64.b64decode(text + padding)


def write_qr_image_file(image_b64: str, *, preferred_path: Path | None = None) -> Path:
    image_bytes = decode_qr_image_bytes(image_b64)
    if preferred_path is not None:
        target = preferred_path.expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(image_bytes)
        return target

    image_path = build_random_qr_image_path(use_tmp=False)
    try:
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(image_bytes)
    except OSError:
        image_path = build_random_qr_image_path(use_tmp=True)
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(image_bytes)
    return image_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="12306 API CLI")
    parser.add_argument("--base-url", default=BASE_URL, help="12306 base URL")
    parser.add_argument("--timeout", type=int, default=15, help="请求超时时间（秒）")
    parser.add_argument(
        "--cookie-file",
        default=DEFAULT_COOKIE_FILE,
        help=f"Cookie 持久化文件路径（默认 {DEFAULT_COOKIE_FILE}）",
    )
    parser.add_argument(
        "--no-browser-headers",
        action="store_true",
        help="关闭浏览器风格请求头仿真（默认开启）",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")

    sub = parser.add_subparsers(dest="command", required=True)

    login_p = sub.add_parser("login", help="登录")
    add_auth_args(login_p, require_username=True, allow_send_sms=True)

    qr_create_p = sub.add_parser("qr-login-create", help="生成二维码登录图片（不轮询）")
    qr_create_p.add_argument("--appid", default="otn", help="二维码登录 appid（默认 otn）")
    qr_create_p.add_argument(
        "--qr-image-file",
        help="二维码图片输出路径（不传则自动生成随机路径）",
    )
    qr_create_p.add_argument(
        "--state-file",
        help="二维码登录状态文件路径（默认从 --cookie-file 推导）",
    )

    sub.add_parser("qr-login-check", help="检查二维码登录状态（固定1秒轮询，持续等待）")

    order_p = sub.add_parser("orders", help="查询用户车票")
    add_auth_args(order_p, require_username=False, allow_send_sms=False)
    order_p.add_argument("--where", default="G", choices=["G", "H"], help="G:未出行/近期, H:历史订单")
    order_p.add_argument("--start-date", help="查询起始日期, YYYY-MM-DD")
    order_p.add_argument("--end-date", help="查询结束日期, YYYY-MM-DD")
    order_p.add_argument("--page-index", type=int, default=0)
    order_p.add_argument("--page-size", type=int, default=8)
    order_p.add_argument("--query-type", type=int, default=1)
    order_p.add_argument("--train-name", default="", help="按车次过滤（可选）")

    candidate_queue_p = sub.add_parser("candidate-queue", help="查询候补排队状态")
    add_auth_args(candidate_queue_p, require_username=False, allow_send_sms=False)

    candidate_orders_p = sub.add_parser("candidate-orders", help="查询候补订单")
    add_auth_args(candidate_orders_p, require_username=False, allow_send_sms=False)
    candidate_orders_p.add_argument(
        "--processed",
        action="store_true",
        help="查询已处理候补订单（默认查询进行中的候补订单）",
    )
    candidate_orders_p.add_argument("--page-no", type=int, default=0, help="页码（默认0）")
    candidate_orders_p.add_argument("--start-date", help="查询起始日期 YYYY-MM-DD（默认今天）")
    candidate_orders_p.add_argument("--end-date", help="查询结束日期 YYYY-MM-DD（默认起始日期+29天）")
    candidate_orders_p.add_argument("--limit", type=int, default=20, help="最多展示多少条候补订单")

    candidate_submit_p = sub.add_parser("candidate-submit", help="提交候补订单")
    add_auth_args(candidate_submit_p, require_username=False, allow_send_sms=False)
    candidate_submit_p.add_argument("--date", required=True, help="出发日期 YYYY-MM-DD")
    candidate_submit_p.add_argument("--from", dest="from_station", required=True, help="出发站（中文名/拼音/三字码）")
    candidate_submit_p.add_argument("--to", dest="to_station", required=True, help="到达站（中文名/拼音/三字码）")
    candidate_submit_p.add_argument("--train-code", required=True, help="车次，例如 G1234")
    candidate_submit_p.add_argument("--seat", required=True, help="席别，例如 second_class / O / 一等座")
    candidate_submit_p.add_argument("--purpose", default="ADULT", help="乘客类型，默认 ADULT")
    candidate_submit_p.add_argument(
        "--endpoint",
        default="queryG",
        choices=["queryG", "queryZ"],
        help="余票接口类型",
    )
    candidate_submit_p.add_argument(
        "--force",
        action="store_true",
        help="即使该席别余票不是“无”也尝试提交候补",
    )

    candidate_cancel_p = sub.add_parser("candidate-cancel", help="取消候补订单")
    add_auth_args(candidate_cancel_p, require_username=False, allow_send_sms=False)
    candidate_cancel_p.add_argument("--reserve-no", required=True, help="候补单号（reserve_no）")

    left_p = sub.add_parser("left-ticket", help="查询车次余票")
    left_p.add_argument("--date", required=True, help="出发日期 YYYY-MM-DD")
    left_p.add_argument("--from", dest="from_station", required=True, help="出发站（中文名/拼音/三字码）")
    left_p.add_argument("--to", dest="to_station", required=True, help="到达站（中文名/拼音/三字码）")
    left_p.add_argument("--purpose", default="ADULT", help="乘客类型，默认 ADULT")
    left_p.add_argument("--endpoint", default="queryG", choices=["queryG", "queryZ"], help="余票接口类型")
    left_p.add_argument("--limit", type=int, default=20, help="最多展示多少行")

    transfer_p = sub.add_parser("transfer-ticket", help="查询中转车票")
    transfer_p.add_argument("--date", required=True, help="出发日期 YYYY-MM-DD")
    transfer_p.add_argument("--from", dest="from_station", required=True, help="出发站（中文名/拼音/三字码）")
    transfer_p.add_argument("--to", dest="to_station", required=True, help="到达站（中文名/拼音/三字码）")
    transfer_p.add_argument("--middle", dest="middle_station", default="", help="指定换乘站（可选）")
    transfer_p.add_argument("--result-index", type=int, default=0, help="分页游标（默认0）")
    transfer_p.add_argument("--can-query", default="Y", choices=["Y", "N"], help="是否继续查询更多方案")
    transfer_p.add_argument("--show-wz", action="store_true", help="显示无座方案")
    transfer_p.add_argument("--purpose", default="00", help="乘客类型编码（默认00）")
    transfer_p.add_argument("--channel", default="E", help="渠道参数（默认E）")
    transfer_p.add_argument("--endpoint", default="queryG", choices=["queryG", "queryZ"], help="中转接口类型")
    transfer_p.add_argument("--limit", type=int, default=20, help="最多展示多少行")

    route_p = sub.add_parser("route", help="查询经停站")
    route_id = route_p.add_mutually_exclusive_group(required=True)
    route_id.add_argument("--train-no", help="列车内部 train_no（如 760000C95604）")
    route_id.add_argument("--train-code", help="车次号（如 C956 / G1234），会自动解析 train_no")
    route_p.add_argument("--date", required=True, help="出发日期 YYYY-MM-DD")
    route_p.add_argument("--from", dest="from_station", required=True, help="出发站（中文名/拼音/三字码）")
    route_p.add_argument("--to", dest="to_station", required=True, help="到达站（中文名/拼音/三字码）")
    route_p.add_argument("--endpoint", default="queryG", choices=["queryG", "queryZ"], help="解析车次号时使用的余票接口类型")
    route_p.add_argument("--purpose", default="ADULT", help="解析车次号时使用的乘客类型，默认 ADULT")
    route_p.add_argument("--limit", type=int, default=200, help="最多展示多少站")

    book_p = sub.add_parser("book", help="订票（提交订单）")
    add_auth_args(book_p, require_username=False, allow_send_sms=False)
    book_p.add_argument("--date", required=True, help="出发日期 YYYY-MM-DD")
    book_p.add_argument("--from", dest="from_station", required=True, help="出发站（中文名/拼音/三字码）")
    book_p.add_argument("--to", dest="to_station", required=True, help="到达站（中文名/拼音/三字码）")
    book_p.add_argument("--train-code", required=True, help="车次，例如 G1234")
    book_p.add_argument("--seat", required=True, help="席别，例如 second_class / first_class / O / M / 9")
    book_p.add_argument("--passengers", required=True, help="乘客姓名，多个用逗号分隔")
    book_p.add_argument("--purpose", default="ADULT", help="乘客类型，默认 ADULT")
    book_p.add_argument("--endpoint", default="queryG", choices=["queryG", "queryZ"], help="余票接口类型")
    book_p.add_argument(
        "--choose-seats",
        default="",
        help="选座（可选；示例：D、1D、D1、A,B；其他格式将原样透传）",
    )
    book_p.add_argument("--max-wait-seconds", type=int, default=30, help="排队轮询最长等待秒数")
    book_p.add_argument("--poll-interval", type=float, default=1.5, help="排队轮询间隔秒数")
    book_p.add_argument("--dry-run", action="store_true", help="只走到排队前检查，不执行最终提交")

    passenger_p = sub.add_parser("passengers", help="查询当前账号乘车人信息")
    add_auth_args(passenger_p, require_username=False, allow_send_sms=False)
    passenger_p.add_argument("--limit", type=int, default=200, help="最多展示多少个乘车人")

    sub.add_parser("status", help="查询当前是否已登录（基于 cookie）")

    return parser


def ensure_logged_in(client: KyfwClient, args: argparse.Namespace) -> None:
    status = client.check_login_status()
    if status.get("logged_in"):
        return
    if not getattr(args, "username", None):
        raise RuntimeError(
            "当前 cookie 未登录或已失效。请提供 --username 并重新登录，"
            "或先执行 login 命令更新 cookie。"
        )
    password = read_password(args)
    login_resp = client.login(
        username=args.username,
        password=password,
        id_last4=getattr(args, "id_last4", None),
        sms_code=getattr(args, "sms_code", None),
        send_sms=False,
    )
    if login_resp.get("step") != "logged_in":
        raise RuntimeError("登录未完成，请确认短信验证码参数。")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    client = KyfwClient(
        base_url=args.base_url,
        timeout=args.timeout,
        cookie_file=args.cookie_file,
        browser_headers=not args.no_browser_headers,
    )

    try:
        if args.command == "login":
            if args.send_sms:
                password = ""
            else:
                password = read_password(args)
            resp = client.login(
                username=args.username,
                password=password,
                id_last4=args.id_last4,
                sms_code=args.sms_code,
                send_sms=args.send_sms,
            )
            if args.json:
                print(json.dumps(resp, ensure_ascii=False, indent=2))
            else:
                if resp.get("step") == "sms_sent":
                    print(resp.get("message"))
                else:
                    print("登录成功。")
            return 0

        if args.command == "qr-login-create":
            result = client.create_qr_login(appid=args.appid)
            requested_image_path = (args.qr_image_file or "").strip()
            if requested_image_path:
                image_path = write_qr_image_file(
                    str(result.get("image") or ""),
                    preferred_path=Path(requested_image_path),
                )
            else:
                image_path = write_qr_image_file(str(result.get("image") or ""))

            state_path = resolve_qr_state_path(args)
            state = {
                "version": 1,
                "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "uuid": result.get("uuid"),
                "appid": result.get("appid"),
                "qr_image_file": str(image_path),
                "cookie_file": args.cookie_file,
                "base_url": args.base_url,
                "last_check": None,
            }
            save_qr_login_state(state_path, state)

            if args.json:
                out = {
                    "step": "qr_created",
                    "result_message": result.get("result_message"),
                    "qr_image_file": str(image_path),
                    "next_action": "立即用类似 nohup 的后台方式执行: nohup python3 client.py qr-login-check > /dev/null 2>&1 &",
                }
                print(json.dumps(out, ensure_ascii=False, indent=2))
            else:
                print("二维码已生成。")
                print("二维码图片:", str(image_path))
                print("立即用类似 nohup 的后台方式执行以下命令持续检查：")
                print("  nohup python3 client.py qr-login-check > /dev/null 2>&1 &")
                print("然后再让用户用 12306 App 扫码并确认。")
            return 0

        if args.command == "qr-login-check":
            state_path = resolve_qr_state_path(args)
            state = load_qr_login_state(state_path)
            uuid = str(state.get("uuid") or "").strip()
            if not uuid:
                raise RuntimeError("状态文件中不存在 uuid。请先执行 qr-login-create。")
            appid = str(state.get("appid") or "otn").strip() or "otn"

            result: dict[str, Any]
            last_qr_status = ""
            while True:
                result = client.check_qr_login(
                    uuid=uuid,
                    appid=appid,
                    finalize=True,
                )
                step = str(result.get("step") or "")
                if step == "pending":
                    qr_status = str(result.get("qr_status") or "")
                    if not args.json and qr_status != last_qr_status:
                        if qr_status == "waiting_scan":
                            print("轮询中: 未扫描")
                        elif qr_status == "waiting_confirm":
                            print("轮询中: 已扫描，待 App 确认")
                        else:
                            print("轮询中:", qr_status or "pending")
                    last_qr_status = qr_status
                    time.sleep(1.0)
                    continue
                break

            state["uuid"] = uuid
            state["appid"] = appid
            state["last_check"] = {
                "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "step": result.get("step"),
                "result_code": result.get("result_code"),
                "result_message": result.get("result_message"),
                "qr_status": result.get("qr_status"),
            }
            if result.get("step") == "logged_in":
                state["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            save_qr_login_state(state_path, state)

            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                step = result.get("step")
                if step == "pending":
                    qr_status = result.get("qr_status")
                    if qr_status == "waiting_scan":
                        print("二维码状态: 未扫描")
                    elif qr_status == "waiting_confirm":
                        print("二维码状态: 已扫描，待 App 确认")
                    else:
                        print("二维码状态:", qr_status)
                    print("结果消息:", result.get("result_message") or "--")
                elif step == "expired":
                    print("二维码状态: 已失效，请重新执行 qr-login-create。")
                elif step == "logged_in":
                    print("登录成功。")
                    login_status = result.get("login_status") or {}
                    print("登录状态:", "已登录" if login_status.get("logged_in") else "未确认")
                    user = login_status.get("user") if isinstance(login_status, dict) else None
                    if isinstance(user, dict):
                        name = user.get("name")
                        username = user.get("username")
                        if name:
                            print("姓名:", name)
                        if username:
                            print("用户名:", username)
                else:
                    print("二维码状态:", result.get("qr_status") or "--")
                    print("结果消息:", result.get("result_message") or "--")
            return 0

        if args.command == "status":
            status = client.check_login_status()
            if args.json:
                print(json.dumps(status, ensure_ascii=False, indent=2))
            else:
                print(f"Cookie 文件: {status.get('cookie_file')}")
                print("登录状态:", "已登录" if status.get("logged_in") else "未登录")
                if status.get("logged_in"):
                    user = status.get("user")
                    if isinstance(user, dict):
                        name = user.get("name")
                        username = user.get("username")
                        email = user.get("email")
                        mobile = user.get("mobile")
                        if any((name, username, email, mobile)):
                            print("用户信息:")
                            if name:
                                print(f"  姓名: {name}")
                            if username:
                                print(f"  用户名: {username}")
                            if email:
                                print(f"  邮箱: {email}")
                            if mobile:
                                print(f"  手机: {mobile}")
            return 0

        if args.command == "passengers":
            ensure_logged_in(client, args)
            result = client.query_passengers()
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                rows = result.get("passengers") if isinstance(result, dict) else None
                if not isinstance(rows, list):
                    raise RuntimeError(f"接口返回异常: {result}")
                print("来源接口:", result.get("source"))
                print_passengers(rows, args.limit)
            return 0

        if args.command == "orders":
            ensure_logged_in(client, args)

            no_complete = client.query_my_order_no_complete()
            orders = client.query_my_order(
                query_where=args.where,
                start_date=args.start_date,
                end_date=args.end_date,
                page_index=args.page_index,
                page_size=args.page_size,
                query_type=args.query_type,
                train_name=args.train_name,
            )
            if args.json:
                out = {"no_complete": no_complete, "orders": orders}
                print(json.dumps(out, ensure_ascii=False, indent=2))
            else:
                print("未完成订单接口状态:", no_complete.get("status"), no_complete.get("httpstatus"))
                print_orders(orders)
            return 0

        if args.command == "candidate-queue":
            ensure_logged_in(client, args)
            result = client.query_candidate_queue()
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print_candidate_queue(result["queue"])
            return 0

        if args.command == "candidate-orders":
            ensure_logged_in(client, args)
            result = client.query_candidate_orders(
                processed=args.processed,
                page_no=args.page_no,
                start_date=args.start_date,
                end_date=args.end_date,
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                q = result["query"]
                print(
                    f"查询条件: type={q['type']} | page_no={q['page_no']} | "
                    f"{q['start_date']} -> {q['end_date']}"
                )
                print_candidate_orders(result["rows"], args.limit)
            return 0

        if args.command == "candidate-submit":
            ensure_logged_in(client, args)
            result = client.submit_candidate_order(
                train_date=args.date,
                from_station=args.from_station,
                to_station=args.to_station,
                train_code=args.train_code,
                seat=args.seat,
                purpose_codes=args.purpose,
                endpoint=args.endpoint,
                force=args.force,
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                step = result.get("step")
                if step == "submitted":
                    print("候补提交成功。")
                    print("车次:", result.get("train", {}).get("train_code"))
                    print("席别:", result.get("seat_name"), f"({result.get('seat_code')})")
                    print("提交前余票:", result.get("seat_status"))
                    print("下一步页面:", result.get("next_url"))
                    print("可用 candidate-orders / candidate-queue 查看状态。")
                elif step == "face_check_required":
                    print("候补提交触发身份核验。")
                    print("车次:", result.get("train", {}).get("train_code"))
                    print("席别:", result.get("seat_name"), f"({result.get('seat_code')})")
                    print("提交前余票:", result.get("seat_status"))
                    print("face_check_code:", result.get("face_check_code"))
                    print("is_show_qrcode:", result.get("is_show_qrcode"))
                    print("请先在 12306 App 完成人证核验后重试。")
            return 0

        if args.command == "candidate-cancel":
            ensure_logged_in(client, args)
            result = client.cancel_candidate_order(reserve_no=args.reserve_no)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print("候补订单取消成功。")
                print("候补单号:", result.get("reserve_no"))
                print("取消方式:", result.get("method"))
            return 0

        if args.command == "left-ticket":
            result = client.query_left_ticket(
                train_date=args.date,
                from_station=args.from_station,
                to_station=args.to_station,
                purpose_codes=args.purpose,
                endpoint=args.endpoint,
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                q = result["query"]
                print(
                    f"查询条件: {q['date']} {q['from_station']}({q['from_code']}) -> "
                    f"{q['to_station']}({q['to_code']}) | endpoint={q['endpoint']}"
                )
                print_left_tickets(result["rows"], args.limit)
            return 0

        if args.command == "transfer-ticket":
            result = client.query_transfer_ticket(
                train_date=args.date,
                from_station=args.from_station,
                to_station=args.to_station,
                middle_station=args.middle_station,
                result_index=args.result_index,
                can_query=args.can_query,
                is_show_wz="Y" if args.show_wz else "N",
                purpose_codes=args.purpose,
                channel=args.channel,
                endpoint=args.endpoint,
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                q = result["query"]
                print(
                    f"查询条件: {q['date']} {q['from_station']}({q['from_code']}) -> "
                    f"{q['to_station']}({q['to_code']}) | middle={q['middle_station'] or '任意'} "
                    f"| endpoint={q['endpoint']}"
                )
                meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
                print(
                    f"分页信息: result_index={meta.get('result_index')} "
                    f"can_query={meta.get('can_query')}"
                )
                print_transfer_tickets(result["rows"], args.limit)
            return 0

        if args.command == "route":
            route_train_no = args.train_no
            resolved_train = None
            if not route_train_no:
                resolved = client.resolve_train_no_by_train_code(
                    train_date=args.date,
                    from_station=args.from_station,
                    to_station=args.to_station,
                    train_code=args.train_code,
                    endpoint=args.endpoint,
                    purpose_codes=args.purpose,
                )
                route_train_no = resolved["train_no"]
                resolved_train = resolved.get("train")
            result = client.query_route(
                train_no=route_train_no,
                train_date=args.date,
                from_station=args.from_station,
                to_station=args.to_station,
            )
            if args.json:
                if resolved_train is not None:
                    result["resolved_train"] = resolved_train
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                q = result["query"]
                if args.train_code:
                    print(f"已根据车次 {args.train_code} 解析 train_no={q['train_no']}")
                print(
                    f"查询条件: train_no={q['train_no']} | {q['date']} "
                    f"{q['from_station']}({q['from_code']}) -> {q['to_station']}({q['to_code']})"
                )
                print_route(result["rows"], args.limit)
            return 0

        if args.command == "book":
            ensure_logged_in(client, args)
            passenger_names = [name.strip() for name in args.passengers.split(",") if name.strip()]
            if not passenger_names:
                raise RuntimeError("--passengers 至少包含一个乘客姓名。")
            result = client.book_ticket(
                train_date=args.date,
                from_station=args.from_station,
                to_station=args.to_station,
                train_code=args.train_code,
                seat=args.seat,
                passenger_names=passenger_names,
                purpose_codes=args.purpose,
                endpoint=args.endpoint,
                choose_seats=args.choose_seats,
                max_wait_seconds=args.max_wait_seconds,
                poll_interval=args.poll_interval,
                dry_run=args.dry_run,
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                if args.dry_run:
                    print("预下单检查完成（未提交最终排队确认）。")
                    print("车次:", result.get("train", {}).get("train_code"))
                    print("席别代码:", result.get("seat_code"))
                    print("乘客:", ", ".join(result.get("selected_passengers", [])))
                else:
                    print("订票请求已提交。")
                    print("订单号:", result.get("order_id"))
                    print("车次:", result.get("train", {}).get("train_code"))
                    print("席别代码:", result.get("seat_code"))
                    print("乘客:", ", ".join(result.get("selected_passengers", [])))
                    payment = result.get("payment") if isinstance(result, dict) else None
                    if isinstance(payment, dict):
                        pay_url = payment.get("pay_url")
                        warning = payment.get("warning")
                        if pay_url:
                            print("支付链接:", pay_url)
                        elif warning:
                            print(warning)
            return 0

        parser.print_help()
        return 1
    except requests.HTTPError as e:
        print(f"HTTP error: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

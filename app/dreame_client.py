"""Self-contained Dreame/Trouver/Mova cloud client for the Roomtone backend.

Multi-region, multi-brand. No file persistence — the server keeps token state
in memory per user session. The password is used once to obtain an OAuth token
and is never stored.
"""
import json
import time
import hashlib

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PORT = "13267"
SALT = "RAylYC%fmSKp7%Tq"
AUTH_BASIC = "Basic ZHJlYW1lX2FwcHYxOkFQXmR2QHpAU1FZVnhOODg="

BRANDS = {
    "trouver": {"host": ".iot.trouver-tech.com", "ua": "Trouver_Smarthome/1.0.9 (iPhone; iOS 18.4.1; Scale/3.00)", "tenant": "000005"},
    "dreame":  {"host": ".iot.dreame.tech",        "ua": "Dreame_Smarthome/2.1.9 (iPhone; iOS 18.4.1; Scale/3.00)",  "tenant": "000000"},
    "mova":    {"host": ".iot.mova-tech.com",       "ua": "Mova_Smarthome/1.2.4 (iPhone; iOS 18.4.1; Scale/3.00)",    "tenant": "000002"},
}
REGIONS = ["ru", "eu", "us", "sg", "cn"]

SIID_AUDIO = 7
PIID_VOLUME = 1
PIID_ACTIVE = 2
PIID_STATUS = 3
PIID_INSTALL = 4


class CloudError(Exception):
    pass


class AuthError(CloudError):
    pass


class DreameCloud:
    def __init__(self, brand="trouver", region="ru"):
        if brand not in BRANDS:
            raise CloudError(f"unknown brand {brand}")
        if region not in REGIONS:
            raise CloudError(f"unknown region {region}")
        self.brand = brand
        self.region = region
        b = BRANDS[brand]
        self.host_suffix = b["host"]
        self.ua = b["ua"]
        self.tenant = b["tenant"]
        self.base = f"https://{region}{self.host_suffix}:{PORT}"
        self.s = requests.Session()
        self.access_token = None
        self.refresh_token = None
        self.expires_at = 0
        self.devices = []

    # ---- auth ----------------------------------------------------------------
    def _login_headers(self):
        return {
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Language": "en-US;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": self.ua,
            "Authorization": AUTH_BASIC,
            "Tenant-Id": self.tenant,
        }

    def _do_login(self, body):
        r = self.s.post(self.base + "/dreame-auth/oauth/token",
                        headers=self._login_headers(), data=body, timeout=15, verify=True)
        if r.status_code != 200:
            try:
                err = r.json().get("error_description") or r.json().get("error")
            except Exception:
                err = r.text[:120]
            raise AuthError(err or f"login failed [{r.status_code}]")
        d = r.json()
        if "access_token" not in d:
            raise AuthError("no token in response")
        self.access_token = d["access_token"]
        self.refresh_token = d.get("refresh_token", self.refresh_token)
        self.expires_at = time.time() + int(d.get("expires_in", 3600)) - 120
        self.tenant = d.get("tenant_id", self.tenant)
        return d

    def login(self, email, password):
        pw = hashlib.md5((password + SALT).encode()).hexdigest()
        body = ("platform=IOS&scope=all&grant_type=password"
                f"&username={requests.utils.quote(email)}&password={pw}&type=account")
        self._do_login(body)
        return True

    def _refresh(self):
        if not self.refresh_token:
            raise AuthError("session expired")
        body = ("platform=IOS&scope=all&grant_type=refresh_token"
                f"&refresh_token={self.refresh_token}")
        self._do_login(body)

    def ensure_token(self):
        if self.access_token and time.time() < self.expires_at:
            return
        self._refresh()

    # ---- session (in)/(de)hydration for server store -------------------------
    def to_session(self):
        return {"brand": self.brand, "region": self.region, "access_token": self.access_token,
                "refresh_token": self.refresh_token, "expires_at": self.expires_at,
                "tenant": self.tenant, "devices": self.devices}

    @classmethod
    def from_session(cls, d):
        c = cls(d["brand"], d["region"])
        c.access_token = d.get("access_token")
        c.refresh_token = d.get("refresh_token")
        c.expires_at = d.get("expires_at", 0)
        c.tenant = d.get("tenant", c.tenant)
        c.devices = d.get("devices", [])
        return c

    # ---- api -----------------------------------------------------------------
    def _api(self, path, params=None, timeout=15):
        self.ensure_token()
        h = self._login_headers()
        h["Content-Type"] = "application/json"
        h["Dreame-Auth"] = self.access_token
        body = json.dumps(params, separators=(",", ":")) if params is not None else None
        r = self.s.post(f"{self.base}/{path}", headers=h, data=body, timeout=timeout, verify=True)
        if r.status_code == 401:
            self._refresh()
            h["Dreame-Auth"] = self.access_token
            r = self.s.post(f"{self.base}/{path}", headers=h, data=body, timeout=timeout, verify=True)
        if r.status_code != 200:
            raise CloudError(f"api {path} -> [{r.status_code}] {r.text[:120]}")
        return r.json()

    def get_devices(self):
        resp = self._api("dreame-user-iot/iotuserbind/device/listV2")
        if resp.get("code") != 0 or "data" not in resp:
            raise CloudError(f"device list error: {resp}")
        out = []
        for dev in resp["data"].get("page", {}).get("records", []):
            out.append({
                "did": str(dev.get("did")),
                "model": dev.get("model"),
                "name": dev.get("customName") or dev.get("deviceInfo", {}).get("displayName"),
                "mac": dev.get("mac"),
                "bindDomain": dev.get("bindDomain"),
                "online": bool(dev.get("online", dev.get("status"))),
            })
        self.devices = out
        return out

    def _device(self, did):
        for d in self.devices:
            if d["did"] == str(did):
                return d
        raise CloudError("device not in session")

    def _send(self, method, params, did):
        dev = self._device(did)
        host = f"-{dev['bindDomain'].split('.')[0]}" if dev.get("bindDomain") else ""
        envelope = {"did": dev["did"], "id": 1,
                    "data": {"did": dev["did"], "id": 1, "method": method, "params": params}}
        resp = self._api(f"dreame-iot-com{host}/device/sendCommand", envelope)
        data = resp.get("data")
        if not data or "result" not in data:
            raise CloudError(f"{method} -> {resp}")
        return data["result"]

    def get_property(self, did, siid, piid):
        return self._send("get_properties", [{"did": str(did), "siid": siid, "piid": piid}], did)

    def set_property(self, did, siid, piid, value):
        return self._send("set_properties", [{"did": str(did), "siid": siid, "piid": piid, "value": value}], did)

    # ---- voice convenience ---------------------------------------------------
    def voice_state(self, did):
        def val(p):
            try:
                return self.get_property(did, SIID_AUDIO, p)[0].get("value")
            except Exception:
                return None
        return {"volume": val(PIID_VOLUME), "active": val(PIID_ACTIVE), "status": val(PIID_STATUS)}

    def set_volume(self, did, level):
        return self.set_property(did, SIID_AUDIO, PIID_VOLUME, int(level))

    def activate(self, did, pack_id):
        return self.set_property(did, SIID_AUDIO, PIID_ACTIVE, str(pack_id))

    def install(self, did, pack_id, url, md5, size):
        payload = json.dumps({"id": pack_id, "url": url, "md5": md5, "size": int(size)}, separators=(",", ":"))
        return self.set_property(did, SIID_AUDIO, PIID_INSTALL, payload)

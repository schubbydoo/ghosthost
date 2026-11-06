"""Checks for GET /api/capabilities: every entry is well formed, every installed one is backed by real code, and no route family in the
web app is left unexplained (so the list cannot drift from the code).

Run:  PROPKIT_DIR=/path/to/propkit python3 -m unittest tests.test_capabilities     (needs propkit v1.25.0 or newer; Flask installed)
Uses a temporary home folder and temporary sound folder; it never touches the real SoundFiles or settings.
"""
import importlib
import os
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("PROPKIT_DIR", os.path.join(os.path.expanduser("~"), "propkit"))
sys.path.insert(0, os.environ["PROPKIT_DIR"])
try:                                                        # the hardware library only exists on the Pi
    import RPi.GPIO  # noqa: F401
except ImportError:
    rpi = types.ModuleType("RPi"); gpio = types.ModuleType("RPi.GPIO")
    gpio.__getattr__ = lambda name: (lambda *a, **k: 0)
    gpio.BCM = gpio.IN = gpio.OUT = gpio.PUD_UP = gpio.PUD_DOWN = gpio.HIGH = gpio.LOW = 0
    rpi.GPIO = gpio; sys.modules["RPi"] = rpi; sys.modules["RPi.GPIO"] = gpio

from propkit import capabilities as pkcaps                  # noqa: E402
from src.core import capabilities as caps                   # noqa: E402


def _web_app():
    os.environ["HOME"] = tempfile.mkdtemp(prefix="gh-home-")      # login state and tokens go to a temporary home
    from src.core.config_manager import config
    config.set("audio.soundfiles_dir", tempfile.mkdtemp(prefix="gh-sf-"))
    config.save_config = lambda *a, **k: None
    config.load_config = lambda *a, **k: None
    return importlib.import_module("web_interface.app").app


class WellFormed(unittest.TestCase):
    def test_nothing_is_dropped_or_duplicated(self):
        ids = [c["id"] for c in caps.CAPABILITIES]
        self.assertEqual(len(ids), len(set(ids)), "duplicate ids")
        self.assertEqual([c["id"] for c in pkcaps.clean(caps.CAPABILITIES)], ids, "propkit dropped an entry (bad id?)")

    def test_each_entry(self):
        for c in caps.CAPABILITIES:
            self.assertTrue(c["label"].strip() and c["description"].strip(), c["id"])
            self.assertLessEqual(len(c["description"]), 400, c["id"])
            self.assertLessEqual(len(c["plain"]), 3, c["id"])
            if c["installed"]:
                self.assertEqual(c["reason"], "", c["id"])
            else:
                self.assertTrue(c["reason"].strip(), "%s is not installed: it needs a reason" % c["id"])
                self.assertEqual(c["since"], "", c["id"])
                self.assertEqual(c["ops"], [], c["id"])

    def test_there_are_both_kinds(self):
        self.assertTrue([c for c in caps.CAPABILITIES if c["installed"]])
        self.assertTrue([c for c in caps.CAPABILITIES if not c["installed"]])


class NoDrift(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = _web_app()
        cls.rules = {r.rule for r in cls.app.url_map.iter_rules()}

    def test_every_installed_capability_has_proof_and_it_exists(self):
        installed = {c["id"] for c in caps.CAPABILITIES if c["installed"]}
        self.assertEqual(installed, set(caps.PROOFS), "installed capabilities and PROOFS must match")
        for cid, proofs in caps.PROOFS.items():
            self.assertTrue(proofs, cid)
            for kind, what in proofs:
                if kind == "route":
                    self.assertIn(what, self.rules, "%s claims route %s but the app has no such route" % (cid, what))
                elif kind == "module":
                    importlib.import_module(what)
                elif kind == "file":
                    self.assertTrue(os.path.exists(os.path.join(ROOT, what)), "%s claims file %s" % (cid, what))
                else:
                    self.fail("unknown proof kind %r" % kind)

    def test_no_unexplained_route_family(self):
        claimed = {what for proofs in caps.PROOFS.values() for kind, what in proofs if kind == "route"}
        unexplained = set()
        for rule in self.rules:
            if any(rule == c or rule.startswith(c + "/") or rule.startswith(c + "<") for c in claimed):
                continue
            if any(rule == s or rule.startswith(s + "/") or (s != "/" and rule.startswith(s)) for s in caps.SHARED_OR_SUPPORT if s != "/") or rule == "/":
                continue
            unexplained.add(rule)
        self.assertFalse(unexplained, "routes with no capability and no entry in SHARED_OR_SUPPORT: %s" % sorted(unexplained))


class Served(unittest.TestCase):
    def test_endpoint_matches_the_list_and_needs_login_once_a_password_is_set(self):
        app = _web_app()
        c = app.test_client()
        body = c.get("/api/capabilities").get_json()
        self.assertEqual([x["id"] for x in body["capabilities"]], [x["id"] for x in caps.CAPABILITIES])
        self.assertEqual(body["prop"], "Ghost Host")
        self.assertTrue(body["propkit"])
        self.assertTrue(any(not x["installed"] and x["reason"] for x in body["capabilities"]))
        c.post("/setup", data={"username": "ghost-host", "password": "test-password-1", "confirm": "test-password-1"})
        self.assertEqual(app.test_client().get("/api/capabilities").status_code, 401)
        self.assertEqual(c.get("/api/capabilities").status_code, 200)


if __name__ == "__main__":
    unittest.main()

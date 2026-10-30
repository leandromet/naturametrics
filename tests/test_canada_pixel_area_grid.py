"""The pixel area must be measured on the grid the histogram counts (canada aci_history._pixel_area_call).

Without ``crs``, ``ee.Image.pixelArea()`` is reduced on a lat/long grid (580 m² per
"30 m" pixel at 50°N) while the ACI counts true 900 m² Albers pixels: every Canadian
area came out a third low. No network: ``ee`` is replaced by a recorder.
"""

import sys
import types

from naturametrics.canada.services import aci_history


def _fake_ee(calls):
    class Img:
        def reduceRegions(self, **kw):
            calls.append(kw)
            return types.SimpleNamespace(getInfo=lambda: {"features": []})

    ee = types.ModuleType("ee")
    ee.Image = types.SimpleNamespace(pixelArea=lambda: Img())
    ee.Reducer = types.SimpleNamespace(mean=lambda: "mean")
    return ee


class _Counted:
    """A stand-in for the counted image: select(0).projection() names its grid."""
    def select(self, i):
        assert i == 0
        return types.SimpleNamespace(projection=lambda: "ALBERS_30M")


def test_area_is_reduced_on_the_counted_images_grid(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "ee", _fake_ee(calls))
    aci_history._pixel_area_call("fc", 30, 4, _Counted())
    assert calls[-1]["crs"] == "ALBERS_30M" and calls[-1]["scale"] == 30


def test_without_like_no_crs_is_forced(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "ee", _fake_ee(calls))
    aci_history._pixel_area_call("fc", 30, 4)
    assert "crs" not in calls[-1]

import math

import pytest

from app.quantity_kind_orders import QUANTITY_KIND_APPLICABLE_UNITS
from app.ucum import ucum_scale


@pytest.mark.parametrize(
    ("source", "target", "expected"),
    [
        ("u[in_i]", "m", 2.54e-8),
        ("[Btu_IT].[lbf_av]-1", "m", 237.1859911386661),
        ("J/N", "m", 1.0),
        ("MS.m-1", "S.m-1", 1e6),
        ("uS.cm-1", "S.m-1", 1e-4),
        (
            "[Btu_IT].[in_i].[ft_i]-2.s-1.[degF]-1",
            "W.m-1.K-1",
            288.4557777285652,
        ),
        ("kcal_IT.h-1.m-1.Cel-1", "W.m-1.K-1", 1.163),
    ],
)
def test_ucum_scale_matches_typescript_canonical_golden(source, target, expected):
    assert ucum_scale(source, target) == pytest.approx(expected, rel=1e-15)


@pytest.mark.parametrize(
    ("quantity_kind", "canonical_unit"),
    [
        ("Length", "m"),
        ("electromagnetism.ElectricConductivity", "S.m-1"),
        ("thermodynamics.ThermalConductivity", "W.m-1.K-1"),
    ],
)
def test_ucum_scale_covers_every_caemble_kernel_quantity_unit(quantity_kind, canonical_unit):
    for unit in QUANTITY_KIND_APPLICABLE_UNITS[quantity_kind]:
        scale = ucum_scale(unit, canonical_unit)
        assert math.isfinite(scale)
        assert scale > 0


@pytest.mark.parametrize("unit", ["µm", "in", " m", "m ", "s"])
def test_ucum_scale_rejects_noncanonical_or_incompatible_length_units(unit):
    with pytest.raises(ValueError):
        ucum_scale(unit, "m")

"""
CFD utility calculators:
  - Turbulence inlet conditions (k, epsilon, omega, nut from intensity + length scale)
  - y+ / first cell height estimator

Can be used standalone or embedded in the main GUI.
"""

from __future__ import annotations

import math

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QComboBox, QDoubleSpinBox, QSpinBox,
    QTabWidget, QFrame, QTextEdit, QScrollArea, QApplication,
)
from PySide6.QtCore import Qt, Signal


# ================================================================== #
#  Turbulence inlet calculator
# ================================================================== #

def calc_turb_inlet(U_mag: float, intensity: float, length_scale: float,
                    nu: float, method: str = "length_scale") -> dict:
    """Calculate k, epsilon, omega, nut from inlet conditions.

    Args:
        U_mag: velocity magnitude [m/s]
        intensity: turbulence intensity as fraction (e.g. 0.05 for 5%)
        length_scale: turbulent length scale [m] OR hydraulic diameter [m]
        nu: kinematic viscosity [m²/s]
        method: "length_scale" or "hydraulic_diameter"

    Returns:
        dict with k, epsilon, omega, nut, Re_turb, l_turb
    """
    if U_mag <= 0 or intensity <= 0 or length_scale <= 0 or nu <= 0:
        return {"k": 0, "epsilon": 0, "omega": 0, "nut": 0,
                "l_turb": 0, "Re_turb": 0}

    Cmu = 0.09

    # Turbulent kinetic energy
    k = 1.5 * (U_mag * intensity) ** 2

    # Turbulent length scale
    if method == "hydraulic_diameter":
        l_turb = 0.07 * length_scale
    else:
        l_turb = length_scale

    # Dissipation rate
    epsilon = (Cmu ** 0.75) * (k ** 1.5) / l_turb

    # Specific dissipation rate
    omega = k ** 0.5 / (Cmu ** 0.25 * l_turb)

    # Turbulent viscosity
    nut = Cmu * k ** 2 / epsilon if epsilon > 0 else 0

    # Turbulent Reynolds number
    Re_turb = k ** 2 / (nu * epsilon) if epsilon > 0 else 0

    return {
        "k": k,
        "epsilon": epsilon,
        "omega": omega,
        "nut": nut,
        "l_turb": l_turb,
        "Re_turb": Re_turb,
    }


class TurbInletCalculator(QWidget):
    """Widget for calculating turbulence inlet values."""

    values_calculated = Signal(dict)  # emitted with {"k":..., "epsilon":...}

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(QLabel(
            "<b>Turbulence Inlet Calculator</b><br>"
            "<span style='font-size:11px; '>"
            "Compute k, \u03b5, \u03c9, \u03bd<sub>t</sub> from velocity, "
            "intensity, and length scale.</span>"
        ))

        # Inputs
        inp = QGroupBox("Input Parameters")
        form = QFormLayout(inp)

        self.velocity = QDoubleSpinBox()
        self.velocity.setRange(0.001, 1e6)
        self.velocity.setValue(10.0)
        self.velocity.setDecimals(4)
        self.velocity.setSuffix(" m/s")
        form.addRow("Velocity magnitude:", self.velocity)

        self.intensity = QDoubleSpinBox()
        self.intensity.setRange(0.01, 100.0)
        self.intensity.setValue(5.0)
        self.intensity.setDecimals(2)
        self.intensity.setSuffix(" %")
        form.addRow("Turbulence intensity:", self.intensity)

        self.method_combo = QComboBox()
        self.method_combo.addItems(["Turbulent length scale", "Hydraulic diameter"])
        self.method_combo.currentIndexChanged.connect(self._update_label)
        form.addRow("Specify by:", self.method_combo)

        self.length_scale = QDoubleSpinBox()
        self.length_scale.setRange(1e-8, 1e6)
        self.length_scale.setValue(0.01)
        self.length_scale.setDecimals(6)
        self.length_scale.setSuffix(" m")
        self._ls_label = QLabel("Length scale:")
        form.addRow(self._ls_label, self.length_scale)

        self.nu = QDoubleSpinBox()
        self.nu.setRange(1e-12, 1.0)
        self.nu.setValue(1.5e-5)
        self.nu.setDecimals(8)
        self.nu.setSuffix(" m\u00b2/s")
        form.addRow("Kinematic viscosity \u03bd:", self.nu)

        layout.addWidget(inp)

        # Calculate button
        btn_row = QHBoxLayout()
        btn_calc = QPushButton("Calculate")
        btn_calc.setMinimumHeight(32)
        btn_calc.clicked.connect(self._calculate)
        btn_row.addWidget(btn_calc)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Results
        self.results = QGroupBox("Results")
        res_form = QFormLayout(self.results)
        self._res_labels: dict[str, QLineEdit] = {}
        for name, label_text in [
            ("k",       "k [m\u00b2/s\u00b2]"),
            ("epsilon", "\u03b5 [m\u00b2/s\u00b3]"),
            ("omega",   "\u03c9 [1/s]"),
            ("nut",     "\u03bd_t [m\u00b2/s]"),
            ("l_turb",  "l_turb [m]"),
            ("Re_turb", "Re_turb [-]"),
        ]:
            le = QLineEdit()
            le.setReadOnly(True)
            le.setReadOnly(True)  # styled by theme
            self._res_labels[name] = le
            res_form.addRow(label_text + ":", le)
        layout.addWidget(self.results)

        layout.addStretch()

    def _update_label(self, idx):
        if idx == 0:
            self._ls_label.setText("Length scale:")
        else:
            self._ls_label.setText("Hydraulic diameter:")

    def _calculate(self):
        method = "length_scale" if self.method_combo.currentIndex() == 0 \
                 else "hydraulic_diameter"
        vals = calc_turb_inlet(
            U_mag=self.velocity.value(),
            intensity=self.intensity.value() / 100.0,
            length_scale=self.length_scale.value(),
            nu=self.nu.value(),
            method=method,
        )
        for name, le in self._res_labels.items():
            v = vals.get(name, 0)
            le.setText(f"{v:.6g}")
        self.values_calculated.emit(vals)


# ================================================================== #
#  y+ / first cell height estimator
# ================================================================== #

def calc_yplus(Re: float, L_ref: float, nu: float,
               y_plus_target: float = 1.0) -> dict:
    """Estimate first cell height from Reynolds number.

    Uses the flat-plate skin friction correlation:
        Cf = 0.058 * Re^(-0.2)      (turbulent)
        tau_w = 0.5 * Cf * rho * U^2
        u_tau = sqrt(tau_w / rho)
        y = y+ * nu / u_tau

    Args:
        Re: Reynolds number based on L_ref
        L_ref: reference length [m]
        nu: kinematic viscosity [m²/s]
        y_plus_target: desired y+ at first cell centre

    Returns:
        dict with y_first_cell, u_tau, Cf, U_ref, Re, and values
        for several common y+ targets
    """
    if Re <= 0 or L_ref <= 0 or nu <= 0:
        return {"y_first_cell": 0, "u_tau": 0, "Cf": 0, "U_ref": 0,
                "targets": {}}

    U_ref = Re * nu / L_ref

    # Skin friction coefficient (Schlichting flat plate, turbulent)
    Cf = 0.058 * Re ** (-0.2)

    # Friction velocity
    u_tau = U_ref * math.sqrt(Cf / 2.0)

    # First cell height
    y = y_plus_target * nu / u_tau if u_tau > 0 else 0

    # Calculate for common y+ targets
    targets = {}
    for yp in [0.5, 1.0, 5.0, 30.0, 50.0, 100.0, 300.0]:
        targets[yp] = yp * nu / u_tau if u_tau > 0 else 0

    return {
        "y_first_cell": y,
        "u_tau": u_tau,
        "Cf": Cf,
        "U_ref": U_ref,
        "y_plus_target": y_plus_target,
        "targets": targets,
    }


class YPlusCalculator(QWidget):
    """Widget for estimating first cell height from y+ target."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(QLabel(
            "<b>y+ / First Cell Height Estimator</b><br>"
            "<span style='font-size:11px; '>"
            "Estimate wall-normal first cell height for a target y+ value.<br>"
            "Uses flat-plate turbulent BL correlation: "
            "C<sub>f</sub> = 0.058 Re<sup>-0.2</sup></span>"
        ))

        # Inputs
        inp = QGroupBox("Input Parameters")
        form = QFormLayout(inp)

        self.input_mode = QComboBox()
        self.input_mode.addItems(["Velocity + Length", "Reynolds number + Length"])
        self.input_mode.currentIndexChanged.connect(self._toggle_mode)
        form.addRow("Specify by:", self.input_mode)

        self.velocity = QDoubleSpinBox()
        self.velocity.setRange(0.001, 1e6)
        self.velocity.setValue(10.0)
        self.velocity.setDecimals(4)
        self.velocity.setSuffix(" m/s")
        self._vel_label = QLabel("Freestream velocity:")
        form.addRow(self._vel_label, self.velocity)

        self.reynolds = QDoubleSpinBox()
        self.reynolds.setRange(1, 1e12)
        self.reynolds.setValue(1e6)
        self.reynolds.setDecimals(0)
        self._re_label = QLabel("Reynolds number:")
        form.addRow(self._re_label, self.reynolds)

        self.ref_length = QDoubleSpinBox()
        self.ref_length.setRange(1e-6, 1e6)
        self.ref_length.setValue(1.0)
        self.ref_length.setDecimals(6)
        self.ref_length.setSuffix(" m")
        form.addRow("Reference length:", self.ref_length)

        self.nu = QDoubleSpinBox()
        self.nu.setRange(1e-12, 1.0)
        self.nu.setValue(1.5e-5)
        self.nu.setDecimals(8)
        self.nu.setSuffix(" m\u00b2/s")
        form.addRow("Kinematic viscosity \u03bd:", self.nu)

        self.yplus_target = QDoubleSpinBox()
        self.yplus_target.setRange(0.1, 1000.0)
        self.yplus_target.setValue(1.0)
        self.yplus_target.setDecimals(1)
        form.addRow("Target y+:", self.yplus_target)

        layout.addWidget(inp)
        self._toggle_mode(0)

        # Calculate button
        btn_row = QHBoxLayout()
        btn_calc = QPushButton("Calculate")
        btn_calc.setMinimumHeight(32)
        btn_calc.clicked.connect(self._calculate)
        btn_row.addWidget(btn_calc)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Results
        self.results = QGroupBox("Results")
        res_layout = QVBoxLayout(self.results)

        res_form = QFormLayout()
        self._res_y = QLineEdit()
        self._res_y.setReadOnly(True)
        self._res_y.setStyleSheet("font-weight: bold; font-size: 13px;")
        res_form.addRow("First cell height \u0394y:", self._res_y)

        self._res_utau = QLineEdit()
        self._res_utau.setReadOnly(True)
        res_form.addRow("u\u03c4 [m/s]:", self._res_utau)

        self._res_cf = QLineEdit()
        self._res_cf.setReadOnly(True)
        res_form.addRow("C_f [-]:", self._res_cf)

        self._res_re = QLineEdit()
        self._res_re.setReadOnly(True)
        res_form.addRow("Re [-]:", self._res_re)
        res_layout.addLayout(res_form)

        # y+ table
        self._table_label = QLabel()
        self._table_label.setWordWrap(True)
        self._table_label.setStyleSheet("font-size: 11px; padding: 4px;")
        res_layout.addWidget(self._table_label)

        layout.addWidget(self.results)
        layout.addStretch()

    def _toggle_mode(self, idx):
        vel_mode = (idx == 0)
        self.velocity.setVisible(vel_mode)
        self._vel_label.setVisible(vel_mode)
        self.reynolds.setVisible(not vel_mode)
        self._re_label.setVisible(not vel_mode)

    def _calculate(self):
        nu = self.nu.value()
        L = self.ref_length.value()

        if self.input_mode.currentIndex() == 0:
            U = self.velocity.value()
            Re = U * L / nu if nu > 0 else 0
        else:
            Re = self.reynolds.value()

        vals = calc_yplus(Re, L, nu, self.yplus_target.value())

        self._res_y.setText(f"{vals['y_first_cell']:.6g} m")
        self._res_utau.setText(f"{vals['u_tau']:.6g}")
        self._res_cf.setText(f"{vals['Cf']:.6g}")
        self._res_re.setText(f"{Re:.0f}")

        # Build y+ table
        lines = ["<b>\u0394y for common y+ targets:</b><br>"
                 "<table style='border-collapse:collapse;'>"]
        lines.append("<tr><td style='padding:2px 12px;'><b>y+</b></td>"
                     "<td style='padding:2px 12px;'><b>\u0394y [m]</b></td>"
                     "<td style='padding:2px 12px;'><b>Usage</b></td></tr>")
        usage = {
            0.5: "Wall-resolved LES",
            1.0: "Wall-resolved RANS (low-Re)",
            5.0: "Enhanced wall treatment",
            30.0: "Wall functions (lower limit)",
            50.0: "Wall functions (typical)",
            100.0: "Wall functions (acceptable)",
            300.0: "Wall functions (upper limit)",
        }
        for yp, dy in sorted(vals.get("targets", {}).items()):
            u = usage.get(yp, "")
            lines.append(
                f"<tr><td style='padding:2px 12px;'>{yp}</td>"
                f"<td style='padding:2px 12px;'>{dy:.6g}</td>"
                f"<td style='padding:2px 12px; '>{u}</td></tr>")
        lines.append("</table>")
        self._table_label.setText("".join(lines))


# ================================================================== #
#  Layer thickness calculator
# ================================================================== #

def calc_layers(n_layers: int, expansion: float, total_thickness: float,
                first_height: float | None = None) -> dict:
    """Calculate individual layer heights for snappyHexMesh addLayers.

    Provide either total_thickness OR first_height (not both).

    Args:
        n_layers: number of layers
        expansion: expansion ratio (each layer = expansion × previous)
        total_thickness: desired total layer thickness [m]
        first_height: if given, compute total from first layer height

    Returns:
        dict with layers (list of heights), total, first, last, y_plus_ratio
    """
    if n_layers <= 0 or expansion <= 0:
        return {"layers": [], "total": 0, "first": 0, "last": 0}

    if expansion == 1.0:
        if first_height:
            h = first_height
            total = h * n_layers
        else:
            h = total_thickness / n_layers
            total = total_thickness
        layers = [h] * n_layers
        return {"layers": layers, "total": total, "first": h, "last": h}

    # Geometric series: total = h * (r^n - 1) / (r - 1)
    geo_sum = (expansion ** n_layers - 1) / (expansion - 1)

    if first_height:
        h = first_height
        total = h * geo_sum
    else:
        total = total_thickness
        h = total / geo_sum

    layers = []
    for i in range(n_layers):
        layers.append(h * expansion ** i)

    return {
        "layers": layers,
        "total": sum(layers),
        "first": layers[0],
        "last": layers[-1],
    }


class LayerCalculator(QWidget):
    """Widget for computing layer heights for snappyHexMesh."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(QLabel(
            "<b>Boundary Layer Calculator</b><br>"
            "<span style='font-size:11px;'>"
            "Compute individual layer heights for snappyHexMesh addLayers.<br>"
            "Geometric expansion: each layer = ratio \u00d7 previous layer.</span>"
        ))

        inp = QGroupBox("Input Parameters")
        form = QFormLayout(inp)

        self.n_layers = QSpinBox()
        self.n_layers.setRange(1, 100)
        self.n_layers.setValue(5)
        form.addRow("Number of Layers:", self.n_layers)

        self.expansion = QDoubleSpinBox()
        self.expansion.setRange(1.0, 5.0)
        self.expansion.setValue(1.2)
        self.expansion.setDecimals(3)
        form.addRow("Expansion Ratio:", self.expansion)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Total thickness", "First layer height"])
        self.mode_combo.currentIndexChanged.connect(self._toggle_mode)
        form.addRow("Specify:", self.mode_combo)

        self.total_thickness = QDoubleSpinBox()
        self.total_thickness.setRange(1e-8, 1e3)
        self.total_thickness.setValue(0.01)
        self.total_thickness.setDecimals(6)
        self.total_thickness.setSuffix(" m")
        self._total_label = QLabel("Total thickness:")
        form.addRow(self._total_label, self.total_thickness)

        self.first_height = QDoubleSpinBox()
        self.first_height.setRange(1e-10, 1e3)
        self.first_height.setValue(0.001)
        self.first_height.setDecimals(8)
        self.first_height.setSuffix(" m")
        self._first_label = QLabel("First layer height:")
        form.addRow(self._first_label, self.first_height)

        layout.addWidget(inp)
        self._toggle_mode(0)

        btn_row = QHBoxLayout()
        btn_calc = QPushButton("Calculate")
        btn_calc.setMinimumHeight(32)
        btn_calc.clicked.connect(self._calculate)
        btn_row.addWidget(btn_calc)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Results
        self.results = QGroupBox("Layer Stack")
        res_layout = QVBoxLayout(self.results)

        res_form = QFormLayout()
        self._res_total = QLineEdit()
        self._res_total.setReadOnly(True)
        res_form.addRow("Total thickness:", self._res_total)
        self._res_first = QLineEdit()
        self._res_first.setReadOnly(True)
        res_form.addRow("First layer (wall):", self._res_first)
        self._res_last = QLineEdit()
        self._res_last.setReadOnly(True)
        res_form.addRow("Last layer (outer):", self._res_last)
        self._res_ratio_actual = QLineEdit()
        self._res_ratio_actual.setReadOnly(True)
        res_form.addRow("Last/First ratio:", self._res_ratio_actual)
        res_layout.addLayout(res_form)

        self._layer_table = QLabel()
        self._layer_table.setWordWrap(True)
        self._layer_table.setStyleSheet("font-size: 11px; padding: 4px;")
        res_layout.addWidget(self._layer_table)

        layout.addWidget(self.results)
        layout.addStretch()

    def _toggle_mode(self, idx):
        total_mode = (idx == 0)
        self.total_thickness.setVisible(total_mode)
        self._total_label.setVisible(total_mode)
        self.first_height.setVisible(not total_mode)
        self._first_label.setVisible(not total_mode)

    def _calculate(self):
        n = self.n_layers.value()
        exp = self.expansion.value()

        if self.mode_combo.currentIndex() == 0:
            r = calc_layers(n, exp, self.total_thickness.value())
        else:
            r = calc_layers(n, exp, 0, self.first_height.value())

        self._res_total.setText(f"{r['total']:.6g} m")
        self._res_first.setText(f"{r['first']:.6g} m")
        self._res_last.setText(f"{r['last']:.6g} m")
        ratio = r['last'] / r['first'] if r['first'] > 0 else 0
        self._res_ratio_actual.setText(f"{ratio:.3f}")

        # Build layer table
        layers = r.get("layers", [])
        if not layers:
            return

        lines = ["<table style='border-collapse:collapse;'>"]
        lines.append("<tr><td style='padding:2px 8px;'><b>Layer</b></td>"
                     "<td style='padding:2px 8px;'><b>Height [m]</b></td>"
                     "<td style='padding:2px 8px;'><b>Cumulative [m]</b></td></tr>")
        cumulative = 0
        for i, h in enumerate(layers):
            cumulative += h
            label = "wall" if i == 0 else ("outer" if i == len(layers) - 1 else "")
            lines.append(
                f"<tr><td style='padding:2px 8px;'>{i + 1}"
                f"{' (' + label + ')' if label else ''}</td>"
                f"<td style='padding:2px 8px;'>{h:.6g}</td>"
                f"<td style='padding:2px 8px;'>{cumulative:.6g}</td></tr>")
        lines.append("</table>")
        self._layer_table.setText("".join(lines))


# ================================================================== #
#  Dimensionless numbers calculator
# ================================================================== #

def calc_dimensionless(U: float, L: float, nu: float, rho: float,
                       mu: float, Cp: float, k_thermal: float,
                       beta: float, dT: float, g_mag: float,
                       a_sound: float) -> dict:
    """Compute common dimensionless numbers.

    Args:
        U: velocity [m/s]
        L: characteristic length [m]
        nu: kinematic viscosity [m²/s]
        rho: density [kg/m³]
        mu: dynamic viscosity [Pa·s]
        Cp: specific heat [J/(kg·K)]
        k_thermal: thermal conductivity [W/(m·K)]
        beta: thermal expansion coefficient [1/K]
        dT: temperature difference [K]
        g_mag: gravitational acceleration [m/s²]
        a_sound: speed of sound [m/s]

    Returns:
        dict with Re, Pr, Gr, Ra, Ma, Nu_est, St, flow_regime, etc.
    """
    result = {}

    # Reynolds
    Re = U * L / nu if nu > 0 else 0
    result["Re"] = Re

    # Prandtl
    Pr = mu * Cp / k_thermal if k_thermal > 0 else 0
    result["Pr"] = Pr

    # Grashof
    Gr = g_mag * beta * abs(dT) * L ** 3 / nu ** 2 if nu > 0 else 0
    result["Gr"] = Gr

    # Rayleigh
    Ra = Gr * Pr
    result["Ra"] = Ra

    # Mach
    Ma = U / a_sound if a_sound > 0 else 0
    result["Ma"] = Ma

    # Richardson (buoyancy / inertia)
    Ri = Gr / Re ** 2 if Re > 0 else 0
    result["Ri"] = Ri

    # Peclet
    Pe = Re * Pr
    result["Pe"] = Pe

    # Flow regime classification
    if Re < 2300:
        result["regime"] = "Laminar"
    elif Re < 4000:
        result["regime"] = "Transitional"
    else:
        result["regime"] = "Turbulent"

    # Compressibility
    if Ma < 0.3:
        result["compressibility"] = "Incompressible (Ma < 0.3)"
    elif Ma < 0.8:
        result["compressibility"] = "Subsonic compressible"
    elif Ma < 1.2:
        result["compressibility"] = "Transonic"
    else:
        result["compressibility"] = "Supersonic"

    # Convection type
    if Re > 0 and Ri < 0.1:
        result["convection"] = "Forced convection dominant"
    elif Ri > 10:
        result["convection"] = "Natural convection dominant"
    else:
        result["convection"] = "Mixed convection"

    # Solver suggestion
    suggestions = []
    if result["regime"] == "Laminar":
        suggestions.append("icoFoam (transient) or simpleFoam with laminar")
    else:
        suggestions.append("simpleFoam / pimpleFoam with k-\u03c9 SST")
    if Ma >= 0.3:
        suggestions.append("Use rhoSimpleFoam / rhoPimpleFoam (compressible)")
    if Ri > 0.1:
        suggestions.append("Use buoyantSimpleFoam / buoyantPimpleFoam")
    result["suggestions"] = suggestions

    return result


class DimensionlessCalculator(QWidget):
    """Widget for computing dimensionless numbers."""

    def __init__(self, parent=None):
        super().__init__(parent)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(QLabel(
            "<b>Dimensionless Numbers</b><br>"
            "<span style='font-size:11px;'>"
            "Compute Re, Pr, Gr, Ra, Ma and get solver recommendations.</span>"
        ))

        inp = QGroupBox("Flow & Fluid Properties")
        form = QFormLayout(inp)

        self.velocity = QDoubleSpinBox()
        self.velocity.setRange(0, 1e6); self.velocity.setValue(10.0)
        self.velocity.setDecimals(4); self.velocity.setSuffix(" m/s")
        form.addRow("Velocity U:", self.velocity)

        self.length = QDoubleSpinBox()
        self.length.setRange(1e-6, 1e6); self.length.setValue(1.0)
        self.length.setDecimals(6); self.length.setSuffix(" m")
        form.addRow("Characteristic length L:", self.length)

        self.nu = QDoubleSpinBox()
        self.nu.setRange(1e-12, 1); self.nu.setValue(1.5e-5)
        self.nu.setDecimals(8); self.nu.setSuffix(" m\u00b2/s")
        form.addRow("Kinematic viscosity \u03bd:", self.nu)

        self.rho = QDoubleSpinBox()
        self.rho.setRange(0.001, 1e5); self.rho.setValue(1.225)
        self.rho.setDecimals(4); self.rho.setSuffix(" kg/m\u00b3")
        form.addRow("Density \u03c1:", self.rho)

        self.cp = QDoubleSpinBox()
        self.cp.setRange(1, 1e6); self.cp.setValue(1005)
        self.cp.setDecimals(1); self.cp.setSuffix(" J/(kg\u00b7K)")
        form.addRow("Specific heat Cp:", self.cp)

        self.k_thermal = QDoubleSpinBox()
        self.k_thermal.setRange(1e-6, 1e4); self.k_thermal.setValue(0.026)
        self.k_thermal.setDecimals(6); self.k_thermal.setSuffix(" W/(m\u00b7K)")
        form.addRow("Thermal conductivity k:", self.k_thermal)

        self.beta = QDoubleSpinBox()
        self.beta.setRange(0, 1); self.beta.setValue(3.3e-3)
        self.beta.setDecimals(6); self.beta.setSuffix(" 1/K")
        form.addRow("Thermal expansion \u03b2:", self.beta)

        self.dT = QDoubleSpinBox()
        self.dT.setRange(0, 1e5); self.dT.setValue(10)
        self.dT.setDecimals(2); self.dT.setSuffix(" K")
        form.addRow("\u0394T (for buoyancy):", self.dT)

        self.g_mag = QDoubleSpinBox()
        self.g_mag.setRange(0, 1e3); self.g_mag.setValue(9.81)
        self.g_mag.setDecimals(3); self.g_mag.setSuffix(" m/s\u00b2")
        form.addRow("|g| (gravity):", self.g_mag)

        self.a_sound = QDoubleSpinBox()
        self.a_sound.setRange(1, 1e6); self.a_sound.setValue(343)
        self.a_sound.setDecimals(1); self.a_sound.setSuffix(" m/s")
        form.addRow("Speed of sound:", self.a_sound)

        layout.addWidget(inp)

        btn_row = QHBoxLayout()
        btn_calc = QPushButton("Calculate")
        btn_calc.setMinimumHeight(32)
        btn_calc.clicked.connect(self._calculate)
        btn_row.addWidget(btn_calc)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._result_label = QLabel()
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label)

        layout.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _calculate(self):
        mu = self.nu.value() * self.rho.value()
        r = calc_dimensionless(
            U=self.velocity.value(), L=self.length.value(),
            nu=self.nu.value(), rho=self.rho.value(), mu=mu,
            Cp=self.cp.value(), k_thermal=self.k_thermal.value(),
            beta=self.beta.value(), dT=self.dT.value(),
            g_mag=self.g_mag.value(), a_sound=self.a_sound.value(),
        )

        html = ["<table style='border-collapse:collapse;'>"]
        rows = [
            ("Re (Reynolds)", f"{r['Re']:.4g}", r["regime"]),
            ("Pr (Prandtl)", f"{r['Pr']:.4g}", ""),
            ("Gr (Grashof)", f"{r['Gr']:.4g}", ""),
            ("Ra (Rayleigh)", f"{r['Ra']:.4g}",
             "Turbulent nat. conv." if r["Ra"] > 1e8 else
             "Laminar nat. conv." if r["Ra"] > 1e3 else ""),
            ("Ma (Mach)", f"{r['Ma']:.4g}", r["compressibility"]),
            ("Ri (Richardson)", f"{r['Ri']:.4g}", r["convection"]),
            ("Pe (P\u00e9clet)", f"{r['Pe']:.4g}", ""),
        ]
        for name, val, note in rows:
            html.append(
                f"<tr><td style='padding:4px 10px;'><b>{name}</b></td>"
                f"<td style='padding:4px 10px;'>{val}</td>"
                f"<td style='padding:4px 10px; font-size:11px;'>{note}</td></tr>")
        html.append("</table>")

        if r.get("suggestions"):
            html.append("<br><b>Solver suggestions:</b><ul>")
            for s in r["suggestions"]:
                html.append(f"<li>{s}</li>")
            html.append("</ul>")

        self._result_label.setText("".join(html))


# ================================================================== #
#  Unit converter
# ================================================================== #

UNIT_GROUPS = {
    "Pressure": {
        "Pa":   1.0,
        "kPa":  1e3,
        "MPa":  1e6,
        "bar":  1e5,
        "atm":  101325,
        "psi":  6894.757,
        "mmHg": 133.322,
    },
    "Velocity": {
        "m/s":    1.0,
        "km/h":   1 / 3.6,
        "mph":    0.44704,
        "knots":  0.51444,
        "ft/s":   0.3048,
    },
    "Length": {
        "m":    1.0,
        "mm":   1e-3,
        "\u00b5m":  1e-6,
        "cm":   1e-2,
        "km":   1e3,
        "in":   0.0254,
        "ft":   0.3048,
    },
    "Temperature": {
        "K":  "K",
        "\u00b0C": "C",
        "\u00b0F": "F",
    },
    "Density": {
        "kg/m\u00b3":  1.0,
        "g/cm\u00b3":  1000,
        "lb/ft\u00b3": 16.0185,
    },
    "Dynamic Viscosity": {
        "Pa\u00b7s":    1.0,
        "mPa\u00b7s":   1e-3,
        "cP":      1e-3,
        "P (poise)": 0.1,
    },
    "Kinematic Viscosity": {
        "m\u00b2/s":   1.0,
        "mm\u00b2/s":  1e-6,
        "cSt":    1e-6,
        "St":     1e-4,
        "ft\u00b2/s":  0.0929,
    },
    "Thermal Conductivity": {
        "W/(m\u00b7K)":     1.0,
        "kW/(m\u00b7K)":    1000,
        "BTU/(h\u00b7ft\u00b7\u00b0F)": 1.7307,
    },
    "Mass Flow Rate": {
        "kg/s":   1.0,
        "kg/h":   1 / 3600,
        "g/s":    1e-3,
        "lb/s":   0.4536,
        "lb/h":   0.4536 / 3600,
    },
    "Force": {
        "N":     1.0,
        "kN":    1e3,
        "lbf":   4.44822,
        "dyn":   1e-5,
    },
}


def convert_unit(value: float, from_unit: str, to_unit: str,
                 group: dict) -> float:
    """Convert between units in a group."""
    # Temperature is special
    if isinstance(list(group.values())[0], str):
        return _convert_temperature(value, from_unit, to_unit)

    from_factor = group.get(from_unit, 1.0)
    to_factor = group.get(to_unit, 1.0)
    return value * from_factor / to_factor


def _convert_temperature(value: float, from_u: str, to_u: str) -> float:
    # Convert to Kelvin first
    if "\u00b0C" in from_u or from_u == "C":
        k = value + 273.15
    elif "\u00b0F" in from_u or from_u == "F":
        k = (value - 32) * 5 / 9 + 273.15
    else:
        k = value

    # Convert from Kelvin
    if "\u00b0C" in to_u or to_u == "C":
        return k - 273.15
    elif "\u00b0F" in to_u or to_u == "F":
        return (k - 273.15) * 9 / 5 + 32
    return k


class UnitConverter(QWidget):
    """Widget for common CFD unit conversions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(QLabel(
            "<b>Unit Converter</b><br>"
            "<span style='font-size:11px;'>"
            "Convert between common CFD units.</span>"
        ))

        form = QFormLayout()

        self._group_combo = QComboBox()
        self._group_combo.addItems(list(UNIT_GROUPS.keys()))
        self._group_combo.currentTextChanged.connect(self._on_group_changed)
        form.addRow("Quantity:", self._group_combo)

        self._value_input = QDoubleSpinBox()
        self._value_input.setRange(-1e15, 1e15)
        self._value_input.setDecimals(8)
        self._value_input.setValue(1.0)
        self._value_input.valueChanged.connect(self._convert)
        form.addRow("Value:", self._value_input)

        self._from_combo = QComboBox()
        self._from_combo.currentTextChanged.connect(self._convert)
        form.addRow("From:", self._from_combo)

        self._to_combo = QComboBox()
        self._to_combo.currentTextChanged.connect(self._convert)
        form.addRow("To:", self._to_combo)

        layout.addLayout(form)

        self._result = QLineEdit()
        self._result.setReadOnly(True)
        self._result.setStyleSheet("font-size: 16px; font-weight: bold; padding: 8px;")
        layout.addWidget(self._result)

        # All conversions table
        self._all_label = QLabel()
        self._all_label.setWordWrap(True)
        self._all_label.setStyleSheet("font-size: 11px; padding: 4px;")
        layout.addWidget(self._all_label)

        layout.addStretch()
        self._on_group_changed(self._group_combo.currentText())

    def _on_group_changed(self, group_name: str):
        group = UNIT_GROUPS.get(group_name, {})
        units = list(group.keys())
        self._from_combo.blockSignals(True)
        self._to_combo.blockSignals(True)
        self._from_combo.clear()
        self._to_combo.clear()
        self._from_combo.addItems(units)
        self._to_combo.addItems(units)
        if len(units) > 1:
            self._to_combo.setCurrentIndex(1)
        self._from_combo.blockSignals(False)
        self._to_combo.blockSignals(False)
        self._convert()

    def _convert(self):
        group_name = self._group_combo.currentText()
        group = UNIT_GROUPS.get(group_name, {})
        from_u = self._from_combo.currentText()
        to_u = self._to_combo.currentText()
        value = self._value_input.value()

        if not from_u or not to_u:
            return

        result = convert_unit(value, from_u, to_u, group)
        self._result.setText(f"{result:.8g} {to_u}")

        # Show all conversions
        lines = ["<table style='border-collapse:collapse;'>"]
        for unit in group:
            converted = convert_unit(value, from_u, unit, group)
            bold = " font-weight:bold;" if unit == to_u else ""
            lines.append(
                f"<tr><td style='padding:2px 8px;{bold}'>{converted:.8g}</td>"
                f"<td style='padding:2px 8px;{bold}'>{unit}</td></tr>")
        lines.append("</table>")
        self._all_label.setText("".join(lines))


# ================================================================== #
#  Pipe flow calculator
# ================================================================== #

def calc_pipe_flow(D: float, U: float, nu: float, rho: float,
                   L_pipe: float, roughness: float = 0.0) -> dict:
    """Darcy-Weisbach pipe flow calculator.

    Args:
        D: pipe diameter [m]
        U: mean velocity [m/s]
        nu: kinematic viscosity [m²/s]
        rho: density [kg/m³]
        L_pipe: pipe length [m]
        roughness: wall roughness [m] (0 = smooth)

    Returns:
        dict with Re, f (friction factor), dP, regime, etc.
    """
    if D <= 0 or nu <= 0:
        return {"Re": 0, "f": 0, "dP": 0, "regime": "Invalid"}

    Re = U * D / nu

    # Friction factor
    if Re < 2300:
        f = 64 / Re if Re > 0 else 0
        regime = "Laminar"
    else:
        regime = "Turbulent"
        # Colebrook-White (iterative) for turbulent
        e_D = roughness / D if roughness > 0 else 0
        # Churchill correlation (explicit approximation)
        A = (2.457 * math.log(1.0 / ((7 / Re) ** 0.9 + 0.27 * e_D))) ** 16
        B = (37530 / Re) ** 16
        f_churchill = 8 * ((8 / Re) ** 12 + 1 / (A + B) ** 1.5) ** (1 / 12)
        f = f_churchill

    # Pressure drop: dP = f * (L/D) * (0.5 * rho * U²)
    dP = f * (L_pipe / D) * 0.5 * rho * U ** 2 if D > 0 else 0

    # Flow rate
    A_cross = math.pi * D ** 2 / 4
    Q = U * A_cross
    m_dot = rho * Q

    # Head loss
    h_loss = dP / (rho * 9.81) if rho > 0 else 0

    # Power to overcome friction
    P_friction = dP * Q

    return {
        "Re": Re,
        "f": f,
        "dP": dP,
        "regime": regime,
        "Q": Q,
        "m_dot": m_dot,
        "A_cross": A_cross,
        "U_mean": U,
        "h_loss": h_loss,
        "P_friction": P_friction,
        "e_D": roughness / D if D > 0 else 0,
    }


class PipeFlowCalculator(QWidget):
    """Widget for Darcy-Weisbach pipe flow calculations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(QLabel(
            "<b>Pipe Flow Calculator</b><br>"
            "<span style='font-size:11px;'>"
            "Darcy-Weisbach pressure drop, friction factor, and flow "
            "regime for internal pipe flows.</span>"
        ))

        inp = QGroupBox("Pipe & Flow Parameters")
        form = QFormLayout(inp)

        self.diameter = QDoubleSpinBox()
        self.diameter.setRange(1e-6, 100); self.diameter.setValue(0.05)
        self.diameter.setDecimals(6); self.diameter.setSuffix(" m")
        form.addRow("Diameter D:", self.diameter)

        self.velocity = QDoubleSpinBox()
        self.velocity.setRange(0.001, 1e5); self.velocity.setValue(2.0)
        self.velocity.setDecimals(4); self.velocity.setSuffix(" m/s")
        form.addRow("Mean velocity U:", self.velocity)

        self.pipe_length = QDoubleSpinBox()
        self.pipe_length.setRange(0.001, 1e6); self.pipe_length.setValue(10.0)
        self.pipe_length.setDecimals(3); self.pipe_length.setSuffix(" m")
        form.addRow("Pipe length L:", self.pipe_length)

        self.nu = QDoubleSpinBox()
        self.nu.setRange(1e-12, 1); self.nu.setValue(1e-6)
        self.nu.setDecimals(8); self.nu.setSuffix(" m\u00b2/s")
        form.addRow("Kinematic viscosity \u03bd:", self.nu)

        self.rho = QDoubleSpinBox()
        self.rho.setRange(0.001, 1e5); self.rho.setValue(998)
        self.rho.setDecimals(3); self.rho.setSuffix(" kg/m\u00b3")
        form.addRow("Density \u03c1:", self.rho)

        self.roughness = QDoubleSpinBox()
        self.roughness.setRange(0, 0.1); self.roughness.setValue(0)
        self.roughness.setDecimals(6); self.roughness.setSuffix(" m")
        form.addRow("Wall roughness \u03b5:", self.roughness)

        layout.addWidget(inp)

        btn_row = QHBoxLayout()
        btn_calc = QPushButton("Calculate")
        btn_calc.setMinimumHeight(32)
        btn_calc.clicked.connect(self._calculate)
        btn_row.addWidget(btn_calc)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._result_label = QLabel()
        self._result_label.setWordWrap(True)
        layout.addWidget(self._result_label)

        layout.addStretch()

    def _calculate(self):
        r = calc_pipe_flow(
            D=self.diameter.value(), U=self.velocity.value(),
            nu=self.nu.value(), rho=self.rho.value(),
            L_pipe=self.pipe_length.value(),
            roughness=self.roughness.value(),
        )

        html = ["<table style='border-collapse:collapse;'>"]
        rows = [
            ("Reynolds number", f"{r['Re']:.0f}", r["regime"]),
            ("Friction factor f", f"{r['f']:.6g}", "Darcy-Weisbach"),
            ("Relative roughness \u03b5/D", f"{r['e_D']:.4g}",
             "smooth" if r['e_D'] == 0 else ""),
            ("Pressure drop \u0394p", f"{r['dP']:.4g} Pa",
             f"= {r['dP']/1000:.4g} kPa"),
            ("Head loss h_L", f"{r['h_loss']:.4g} m", "of fluid"),
            ("Volume flow Q", f"{r['Q']:.6g} m\u00b3/s",
             f"= {r['Q']*1000:.4g} L/s"),
            ("Mass flow \u1e41", f"{r['m_dot']:.4g} kg/s", ""),
            ("Cross-section A", f"{r['A_cross']:.6g} m\u00b2", ""),
            ("Friction power", f"{r['P_friction']:.4g} W",
             f"= {r['P_friction']/1000:.4g} kW" if r['P_friction'] > 1000 else ""),
        ]
        for name, val, note in rows:
            html.append(
                f"<tr><td style='padding:4px 10px;'><b>{name}</b></td>"
                f"<td style='padding:4px 10px;'>{val}</td>"
                f"<td style='padding:4px 10px; font-size:11px;'>{note}</td></tr>")
        html.append("</table>")

        # Suggestions
        html.append("<br><b>Notes:</b><ul>")
        if r["regime"] == "Laminar":
            html.append("<li>f = 64/Re (Hagen-Poiseuille)</li>")
            html.append("<li>Consider icoFoam or simpleFoam with laminar</li>")
        else:
            html.append("<li>f from Churchill correlation (explicit Colebrook-White)</li>")
            html.append("<li>Use simpleFoam with k-\u03c9 SST or k-\u03b5</li>")
        if r["Re"] > 2000 and r["Re"] < 4000:
            html.append("<li>\u26A0 Transitional regime — results may be unreliable</li>")
        entry_length = 0.06 * r["Re"] * self.diameter.value() if r["regime"] == "Laminar" \
            else 4.4 * r["Re"] ** (1/6) * self.diameter.value()
        html.append(
            f"<li>Estimated entry length: {entry_length:.3g} m "
            f"({entry_length/self.diameter.value():.0f} diameters)</li>")
        html.append("</ul>")

        self._result_label.setText("".join(html))


# ================================================================== #
#  Combined calculator widget (tabbed)
# ================================================================== #

class CalculatorsWidget(QWidget):
    """Tabbed widget combining all calculators."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        self.turb_calc = TurbInletCalculator()
        tabs.addTab(self.turb_calc, "Turbulence Inlet")

        self.yplus_calc = YPlusCalculator()
        tabs.addTab(self.yplus_calc, "y+ Estimator")

        self.layer_calc = LayerCalculator()
        tabs.addTab(self.layer_calc, "Layer Thickness")

        self.dim_calc = DimensionlessCalculator()
        tabs.addTab(self.dim_calc, "Dimensionless Numbers")

        self.unit_conv = UnitConverter()
        tabs.addTab(self.unit_conv, "Unit Converter")

        self.pipe_calc = PipeFlowCalculator()
        tabs.addTab(self.pipe_calc, "Pipe Flow")

        layout.addWidget(tabs)

"""
of_version.py — OpenFOAM version handler.

Defines differences between OpenFOAM Foundation (openfoam.org)
and ESI-OpenCFD (openfoam.com) distributions.

Key differences handled:
  - FoamFile header: website URL, version string
  - turbulenceProperties: 'RASModel'/'LESModel' (org) vs 'model' (com)
  - fvSolution relaxationFactors: p in equations (org) vs fields (com)
  - blockMeshDict: 'convertToMeters' (org) vs 'scale' (com)
  - Surface feature utility: 'surfaceFeatureExtract' (org) vs 'surfaceFeatures' (com)
  - surfaceFeatureExtractDict (org) vs system/surfaceFeaturesDict (com)
"""


class OFVersion:
    """Holds the active OpenFOAM distribution and version string."""

    ORG = "org"
    COM = "com"

    # Available versions per distribution
    VERSIONS = {
        ORG: ["11", "10", "9", "8"],
        COM: ["v2412", "v2312", "v2206", "v2112", "v2006"],
    }

    DEFAULT_VERSION = {ORG: "11", COM: "v2412"}

    def __init__(self, dist=ORG, version=None):
        self.dist = dist
        self.version = version or self.DEFAULT_VERSION.get(dist, "11")

    @property
    def is_org(self):
        return self.dist == self.ORG

    @property
    def is_com(self):
        return self.dist == self.COM

    @property
    def label(self):
        return f"openfoam.{'org' if self.is_org else 'com'} {self.version}"

    # ---- Header ---- #

    @property
    def website(self):
        if self.is_org:
            return "https://openfoam.org"
        return "https://www.openfoam.com"

    @property
    def header_version(self):
        return self.version

    # ---- turbulenceProperties ---- #

    @property
    def ras_model_keyword(self):
        """Keyword for the RAS model name inside the RAS sub-dict."""
        return "RASModel" if self.is_org else "model"

    @property
    def les_model_keyword(self):
        """Keyword for the LES model name inside the LES sub-dict."""
        return "LESModel" if self.is_org else "model"

    # ---- fvSolution relaxation ---- #

    @property
    def p_relax_in_fields(self):
        """Whether pressure relaxation goes in 'fields' (com) or 'equations' (org)."""
        return self.is_com

    # ---- blockMeshDict ---- #

    @property
    def scale_keyword(self):
        """'convertToMeters' (org) vs 'scale' (com)."""
        return "convertToMeters" if self.is_org else "scale"

    # ---- Surface feature extraction ---- #

    @property
    def surface_feature_command(self):
        """Utility command name."""
        return "surfaceFeatures" if self.is_org else "surfaceFeatureExtract"

    @property
    def surface_feature_dict_name(self):
        """Dictionary file name."""
        return "surfaceFeaturesDict" if self.is_org else "surfaceFeatureExtractDict"

    # ---- FoamFile header format ---- #

    @property
    def foamfile_has_note(self):
        """com sometimes includes a note field."""
        return False  # not critical, skip for now

    # ---- Serialization ---- #

    def to_dict(self):
        return {"dist": self.dist, "version": self.version}

    @classmethod
    def from_dict(cls, d):
        return cls(d.get("dist", cls.ORG), d.get("version"))

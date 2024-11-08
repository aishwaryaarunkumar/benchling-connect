from allotropy.allotrope.models.shared.components.plate_reader import SampleRoleType

BRAND_NAME = "Biacore"
PRODUCT_MANUFACTURER = "Cytiva"
DISPLAY_NAME = "Cytiva Biacore T200 Control"
SURFACE_PLASMON_RESONANCE = "surface plasmon resonance"
DEVICE_TYPE = "binding affinity analyzer"
SAMPLE_ROLE_TYPE_MAPPING = {
    "blank role": SampleRoleType.blank_role,
    "sample role": SampleRoleType.sample_role,
}

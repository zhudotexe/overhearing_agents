from pathlib import Path

# ==== core ====
PROJECT_ROOT = Path(__file__).parents[1]

CACHE_DIR = PROJECT_ROOT / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# log instances to logs/ by default
DEFAULT_LOG_DIR = PROJECT_ROOT / "logs"
DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)

# ==== dnd ====
GAMEDATA_BASE_URL = "https://2014.5e.tools"
# equivalent to Parser.SOURCES_CORE_SUPPLEMENTS from 5et
GAMEDATA_ALLOWED_SOURCES = [
    "DMG",
    "EEPC",
    "EET",
    "MM",
    "PHB",
    "SCAG",
    "ToD",
    "VGM",
    "XGE",
    "OGA",
    "MTF",
    "GGR",
    "AI",
    "ESK",
    "AL",
    "SAC",
    "ERLW",
    "RMR",
    "MFF",
    "SADS",
    "EGW",
    "MOT",
    "TCE",
    "VRGR",
    "DoD",
    "MaBJoV",
    "FTD",
    "MPMM",
    "SAiS",
    "AAG",
    "BAM",
    "BGG",
    "TDCSR",
    "PAitM",
    "SatO",
    "ToFW",
    "MPP",
    "BMT",
    "DMTCRG",
    "QftIS",
    "VEoR",
    "TD",
    "HF",
    "HFFotM",
    "MGELFT",
    "VD",
    "HAT-TG",
    "HAT-LMI",
    "PSA",
    "PSI",
    "PSK",
    "PSZ",
    "PSX",
    "PSD",
    "MisMV1",
    "AATM",
]

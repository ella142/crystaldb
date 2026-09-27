from pathlib import Path
from pprint import pprint

from crystaldb.matching.matcher import (
    match_rruff_to_cif,
)


PROJECT_ROOT = Path(
    r"D:\document\aiformaterials\crystaldb"
)

result = match_rruff_to_cif(
    sample_id="R050336",
    cif_path=(
        PROJECT_ROOT
        / "data"
        / "raw"
        / "amcsd"
        / "0012672.cif"
    ),
)

pprint(result)
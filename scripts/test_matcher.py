from pathlib import Path
from pprint import pprint

from crystaldb.matching.matcher import (
    match_rruff_to_cif,
)


PROJECT_ROOT = Path(
    r"D:\document\aiformaterials\crystaldb"
)

result = match_rruff_to_cif(
    sample_id="R080016",

    cif_path=(
        PROJECT_ROOT
        / "data"
        / "raw"
        / "cod"
        / "9000253.cif"
    ),
)

pprint(result)
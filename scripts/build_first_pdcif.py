from pathlib import Path

from crystaldb.mongo import get_database
from crystaldb.pdcif_writer import write_pdcif


PROJECT_ROOT = Path(
    r"D:\document\aiformaterials\crystaldb"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "canonical"
    / "powder"
    / "MEAS_000001.pdCIF"
)


db = get_database()


# 1. 读取 RAW pattern
raw = db.patterns.find_one(
    {
        "measurement_id": "MEAS_000001",
        "representation": "raw",
    }
)

# 2. 读取 Processed pattern
processed = db.patterns.find_one(
    {
        "measurement_id": "MEAS_000001",
        "representation": "processed",
    }
)


if raw is None:
    raise RuntimeError("找不到 RAW pattern")

if processed is None:
    raise RuntimeError("找不到 Processed pattern")


raw_theta = raw["data"]["two_theta"]
raw_intensity = raw["data"]["intensity"]

processed_theta = processed["data"]["two_theta"]
processed_intensity = processed["data"]["intensity"]


# 3. 检查 RAW 和 Processed 是否真的是同一个扫描网格
if len(raw_theta) != len(processed_theta):
    raise ValueError(
        "RAW 和 Processed 的数据点数量不同"
    )

if raw_theta != processed_theta:
    raise ValueError(
        "RAW 和 Processed 的 2theta 网格不同"
    )


# 4. 生成 canonical pdCIF
output = write_pdcif(
    output_path=OUTPUT_PATH,
    measurement_id="MEAS_000001",
    mineral_name="Acanthite",
    two_theta=raw_theta,
    raw_intensity=raw_intensity,
    processed_intensity=processed_intensity,

    # 现在先不猜测实验波长
    wavelength=None,
)


print("pdCIF created:")
print(output)

print("point_count:", len(raw_theta))
from pathlib import Path
import zipfile

from pymongo import MongoClient

from crystaldb.sources.rruff.dif_parser import (
    DEFAULT_ZIP_PATH,
    document_for_entry,
)


TARGET_SAMPLE_ID = "R141118"

TEST_DATABASE = "rruff"
TEST_COLLECTION = "dif_crystaldb_test"


def main():
    zip_path = Path(DEFAULT_ZIP_PATH)

    print(f"ZIP: {zip_path}")

    if not zip_path.exists():
        raise FileNotFoundError(
            f"RRUFF DIF ZIP not found: {zip_path}"
        )

    target_document = None

    with zipfile.ZipFile(zip_path) as archive:
        entries = [
            entry
            for entry in archive.infolist()
            if not entry.is_dir()
        ]

        for entry in entries:
            if (
                f"__{TARGET_SAMPLE_ID}-"
                not in entry.filename
            ):
                continue

            document = document_for_entry(
                zip_path=zip_path,
                zip_hash="",
                entry=entry,
                content=archive.read(entry),
            )

            if (
                document.get("sample_id")
                == TARGET_SAMPLE_ID
            ):
                target_document = document
                break

    if target_document is None:
        raise RuntimeError(
            f"Sample not found: "
            f"{TARGET_SAMPLE_ID}"
        )

    print()
    print("Parsed:")
    print(
        "sample_id:",
        target_document.get("sample_id"),
    )
    print(
        "filename_mineral:",
        target_document.get(
            "filename_mineral"
        ),
    )
    print(
        "mineral:",
        target_document.get("mineral"),
    )

    client = MongoClient(
        "mongodb://127.0.0.1:27017"
    )

    try:
        collection = (
            client[TEST_DATABASE][
                TEST_COLLECTION
            ]
        )

        collection.replace_one(
            {
                "sample_id":
                    target_document[
                        "sample_id"
                    ]
            },
            target_document,
            upsert=True,
        )

        print()
        print(
            f"Written to "
            f"{TEST_DATABASE}."
            f"{TEST_COLLECTION}"
        )

    finally:
        client.close()


if __name__ == "__main__":
    main()
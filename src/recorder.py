import csv
from datetime import datetime
import os


def record(*fields: str) -> None:
    """
    Record the fields to a CSV file.
    @param fields: The fields to record.
    """
    if len(fields) > 5:
        raise ValueError("A maximum of 5 fields are allowed")

    file_path = os.path.expanduser(".cache/recorder.csv")
    file_exists = os.path.isfile(file_path)

    with open(file_path, mode="a", newline="") as file:
        writer = csv.writer(file)

        if not file_exists:
            writer.writerow(
                ["datetime", "field1", "field2", "field3", "field4", "field5"]
            )

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [current_time] + list(fields) + [""] * (5 - len(fields))
        writer.writerow(row)

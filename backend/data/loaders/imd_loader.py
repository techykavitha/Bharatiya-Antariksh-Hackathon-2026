"""
===========================================================
IMD Rainfall Loader
===========================================================

Reads IMD Daily Gridded Rainfall (.grd) binary files.

Dataset:
    Spatial Resolution : 0.25° × 0.25°
    Longitude          : 66.5°E → 100.0°E
    Latitude           : 6.5°N → 38.5°N
    Grid Size          : 135 × 129

Output:
    Rainfall Cube
    Shape -> (days, latitude, longitude)

Author : Hyperion Team
===========================================================
"""

from pathlib import Path
import numpy as np


class IMDRainfallLoader:
    """
    Loader for IMD Daily Rainfall Dataset.
    """

    # ----------------------------
    # Grid Information
    # ----------------------------

    GRID_WIDTH = 135
    GRID_HEIGHT = 129

    LON_START = 66.5
    LAT_START = 6.5

    RESOLUTION = 0.25

    def __init__(self, filepath):
        """
        Parameters
        ----------
        filepath : str or Path
            Path to .grd rainfall file
        """

        self.filepath = Path(filepath)

        if not self.filepath.exists():
            raise FileNotFoundError(
                f"File not found:\n{self.filepath}"
            )

        # Longitude coordinates
        self.longitudes = (
            self.LON_START
            + np.arange(self.GRID_WIDTH) * self.RESOLUTION
        )

        # Latitude coordinates
        self.latitudes = (
            self.LAT_START
            + np.arange(self.GRID_HEIGHT) * self.RESOLUTION
        )

    # --------------------------------------------------

    def load(self):
        """
        Load binary rainfall file.

        Returns
        -------
        dict
            {
                rainfall,
                latitudes,
                longitudes,
                days
            }
        """

        data = np.fromfile(
            self.filepath,
            dtype=np.float32
        )

        total_points = (
            self.GRID_WIDTH *
            self.GRID_HEIGHT
        )

        if data.size % total_points != 0:
            raise ValueError(
                "Invalid IMD rainfall file.\n"
                "File size does not match grid dimensions."
            )

        days = data.size // total_points

       rainfall = data.reshape(
    days,
    self.GRID_HEIGHT,
    self.GRID_WIDTH
)

rainfall = np.where(rainfall == -999.0, np.nan, rainfall)

        return {
            "rainfall": rainfall,
            "latitudes": self.latitudes,
            "longitudes": self.longitudes,
            "days": days
        }

    # --------------------------------------------------

    def summary(self):
        """
        Print dataset information.
        """

        dataset = self.load()

        rain = dataset["rainfall"]

        print("\n========== IMD DATASET ==========")

        print(f"File            : {self.filepath.name}")
        print(f"Days            : {dataset['days']}")
        print(f"Shape           : {rain.shape}")
        print(f"Datatype        : {rain.dtype}")

        print(f"Latitude Range  : {self.latitudes[0]} → {self.latitudes[-1]}")
        print(f"Longitude Range : {self.longitudes[0]} → {self.longitudes[-1]}")

       print(f"Minimum Rainfall : {np.nanmin(rain):.2f} mm")
print(f"Maximum Rainfall : {np.nanmax(rain):.2f} mm")
print(f"Average Rainfall : {np.nanmean(rain):.2f} mm")

        print("=================================\n")


# ----------------------------------------------------------
# Example Usage
# ----------------------------------------------------------

if __name__ == "__main__":

    FILE = (
        "../raw/IMD/rainfall/"
        "Rainfall_ind2025_rfp25.grd"
    )

    loader = IMDRainfallLoader(FILE)

    dataset = loader.load()

    loader.summary()

    rainfall = dataset["rainfall"]

    print("First Grid Cell:")
    print(rainfall[0, 0, 0])

    print("\nFirst Day Shape:")
    print(rainfall[0].shape)
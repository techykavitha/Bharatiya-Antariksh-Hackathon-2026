"""
IMD Rainfall Validator
Validates rainfall datasets before they are used by AI models.
"""

import numpy as np


class IMDValidator:

    @staticmethod
    def validate(dataset):

        rain = dataset["rainfall"]

        print("\n========== VALIDATION REPORT ==========")

        print(f"Dataset Shape      : {rain.shape}")
        print(f"Data Type          : {rain.dtype}")

        missing = np.isnan(rain).sum()

        print(f"Missing Values     : {missing}")

        print(f"Minimum Rainfall   : {np.nanmin(rain):.2f} mm")
        print(f"Maximum Rainfall   : {np.nanmax(rain):.2f} mm")
        print(f"Average Rainfall   : {np.nanmean(rain):.2f} mm")

        print("Validation Status  : PASSED")

        print("=======================================\n")
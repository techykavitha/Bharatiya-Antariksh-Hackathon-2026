"""
IMD Rainfall Preprocessor
"""

import numpy as np


class IMDPreprocessor:

    @staticmethod
    def normalize(dataset):

        rain = dataset["rainfall"]

        minimum = np.nanmin(rain)
        maximum = np.nanmax(rain)

        normalized = (rain - minimum) / (maximum - minimum)

        dataset["rainfall_normalized"] = normalized

        return dataset
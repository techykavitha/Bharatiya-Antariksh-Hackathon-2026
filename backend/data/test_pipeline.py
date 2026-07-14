
from loaders.imd_loader import IMDRainfallLoader
from validation.imd_validator import IMDValidator
from preprocessing.imd_preprocessor import IMDPreprocessor

FILE = "raw/IMD/rainfall/Rainfall_ind2025_rfp25.grd"

loader = IMDRainfallLoader(FILE)

dataset = loader.load()

loader.summary()

IMDValidator.validate(dataset)

dataset = IMDPreprocessor.normalize(dataset)

print("Normalized Shape :", dataset["rainfall_normalized"].shape)

print("\nPipeline Completed Successfully!")
from imd_loader import IMDRainfallLoader

# Path to the IMD rainfall dataset
FILE = "../raw/IMD/rainfall/Rainfall_ind2025_rfp25.grd"

# Create loader
loader = IMDRainfallLoader(FILE)

# Load dataset
dataset = loader.load()

# Extract rainfall array
rainfall = dataset["rainfall"]

# Print summary
loader.summary()

# Additional checks
print("\n===== DATA VALIDATION =====")
print("Shape           :", rainfall.shape)
print("Datatype        :", rainfall.dtype)
print("First Value     :", rainfall[0, 0, 0])
import numpy as np

print("Maximum Rainfall:", np.nanmax(rainfall))
print("Minimum Rainfall:", np.nanmin(rainfall))
print("Mean Rainfall   :", np.nanmean(rainfall))
print("Missing Values  :", np.isnan(rainfall).sum())
print("\nLatitude Points :", len(dataset["latitudes"]))
print("Longitude Points:", len(dataset["longitudes"]))
print("Days            :", dataset["days"])
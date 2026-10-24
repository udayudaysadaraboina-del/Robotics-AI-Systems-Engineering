import math
import numpy as np
import pandas as pd
import torch
import tensorflow as tf

print("--- WORKSTATION VERIFICATION ---")
print("1. Math Module Ready:", math.pi)
print("2. NumPy Version:", np.__version__)
print("3. Pandas Version:", pd.__version__)
print("4. PyTorch Version:", torch.__version__, "| CUDA Active:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("5. Active GPU Device:", torch.cuda.get_device_name(0))
print("6. TensorFlow Version:", tf.__version__)
print("--------------------------------")
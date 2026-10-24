import torch, tensorflow as tf
print("--- WORKSTATION GPU VERIFICATION ---")
print("PyTorch Version:", torch.__version__)
print("CUDA Active:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("Active GPU Device:", torch.cuda.get_device_name(0))
print("TensorFlow Version:", tf.__version__)
print("--------------------------------------")

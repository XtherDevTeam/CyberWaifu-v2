import numpy
import torch

def int2float(sound):
    abs_max = numpy.abs(sound).max()
    sound = sound.astype('float32')
    if abs_max > 0:
        sound *= 1/32768
    sound = sound.squeeze()  # depends on the use case
    return sound

class _SileroVAD:
    def __init__(self, use_onnx=False):
        self.model, self.utils = torch.hub.load('snakers4/silero-vad', 'silero_vad', force_reload=False, onnx=use_onnx)
        
    def predict(self, frame: numpy.ndarray, sample_rate: int) -> bool:
        """
        Predict voice activity detection for a single frame of audio

        Args:
            frame (numpy.ndarray): a single frame of audio

        Returns:
            bool: True if voice activity is detected, False otherwise
        """
        frame = int2float(frame)
        frame = torch.from_numpy(frame)
        # print('frame len', len(frame))
        return self.model(frame, sample_rate).item()
        
    def reset(self):
        """
        Reset the model to its initial state
        """
        self.model.reset_states()
        
        
SileroVAD = _SileroVAD(use_onnx=True)
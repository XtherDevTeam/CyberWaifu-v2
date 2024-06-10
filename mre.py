import av
import time

container = av.open('temp/wdnmd.wav')

lastsec = 0
count = 0
for frame in container.decode(audio=0):
    # for frame in i.decode():
        calc = (frame.pts) * frame.time_base
        print(lastsec, calc.numerator // calc.denominator, frame.pts, frame.samples)
        if calc.numerator // calc.denominator > 0:
            raise RuntimeError(f'there are {count} frames in the first second of the audio file.')
        lastsec = frame.pts
        count += 1
import time
import numpy as np
import matplotlib.pyplot as plt
from neurosky import Connector, Processor

connector = Connector(verbose=True)
processor = Processor()

connector.start()
connector.data.subscribe(processor.add_data)

timestamps = []
values = []
start_time = time.time()


def process_and_plot(data):
    global timestamps, values
    timestamps.append(time.time() - start_time)

    if isinstance(data, list):
        values.append(np.mean(data))
    else:
        values.append(data)

    plt.clf()
    plt.plot(timestamps, values, label="EEG Signal")
    plt.xlabel("Time (s)")
    plt.ylabel("Value")
    plt.title("EEG Data over Time")
    plt.legend()
    plt.pause(0.01)


processor.data.subscribe(process_and_plot)

time.sleep(10)

processor.close()
connector.close()
plt.show()

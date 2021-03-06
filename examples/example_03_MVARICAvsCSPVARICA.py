
"""
This example shows how to decompose motor imagery EEG into sources using
SCPVARICA and visualize a connectivity measure.
"""
import numpy as np

import scot.backend.sklearn     # use scikit-learn backend
#import scot.backend.builtin     # use builtin (default) backend
import scot

from eegtopo.eegpos3d import positions as eeg_locations
from eegtopo.topoplot import topoplot

"""
The example data set contains a continuous 45 channel EEG recording of a motor
imagery experiment. The data was preprocessed to reduce eye movement artifacts
and resampled to a sampling rate of 100 Hz.
With a visual cue the subject was instructed to perform either hand of foot
motor imagery. The the trigger time points of the cues are stored in 'tr', and
'cl' contains the class labels (hand: 1, foot: -1). Duration of the motor 
imagery period was approximately 6 seconds.
"""
import scotdata.motorimagery as midata

raweeg = midata.eeg
triggers = midata.triggers
classes = midata.classes
fs = midata.samplerate
locs = midata.locations


"""
Prepare the data

Here we cut segments from 3s to 4s following each trigger out of the EEG. This
is right in the middle of the motor imagery period.
"""
data = scot.datatools.cut_segments(raweeg, triggers, 3*fs, 4*fs)

"""
Set up the analysis object

We simply choose a VAR model order of 30, and reduction to 4 components (that's not a lot!).
"""
ws = scot.Workspace(30, reducedim=4, fs=fs, locations=locs)

"""
Perform MVARICA
"""
ws.set_data(data, classes)
ws.do_mvarica()
ws.fit_var()
fig1 = ws.plot_connectivity('ffDTF', freq_range=[0,30])
fig1.suptitle('MVARICA')

"""
Perform CSPVARICA
"""
ws.set_data(data, classes)
ws.do_cspvarica()
ws.fit_var()
fig2 = ws.plot_connectivity('ffDTF', freq_range=[0,30])
fig2.suptitle('CSPVARICA')

fig1.savefig('mvarica.png', dpi=900)
fig2.savefig('cspvarica.png', dpi=900)

ws.show_plots()

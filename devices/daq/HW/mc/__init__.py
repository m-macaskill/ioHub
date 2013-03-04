"""
ioHub
.. file: ioHub/devices/daq/__init__.py

Copyright (C)  2012-2013 iSolver Software Solutions
Distributed under the terms of the GNU General Public License (GPL version 3 or any later version).

.. moduleauthor:: Sol Simpson <sol@isolver-software.com> + contributors, please see credits section of documentation.
.. fileauthor:: Sol Simpson
"""


import sys
import ioHub
from ... import DAQDevice, DAMultiChannelInputEvent#, DASingleChannelInputEvent
from .... import Computer, EventConstants, DeviceConstants, ioDeviceError
from ctypes import *
from constants import *

class DAQ(DAQDevice):
    """
    """

    DAQ_CHANNEL_MAPPING=dict()
    DAQ_CHANNEL_MAPPING['AI_0']=0
    DAQ_CHANNEL_MAPPING['AI_1']=1
    DAQ_CHANNEL_MAPPING['AI_2']=2
    DAQ_CHANNEL_MAPPING['AI_3']=3
    DAQ_CHANNEL_MAPPING['AI_4']=4
    DAQ_CHANNEL_MAPPING['AI_5']=5
    DAQ_CHANNEL_MAPPING['AI_6']=6
    DAQ_CHANNEL_MAPPING['AI_7']=7
    DAQ_CHANNEL_MAPPING['AI_8']=8
    DAQ_CHANNEL_MAPPING['AI_9']=9
    DAQ_CHANNEL_MAPPING['AI_10']=10
    DAQ_CHANNEL_MAPPING['AI_11']=11
    DAQ_CHANNEL_MAPPING['AI_12']=12
    DAQ_CHANNEL_MAPPING['AI_13']=13
    DAQ_CHANNEL_MAPPING['AI_14']=14
    DAQ_CHANNEL_MAPPING['AI_15']=15
    DAQ_CHANNEL_MAPPING['DI_0']=0
    DAQ_CHANNEL_MAPPING['DI_1']=1
    DAQ_CHANNEL_MAPPING['DI_2']=2
    DAQ_CHANNEL_MAPPING['DI_3']=3
    DAQ_CHANNEL_MAPPING['DI_4']=4
    DAQ_CHANNEL_MAPPING['DI_5']=5
    DAQ_CHANNEL_MAPPING['DI_6']=6
    DAQ_CHANNEL_MAPPING['DI_7']=7
    DAQ_CHANNEL_MAPPING['DI_8']=8
    DAQ_CHANNEL_MAPPING['DI_9']=9
    DAQ_CHANNEL_MAPPING['DI_10']=10
    DAQ_CHANNEL_MAPPING['DI_11']=11
    DAQ_CHANNEL_MAPPING['DI_12']=12
    DAQ_CHANNEL_MAPPING['DI_13']=13
    DAQ_CHANNEL_MAPPING['DI_14']=14
    DAQ_CHANNEL_MAPPING['DI_15']=15

    DAQ_GAIN_OPTIONS=dict()
    DAQ_GAIN_OPTIONS['BIP10VOLTS']=BIP10VOLTS

    DAQ_CONFIG_OPTIONS=dict()
    DAQ_CONFIG_OPTIONS['DEFAULTOPTION']=DEFAULTOPTION

    DAQ_MODEL_OPTIONS=dict()
    DAQ_MODEL_OPTIONS['MC-USB-1208FS']='MC-USB-1208FS'
    DAQ_MODEL_OPTIONS['MC-USB-1616FS']='MC-USB-1616FS'

    DAQ_BLOCK_TRANSFER_SIZE=dict()
    DAQ_BLOCK_TRANSFER_SIZE['MC-USB-1208FS']=31
    DAQ_BLOCK_TRANSFER_SIZE['MC-USB-1616FS']=62

    ALL_EVENT_CLASSES=[]
    # <<<<<
    lastPollTime=0.0

    # >>> implementation specific private class attributes
    _DLL=None
    # <<<

    DEVICE_MODEL_ID=1
    DEVICE_TYPE_ID=DeviceConstants.DAQ
    DEVICE_TYPE_STRING=DeviceConstants.getName(DEVICE_TYPE_ID)

    _newDataTypes=[('board_id','i4'),('input_channels','a128'),('gain','i4'),('offset','f4'),('options','i4')]
    __slots__=[e[0] for e in _newDataTypes]+['_MemHandle','_daqStatus','_HighResolution_A2D','_A2D_Resolution','_A2DData','_revision','_lastChannelReadValueDict',
                                             '_input_read_method','_input_scan_frequency',"_input_sample_count","_input_poll_type","_currentIndex","_currentCount","_lastSampleCount","_lastIndex",
                                             '_AI_function','_A2DSamples','_eventsCreated','_wrapCount','_lastStartRecordingTimePre','_lastStartRecordingTimePost',
                                             '_lowChannelAI','_highChannelAI','_daq_model']

    def __init__(self,*args,**kwargs):
        """
        """
        deviceConfig=kwargs['dconfig']

        self._startupConfiguration = deviceConfig


        DAQ.ALL_EVENT_CLASSES=[DAMultiChannelInputEvent,]

        deviceConfig['monitor_event_types']=deviceConfig.get('monitor_event_types',DAQ.ALL_EVENT_CLASSES)
        deviceConfig['device_class']=DAQ.__name__
        deviceConfig['name']=deviceConfig.get('name','daq')
        deviceConfig['max_event_buffer_length']=deviceConfig.get('event_buffer_length',1024)
        deviceConfig['type_id']=self.DEVICE_TYPE_ID
        deviceConfig['os_device_code']='OS_DEV_CODE_NOT_SET'
        deviceConfig['board_id']=deviceConfig.get('board_id',0)

        deviceConfig['input_channels']=tuple(deviceConfig.get('input_channels',tuple()))
        ioHub.print2err("Going to monitor input channels:",deviceConfig['input_channels'])

        deviceConfig['gain']=self.DAQ_GAIN_OPTIONS[deviceConfig.get('gain','BIP10VOLTS')]
        deviceConfig['offset']=deviceConfig.get('offset',0.0)
        deviceConfig['options']=self.DAQ_CONFIG_OPTIONS[deviceConfig.get('options',DEFAULTOPTION)]
        deviceConfig['_isReportingEvents']=deviceConfig.get('auto_report_events',False)

        DAQDevice.__init__(self,*args,**deviceConfig)
        
        self._input_read_method=deviceConfig.get('input_read_method','SCAN')
        self._input_scan_frequency=c_int(deviceConfig.get('input_scan_frequency',1000))
        self._daq_model=deviceConfig.get('daq_model','UNKNOWN')
        if self._daq_model in self.DAQ_BLOCK_TRANSFER_SIZE:
            self._input_sample_count=self.DAQ_BLOCK_TRANSFER_SIZE[self._daq_model]*8
        else:
            ioHub.print2err("DAQ Model not supported or not set. Supported models are %s, using daq_model parameter."%(str(self.DAQ_MODEL_OPTIONS.keys()),))
            raise ioDeviceError(self,"DAQ Model not supported: %s"%(self._daq_model))
        self._input_poll_type=deviceConfig.get('input_poll_type','ALL')

        if self._input_read_method == 'POLL':
            DAQ._localPoll=DAQ._pollSequential
        elif self._input_read_method == 'SCAN':
            DAQ._localPoll=DAQ._scanningPoll


        self._lastChannelReadValueDict=dict()
        for c in self.input_channels:
            self._lastChannelReadValueDict[c]=(None,None) # (lastReadTime, lastReadValue)


        #--------------------------------------

        inputChannelCount=len(self.input_channels)

        if inputChannelCount > 0:
            _DLL = windll.LoadLibrary("cbw32.dll")
            DAQ._DLL = _DLL

            #ioHub.print2err("DLL: ",DAQ._DLL)

            self._revision=c_float(CURRENTREVNUM)
            ULStat = _DLL.cbDeclareRevision(byref(self._revision))
            #ioHub.print2err('ULStat cbDeclareRevision: ',self._revision,' : ',ULStat)

            # Initiate error handling
            # Parameters:
            # PRINTALL :all warnings and errors encountered will be printed
            # DONTSTOP :program will continue even if error occurs.
            # Note that STOPALL and STOPFATAL are only effective in
            # Windows applications, not Console applications.
            _DLL.cbErrHandling (c_int(PRINTALL),c_int(DONTSTOP))

            self._A2D_Resolution=c_int(0)

            board=c_int32(self.board_id)
            #ioHub.print2err('board: ', board)

            #1208FS
            #self.options = NOCONVERTDATA + BACKGROUND + CONTINUOUS + CALIBRATEDATA

            #1616FS
            self.options = BACKGROUND + CONTINUOUS
            #ioHub.print2err('self.options: ', self.options)


            # /* Get the resolution of A/D */
            _DLL.cbGetConfig(c_int(BOARDINFO), board, 0, c_int(BIADRES), byref(self._A2D_Resolution))

            #ioHub.print2err('A2D_Resolution: ',self._A2D_Resolution)

            self._HighResolution_A2D=False
            if self._A2D_Resolution.value > 12:
                self._HighResolution_A2D=True
            #ioHub.print2err('_HighResolution_A2D: ',self._HighResolution_A2D)

            if self._input_read_method == 'SCAN':
                count=c_int(self._input_sample_count)
                #ioHub.print2err('count: ', count)

                if self._HighResolution_A2D:
                    #ioHub.print2err("** Using cbWinBufAlloc for 16 bit card **")
                    self._MemHandle=_DLL.cbWinBufAlloc(count)
                    self._A2DData = cast(self._MemHandle,POINTER(c_uint16))
                else:
                    self._MemHandle=_DLL.cbWinBufAlloc(count)
                    self._A2DData = cast(self._MemHandle,POINTER(c_uint16))



                #ioHub.print2err('_MemHandle ', self._MemHandle)
                #ioHub.print2err('_A2DData ', self._A2DData)


                if self._MemHandle == 0:   # Make sure it is a valid pointer
                    ioHub.print2err("\nERROR ALLOCATING DAQ MEMORY: out of memory\n")
                    sys.exit(1)

                lowChan=32
                highChan=0
                saveChannels=[]
                for chan in self.input_channels:
                    if chan[0:2] == 'AI':
                        chanVal=self.DAQ_CHANNEL_MAPPING[chan]
                        saveChannels.append(chanVal)
                        if lowChan > chanVal:
                            lowChan=chanVal
                        if highChan < chanVal:
                            highChan=chanVal
                saveChannels=tuple(saveChannels)

                if lowChan == 32 and highChan == 0:
                    ioHub.print2err('ERROR: No Analaog Channels Spefied to Monitor: ',self.input_channels )
                    sys.exit(1)

                self._lowChannelAI=c_int(lowChan)
                self._highChannelAI=c_int(highChan)
                #ioHub.print2err('_lowChannelAI: ', self._lowChannelAI)
                #ioHub.print2err('_highChannelAI: ', self._highChannelAI)

                self._currentIndex=c_long(0)
                self._currentCount=c_long(0)
                #ioHub.print2err('_currentIndex: ', self._currentIndex)
                #ioHub.print2err('_currentCount: ', self._currentCount)

                self._lastSampleCount=c_long(0)
                self._lastIndex=c_long(0)
                self._eventsCreated=0
                self._AI_function=c_uint16(AIFUNCTION)
                #ioHub.print2err('_lastSampleCount: ', self._lastSampleCount)
                #ioHub.print2err('_lastIndex: ', self._lastIndex)
                #ioHub.print2err('_eventsCreated: ', self._eventsCreated)
                #ioHub.print2err('_AI_function: ', self._AI_function)

                self._wrapCount=0
                #ioHub.print2err('_wrapCount: ', self._wrapCount)



                class DAQSampleArray(Structure):
                    _fields_ = [('low_channel', c_int),('high_channel', c_int),('save_channels', POINTER(c_int)),("readChannelsCount", c_int),("saveChannelsCount", c_int),("count", c_int), ("indexes", POINTER(c_uint)),("values", POINTER(c_uint16)),("channels", POINTER(c_ushort))]

                    @staticmethod
                    def create(low,high,saveChannels,asize):
                        dsb = DAQSampleArray()
                        dsb.indexes=(c_uint * asize)()
                        dsb.values=(c_uint16 * asize)()
                        dsb.channels=(c_ushort * asize)()
                        dsb.count=asize
                        dsb.low_channel=low
                        dsb.high_channel=high
                        dsb.readChannelsCount=c_int(8)
                        dsb.saveChannelsCount=c_int(len(saveChannels))
                        dsb.save_channels=(c_int * dsb.saveChannelsCount)(*saveChannels)
                        return dsb

                    def zero(self):
                        for d in xrange(self.count):
                            self.indexes[d]=0
                            self.values[d]=0
                            self.channels[d]=0


                self._A2DSamples=DAQSampleArray.create(self._lowChannelAI,self._highChannelAI,saveChannels,self._input_sample_count)


                self.enableEventReporting(False)
                if self.isReportingEvents():
                    self.enableEventReporting(True)


    def enableEventReporting(self,enable):
        ioHub.print2err("---------------------------------------------")
        ioHub.print2err("DAQ.enableEventReporting: ",enable)
        current=self.isReportingEvents()
        if current == enable:
            return current

        if DAQDevice.enableEventReporting(self,enable) is True:
            #ioHub.print2err('self.options: ', self.options)

            board=c_int32(self.board_id)
            ioHub.print2err('board: ', board)

            ioHub.print2err('rate: ', self._input_scan_frequency)

            gain = c_int(self.gain)
            ioHub.print2err('gain: ', gain)

            self._daqStatus=c_short(RUNNING)
            ioHub.print2err('_daqStatus: ', self._daqStatus)

            self._lastStartRecordingTimePre=Computer.currentSec()
            ulStat = self._DLL.cbAInScan(board, 0, 7, c_int(self._input_sample_count), byref(self._input_scan_frequency), gain, self._MemHandle, self.options)
            self._lastStartRecordingTimePost=Computer.currentSec()
            ioHub.print2err('*** self._lastStartRecordingTimePost: ',self._lastStartRecordingTimePost)


            ioHub.print2err('ulStat: ', ulStat)
            ioHub.print2err('rate after: ', self._input_scan_frequency)
        else:
            board=c_int32(self.board_id)

            ulStat = self._DLL.cbStopBackground (board)  # this should be taking board ID and AIFUNCTION
                                                         # but when ever I give it second param ctypes throws
                                                         # a `4 bytes too much`error
            ioHub.print2err("cbStopBackground: ",ulStat)
            self._daqStatus=c_short(IDLE)
            ioHub.print2err('_daqStatus: ', self._daqStatus)
            self._A2DSamples.zero()
            self._lastStartRecordingTimePre=0.0
            self._lastStartRecordingTimePost=0.0
            ioHub.print2err('_A2DSamples cleared')
        ioHub.print2err("---------------------------------------------")

    def _localPoll(self):
        ioHub.print2err("ERROR: INVALID INPUT READING TYPE SPECIFIED: ",self._input_read_method)

    def _poll(self):
        if DAQDevice._poll(self):
            return self._localPoll()
        else:
            return False

    def _close(self):
        #/* The BACKGROUND operation must be explicitly stopped
        #Parameters:
        #BoardNum    :the number used by CB.CFG to describe this board
        #FunctionType: A/D operation (AIFUNCTION)*/
        board=c_int32(self.board_id)

        ulStat = self._DLL.cbStopBackground (board)  # this should be taking board ID and AIFUNCTION
                                                 # but when ever I give it second param ctypes throws
                                                 # a `4 bytes too much`error
        #ioHub.print2err("cbStopBackground: ",ulStat)

        ulStat=self._DLL.cbWinBufFree(cast(self._MemHandle,POINTER(c_void_p)))
        #ioHub.print2err("cbWinBufFree _MemHandle: ",ulStat)

    def __del__(self):
        try:
            self._close()
        except:
            pass

    def _scanningPoll(self):
        #/*Parameters:
        #BoardNum    :number used by CB.CFG to describe this board
        #Chan        :input channel number
        #Gain        :gain for the board in BoardNum
        #DataValue   :value collected from Chan */

        board=c_int32(self.board_id)

        if self._daqStatus.value == RUNNING:
            ulStat = self._DLL.cbGetStatus (board, byref(self._daqStatus), byref(self._currentCount), byref(self._currentIndex))#,AIFUNCTION)
            logged_time = Computer.currentSec()
            if self._currentCount.value > 0 and self._currentIndex.value > 0:
                currentIndex=self._currentIndex.value
                currentSampleCount=self._currentCount.value
                lastIndex=self._lastIndex.value
                samples=self._A2DSamples

                #ioHub.print2err("cc: %ld\tec: %ld"%(self._currentCount.value,self._eventsCreated))
                #ioHub.print2err("c_index: %ld, l_index: %ld,  c_count: %ld, l_count %ld"%(currentIndex,lastIndex,currentSampleCount,self._lastSampleCount.value))
                if lastIndex != currentIndex:

                        # only for 1208FS
                        #ulStat = self._DLL.cbAConvertData (board, self._currentIndex, self._A2DData,None)

                        self._lastIndex=c_long(currentIndex)
                        self._lastSampleCount=c_long(currentSampleCount)

                        if lastIndex>currentIndex:
                            self._wrapCount+=1

                            for v in xrange(lastIndex,self._input_sample_count):
                                #ioHub.print2err("v: %d\t%d"%(v,self._A2DData[v]))
                                self._saveScannedEvent(logged_time,samples,v)

                            lastIndex=0

                        for v in xrange(lastIndex,currentIndex):
                                #ioHub.print2err("v: %d\t%d"%(v,self._A2DData[v]))
                                self._saveScannedEvent(logged_time,samples,v)
        else:
           ioHub.print2err("Warning: MC DAQ not running")

    def _saveScannedEvent(self,logged_time,asamples,aindex,dsamples=None,dindex=None,timer1=None,timer2=None):
        achannel=self._eventsCreated%asamples.readChannelsCount

        asamples.values[aindex]=self._A2DData[aindex]
        #if achannel in asamples.save_channels:
        #    asamples.values[aindex]=self._A2DData[aindex]
        #else:
        #    asamples.values[aindex]=0
        
        
        asamples.indexes[aindex]=self._eventsCreated/asamples.readChannelsCount
        asamples.channels[aindex]=achannel

        if achannel == asamples.readChannelsCount-1 and self.isReportingEvents():
            mce=self._createMultiChannelEventList(logged_time,asamples,aindex-achannel)
            self._addNativeEventToBuffer(mce)
        self._eventsCreated+=1


    def _createMultiChannelEventList(self,logged_time,samples,index):
        time=(float(samples.indexes[index])/float(self._input_scan_frequency.value))+self._lastStartRecordingTimePost

        daqEvent=[0,    # exp id
            0,              # session id
            Computer._getNextEventID(),  # event id
            DAMultiChannelInputEvent.EVENT_TYPE_ID,    # event type
            0,   # device time
            logged_time,  # logged time
            time,       # hub time
            self._lastStartRecordingTimePost-self._lastStartRecordingTimePre, # confidence interval
            logged_time-time,        # delay
            0,                       # filter_id
            self.DEVICE_MODEL_ID,
            float(samples.values[index]),         # analog input 0
            float(samples.values[index+1]),       # analog input 1
            float(samples.values[index+2]),       # analog input 2
            float(samples.values[index+3]),       # analog input 3
            float(samples.values[index+4]),       # analog input 4
            float(samples.values[index+5]),       # analog input 5
            float(samples.values[index+6]),       # analog input 6
            float(samples.values[index+7])       # analog input 7
            ]
        return daqEvent

    def _pollSequential(self):
        # works, but takes 1 msec per channel to get the data, so each channel is interleaved
        # and it is 'slow'. Might be fine for some initial tests with dual recording,
        # but not good enough for prime time.
        #ioHub.print2err("_pollSequential: start")
        numChannels=len(self.input_channels)
        dataValue = c_float(23.0)
        if numChannels:
            #ioHub.print2err( "numChannels: ",numChannels)
            for chan in self.input_channels:
                lastChanTime,lastChanValue=self._lastChannelReadValueDict[chan]
                stime=Computer.currentSec()
                udStat = self._DLL.cbVIn (self.board_id, c_int(self.DAQ_CHANNEL_MAPPING[chan]), self.gain, byref(dataValue), self.options)
                ctime=Computer.currentSec()
                if udStat == NOERRORS:
                    if (dataValue.value != lastChanValue) or lastChanTime is None:
                        edelay=ctime-stime
                        ci=0.0
                        if lastChanTime is not None:
                            ci=ctime-lastChanTime
                        eventDict=dict(logged_time=ctime, device_time=ctime, channel_name=chan,float_value=dataValue.value, delay=edelay, confidence_interval=ci)
                        self._addNativeEventToBuffer(self._createSingleChannelEventList(**eventDict))
                        self._lastChannelReadValueDict[chan]=(stime,dataValue.value)
                    else:
                        self._lastChannelReadValueDict[chan]=(stime,lastChanValue)
                else:
                    ioHub.print2err( "ERROR: ", udStat,dataValue ,dataValue.value)

    def _createSingleChannelEventList(self,**kwargs):
        device_time=0
        logged_time=0
        delay=0.0
        confidence_interval=0.0
        channel_name='UNKNOWN'
        float_value=0.0
        int_value=0

        if kwargs:
            if 'device_time' in kwargs:
                device_time=kwargs['device_time']
            if 'logged_time' in kwargs:
                logged_time=kwargs['logged_time']
            if 'delay' in kwargs:
                delay=kwargs['delay']
            if 'confidence_interval' in kwargs:
                confidence_interval=kwargs['confidence_interval']
            if 'channel_name' in kwargs:
                channel_name=kwargs['channel_name']
            if 'float_value' in kwargs:
                float_value=kwargs['float_value']
            if 'int_value' in kwargs:
                int_value=kwargs['int_value']

        time=logged_time-delay

        daqEvent=[0,    # exp id
                  0,              # session id
                  Computer._getNextEventID(),  # event id
                  DASingleChannelInputEvent.EVENT_TYPE_ID,    # event type
                  device_time,          # device time
                  logged_time,          # logged time
                  time,             # hub time
                  confidence_interval, # confidence interval
                  delay,                # delay
                  channel_name,         # name of channel
                  float_value,          # float value of event, if applicable
                  int_value             # int value of event, if applicable
                  ]
        return daqEvent


    def _getIOHubEventObject(self,event):
        return event # already a DAQ Event
